import os
from typing import AsyncGenerator, Callable, List

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Endpoints that remain reachable while must_change_password is set.
_PW_CHANGE_ALLOWLIST = {
    "/api/v1/auth/me",
    "/api/v1/auth/me/password",
    "/api/v1/auth/logout",
}


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = auth_manager.decode_token(token)
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
