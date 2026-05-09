import os
from typing import AsyncGenerator, Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import AuthManager
from config import ConfigManager
from db.engine import get_db
from db.models.user import User
from db.repositories.users_repo import get_user_by_username

config_manager = ConfigManager()
auth_manager = AuthManager(config_manager)

# Name of the httpOnly session cookie. Kept in sync with the frontend.
COOKIE_NAME = "dbmanager_session"

# auto_error=False: we resolve the token ourselves so we can fall back to the
# httpOnly cookie when the Authorization header is missing.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token", auto_error=False
)

# Endpoints that remain reachable while must_change_password is set.
_PW_CHANGE_ALLOWLIST = {
    "/api/v1/auth/me",
    "/api/v1/auth/me/password",
    "/api/v1/auth/logout",
}

# State-changing methods need stricter CSRF protection than SameSite=Strict
# alone. We require a custom header that browsers refuse to set on cross-site
# requests without a CORS preflight, and our CORS allow-list is explicit.
_STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    cookie_token = request.cookies.get(COOKIE_NAME)
    # CSRF: when authenticating via cookie on a state-changing request,
    # require the X-Requested-With header. Browsers will not set this on a
    # cross-origin <form> POST and our CORS config forbids the header from
    # untrusted origins via preflight.
    if (
        cookie_token
        and not token
        and request.method in _STATE_CHANGING
        and request.headers.get("x-requested-with", "").lower()
        != "xmlhttprequest"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Requested-With header (CSRF protection)",
        )

    effective_token = token or cookie_token
    if not effective_token:
        raise credentials_exception

    payload = auth_manager.decode_token(effective_token)
    if payload is None:
        raise credentials_exception

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise credentials_exception

    user = await get_user_by_username(db, subject)
    if user is None or not user.is_active:
        raise credentials_exception

    # Token-version check: password reset / forced logout invalidates old tokens.
    token_ver = payload.get("tv")
    if not isinstance(token_ver, int) or token_ver != user.token_version:
        raise credentials_exception

    # Force password change: only the allowlisted endpoints are reachable.
    if user.must_change_password and request.url.path not in _PW_CHANGE_ALLOWLIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )

    # Expose user to middleware for correct audit attribution.
    request.state.current_user = user
    return user


def require_role(*roles: str) -> Callable:
    """Dependency factory. Raises 403 if current user's role not in allowed roles."""

    async def _check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.role not in roles:
            # Critical audit: write synchronously before raising so it can't be lost.
            from core.audit import record_audit

            await record_audit(
                action="access.denied",
                resource_type=request.url.path,
                status="denied",
                user=current_user,
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check
