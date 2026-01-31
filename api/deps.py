from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from core.auth import AuthManager
from config import ConfigManager

# We need a way to access AuthManager globally or instantiate it
# Since config is global via ConfigManager(), we can instantiate AuthManager here
config_manager = ConfigManager()
auth_manager = AuthManager(config_manager)

# Create initial user if needed (on startup import)
# Ideally this should be in main startup event, but fine here for now
auth_manager.create_initial_user()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = auth_manager.decode_token(token)
    if payload is None:
        raise credentials_exception
        
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
        
    user = auth_manager.get_user(username)
    if user is None:
        raise credentials_exception
        
    return user
