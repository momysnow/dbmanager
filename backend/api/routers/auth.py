import os
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Deque, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import COOKIE_NAME, auth_manager, get_current_user
from core.audit import record_audit
from db.engine import get_db
from db.models.user import User


def _cookie_kwargs() -> Dict[str, object]:
    """Cookie attributes used by login/logout. SameSite=Strict + httpOnly +
    Secure (unless explicitly disabled for local HTTP dev) make this
    cookie unreadable from JS and not sent on cross-site requests."""
    insecure = os.getenv("DBMANAGER_COOKIE_INSECURE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": not insecure,
        "samesite": "strict",
        # Scope to the v1 API surface so a future /api/v2 with different
        # validation rules cannot inherit the v1 session cookie.
        "path": "/api/v1",
    }

router = APIRouter()


class UserMe(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


# --- Simple in-memory rate limiter -------------------------------------------
# IMPORTANT: state is per-process. Safe for single-node deploys (the default
# docker-compose ships with one backend replica). If you scale horizontally
# you MUST front the API with a shared store (Redis / DB) — otherwise an
# attacker can spread brute-force attempts across replicas to bypass the
# limits. The startup hook in api/main.py refuses placeholder JWT secrets
# which is the more important brute-force mitigation.
_WINDOW_SECONDS = 60
_IP_MAX = 5
_USER_MAX = 10
_LOCKOUT_THRESHOLD = 10
_LOCKOUT_SECONDS = 15 * 60

_ip_hits: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=64))
_user_hits: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=64))
_user_lockout: Dict[str, float] = {}


def _prune(q: Deque[float], now: float) -> None:
    cutoff = now - _WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()


def _rate_check(ip: str, username: str) -> Tuple[bool, str]:
    now = time.monotonic()
    locked_until = _user_lockout.get(username)
    if locked_until and locked_until > now:
        return False, "account_locked"
    _prune(_ip_hits[ip], now)
    _prune(_user_hits[username], now)
    if len(_ip_hits[ip]) >= _IP_MAX:
        return False, "ip_rate"
    if len(_user_hits[username]) >= _USER_MAX:
        return False, "user_rate"
    return True, ""


def _record_failure(ip: str, username: str) -> None:
    now = time.monotonic()
    _ip_hits[ip].append(now)
    _user_hits[username].append(now)
    if len(_user_hits[username]) >= _LOCKOUT_THRESHOLD:
        _user_lockout[username] = now + _LOCKOUT_SECONDS


def _record_success(username: str) -> None:
    _user_hits.pop(username, None)
    _user_lockout.pop(username, None)


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/token")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    ip = _client_ip(request)
    username = form_data.username

    ok, reason = _rate_check(ip, username)
    if not ok:
        # Critical audit: sync write so lockout events are not lost.
        await record_audit(
            action=(
                "auth.login.lockout"
                if reason == "account_locked"
                else "auth.login.rate_limited"
            ),
            status="denied",
            resource_type="auth",
            request=request,
            details={"username": username, "reason": reason},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, try again later",
        )

    user = await auth_manager.authenticate(form_data.username, form_data.password, db)
    if not user:
        _record_failure(ip, username)
        await record_audit(
            action="auth.login",
            status="failure",
            resource_type="auth",
            request=request,
            details={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _record_success(username)
    await record_audit(
        action="auth.login",
        status="success",
        resource_type="auth",
        user=user,
        request=request,
        details={"username": user.username},
    )
    access_token = auth_manager.create_access_token(
        data={"sub": user.username, "tv": user.token_version}
    )
    # Set httpOnly+Secure+SameSite=Strict cookie so the browser ships the
    # token automatically without exposing it to JS (XSS-safe).
    response.set_cookie(
        value=access_token,
        max_age=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_cookie_kwargs(),
    )
    # Body still includes the token for non-browser clients (CLI, scripts).
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    response.delete_cookie(
        key=COOKIE_NAME,
        # Must mirror the path used by login (_cookie_kwargs); browsers
        # delete cookies only on an exact (domain, path) match.
        path=_cookie_kwargs()["path"],
        samesite="strict",
        secure=_cookie_kwargs()["secure"],
        httponly=True,
    )
    await record_audit(
        action="auth.logout",
        status="success",
        user=current_user,
        request=request,
    )
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserMe)
async def get_me(current_user: User = Depends(get_current_user)) -> UserMe:
    return UserMe.model_validate(current_user)


@router.post("/me/password")
async def change_own_password(
    body: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if not auth_manager.verify_password(
        body.current_password, current_user.password_hash
    ):
        await record_audit(
            action="auth.password_change",
            status="failure",
            user=current_user,
            request=request,
        )
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from current"
        )
    if current_user.username.lower() in body.new_password.lower():
        raise HTTPException(
            status_code=400, detail="Password must not contain username"
        )

    current_user.password_hash = auth_manager.get_password_hash(body.new_password)
    current_user.must_change_password = False
    current_user.token_version = (current_user.token_version or 0) + 1
    await db.commit()
    await record_audit(
        action="auth.password_change",
        status="success",
        user=current_user,
        request=request,
    )
    return {"detail": "Password updated. Please log in again."}
