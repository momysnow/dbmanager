from datetime import datetime, timedelta
import os
from typing import Any, Dict, Optional, cast
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import ConfigManager


class AuthManager:
    # Hash context
    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

    # Token settings
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        # Use a configured JWT secret if present, otherwise generate one.
        # We reuse the encryption master key context to avoid extra secrets.
        self.secret_key = self._get_or_create_secret_key()

    def _get_or_create_secret_key(self) -> str:
        # Environment override
        env_secret = os.getenv("DBMANAGER_JWT_SECRET")
        if env_secret:
            return env_secret

        # Check config
        auth_config = self.config_manager.config.get("auth", {})
        secret = auth_config.get("jwt_secret")

        if not secret:
            # Generate new secret
            import secrets

            secret = secrets.token_urlsafe(32)
            # Save to config
            if "auth" not in self.config_manager.config:
                self.config_manager.config["auth"] = {}
            self.config_manager.config["auth"]["jwt_secret"] = secret
            self.config_manager.save_config()

        return str(secret)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bool(self.pwd_context.verify(plain_password, hashed_password))

    def get_password_hash(self, password: str) -> str:
        return str(self.pwd_context.hash(password))

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.ALGORITHM)
        return str(encoded_jwt)

    def decode_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.ALGORITHM])
            return cast(Dict[str, Any], payload)
        except JWTError:
            return None

    def create_initial_user(
        self, username: str = "admin", password: str = "admin"
    ) -> bool:
        """Create initial admin user if no users exist"""
        if not username or not password:
            return False
        users = self.config_manager.config.get("users", [])
        if not users:
            hashed = self.get_password_hash(password)
            user = {
                "username": username,
                "password_hash": hashed,
                "role": "admin",
                "created_at": datetime.now().isoformat(),
            }
            # Ensure the users list exists and persist it.
            if "users" not in self.config_manager.config:
                self.config_manager.config["users"] = []
            self.config_manager.config["users"].append(user)
            self.config_manager.save_config()
            return True
        return False

    def get_user(self, username: str) -> Optional[Dict]:
        users = self.config_manager.config.get("users", [])
        for user in users:
            if user["username"] == username:
                return cast(Dict[str, Any], user)
        return None
