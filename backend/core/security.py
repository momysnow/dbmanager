import logging
import os
import sys
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Handles encryption and decryption of sensitive data using Fernet
    (symmetric encryption).
    The key is derived from a master key file or environment variable.
    """

    def __init__(self, key_path: Optional[Path] = None) -> None:
        self._fernet: Optional[Fernet] = None
        self._key_path = key_path or Path.home() / ".dbmanager" / ".secret.key"
        self._init_key()

    def _init_key(self) -> None:
        """Initialize encryption key"""
        # 1. Try environment variable
        env_key = os.getenv("DBMANAGER_MASTER_KEY")
        if env_key:
            self._fernet = Fernet(env_key.encode())
            return

        # 2. Try loading from file
        if self._key_path.exists():
            with open(self._key_path, "rb") as f:
                key = f.read().strip()
                if key:
                    try:
                        self._fernet = Fernet(key)
                        return
                    except Exception:
                        pass  # Invalid key in file, will regenerate

        # 3. Generate new key
        key = Fernet.generate_key()

        # Ensure dir exists with strict perms first (owner-only).
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            try:
                os.chmod(self._key_path.parent, 0o700)
            except OSError as exc:
                logger.warning(
                    "Could not chmod %s to 0700: %s", self._key_path.parent, exc
                )

        # Save key with strict permissions (owner read/write only).
        # Use os.open with mode so the file is never world-readable, even
        # transiently between write and chmod.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(self._key_path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(key)
        except Exception:
            os.close(fd)
            raise

        if sys.platform != "win32":
            try:
                os.chmod(self._key_path, 0o600)
            except OSError as exc:
                # On Unix this is a hard failure: a world-readable master key
                # is unacceptable. Refuse to continue.
                raise RuntimeError(
                    f"Failed to set 0600 perms on {self._key_path}: {exc}. "
                    "Refusing to start with a potentially world-readable key."
                ) from exc

        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not data:
            return data
        if self._fernet is None:
            raise RuntimeError("Encryption key not initialized")

        # If already encrypted (heuristic: starts with gAAAA), return as is
        # Fernet tokens start with gAAAA
        if data.startswith("gAAAA"):
            try:
                # Validate it's a real token
                self._fernet.decrypt(data.encode())
                return data
            except Exception:
                pass  # Not a valid token, proceed to encrypt

        return str(self._fernet.encrypt(data.encode()).decode())

    def decrypt(self, data: str) -> str:
        """Decrypt string data"""
        if not data:
            return data
        if self._fernet is None:
            raise RuntimeError("Encryption key not initialized")

        try:
            return str(self._fernet.decrypt(data.encode()).decode())
        except Exception:
            # If decryption fails, it might be plaintext (legacy) return as is
            # This handles migration scenario
            return data


# Singleton instance not created here to allow dependency injection
