from datetime import datetime, timedelta, timezone
import os
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import ConfigManager
from db.models.user import User
from db.repositories.users_repo import get_user_by_username, update_last_login


class AuthManager:
    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    # `aud` and `iss` claims aren't strictly required for a single-app
    # deployment, but pinning them costs nothing and turns a hypothetical
    # secret-reuse incident (same JWT secret used by another service) into
    # a 401 instead of a confused-deputy authentication.
    JWT_ISSUER = "dbmanager"
    JWT_AUDIENCE = "dbmanager-api"
    # Pre-computed argon2 hash of a random string, used for constant-time
    # verification when the username doesn't exist.
    DUMMY_HASH = (
        "$argon2id$v=19$m=65536,t=3,p=4$"
        "c29tZXNhbHRzb21lc2FsdA$"
        "dGhpc2lzbm90YXJlYWxoYXNodGhpc2lzbm90YXJlYWxo"
    )

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.secret_key = self._get_or_create_secret_key()

    # Known placeholder values that ship in .env.example. Refuse to boot if
    # any of these reach production unchanged — they would let any attacker
    # forge a valid JWT.
    _REJECTED_JWT_SECRETS = {
        "change-me-jwt-secret",
        "change-me",
        "changeme",
        "secret",
        "default",
    }

    def _get_or_create_secret_key(self) -> str:
        env_secret = os.getenv("DBMANAGER_JWT_SECRET")
        if env_secret:
            if env_secret.strip().lower() in self._REJECTED_JWT_SECRETS:
                raise RuntimeError(
                    "DBMANAGER_JWT_SECRET is set to a known placeholder value. "
                    "Generate a strong secret (e.g. `python -c \"import secrets;"
                    " print(secrets.token_urlsafe(48))\"`) and set it in .env "
                    "before starting the API."
                )
            if len(env_secret) < 32:
                raise RuntimeError(
                    "DBMANAGER_JWT_SECRET is too short (<32 chars). Use at "
                    "least 32 random characters."
                )
            return env_secret

        auth_config = self.config_manager.config.get("auth", {})
        secret = auth_config.get("jwt_secret")

        if not secret:
            import secrets

            secret = secrets.token_urlsafe(32)
            if "auth" not in self.config_manager.config:
                self.config_manager.config["auth"] = {}
            self.config_manager.config["auth"]["jwt_secret"] = secret
            self.config_manager.save_config()

        return str(secret)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bool(self.pwd_context.verify(plain_password, hashed_password))
        except Exception:
            return False

    def burn_cycles(self, password: str) -> None:
        """Verify against a dummy hash to equalize timing when user not found."""
        try:
            self.pwd_context.verify(password, self.DUMMY_HASH)
        except Exception:
            pass

    def get_password_hash(self, password: str) -> str:
        return str(self.pwd_context.hash(password))

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.now(timezone.utc),
                "iss": self.JWT_ISSUER,
                "aud": self.JWT_AUDIENCE,
            }
        )
        return str(jwt.encode(to_encode, self.secret_key, algorithm=self.ALGORITHM))

    def decode_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.ALGORITHM],
                audience=self.JWT_AUDIENCE,
                issuer=self.JWT_ISSUER,
            )
            return dict(payload)
        except JWTError:
            return None

    async def authenticate(
        self, username: str, password: str, session: AsyncSession
    ) -> Optional[User]:
        user = await get_user_by_username(session, username)
        if not user:
            # Run a dummy verify to keep timing flat for unknown usernames.
            self.burn_cycles(password)
            return None
        if not user.is_active:
            self.burn_cycles(password)
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        await update_last_login(session, user)
        await session.commit()
        return user
