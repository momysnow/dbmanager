import os
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.auth import AuthManager
from config import ConfigManager

# We need a way to access AuthManager globally or instantiate it
# Since config is global via ConfigManager(), we can instantiate AuthManager here
config_manager = ConfigManager()
auth_manager = AuthManager(config_manager)

# Create initial user if needed (on startup import)
# Allows configuration via environment variables
create_admin = os.getenv("DBMANAGER_CREATE_ADMIN", "true").lower() not in {
    "0",
    "false",
    "no",
}
if create_admin:
    admin_user = os.getenv("DBMANAGER_ADMIN_USER", "admin")
    admin_password = os.getenv("DBMANAGER_ADMIN_PASSWORD", "admin")
    auth_manager.create_initial_user(username=admin_user, password=admin_password)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Return the authenticated user or raise an HTTP 401 error."""
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

    user = auth_manager.get_user(subject)
    if user is None:
        raise credentials_exception

    return user
