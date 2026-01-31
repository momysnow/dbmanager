import os
import base64
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityManager:
    """
    Handles encryption and decryption of sensitive data using Fernet (symmetric encryption).
    The key is derived from a master key file or environment variable.
    """
    
    def __init__(self, key_path: Optional[Path] = None):
        self._fernet: Optional[Fernet] = None
        self._key_path = key_path or Path.home() / ".dbmanager" / ".secret.key"
        self._init_key()
    
    def _init_key(self):
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
                        pass # Invalid key in file, will regenerate

        # 3. Generate new key
        key = Fernet.generate_key()
        
        # Ensure dir exists
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save key with strict permissions
        with open(self._key_path, "wb") as f:
            f.write(key)
        
        # Set permissions to read/write only by owner (600)
        try:
            os.chmod(self._key_path, 0o600)
        except Exception:
            pass # Might fail on Windows or some FS
            
        self._fernet = Fernet(key)
        
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not data:
            return data
        
        # If already encrypted (heuristic: starts with gAAAA), return as is
        # Fernet tokens start with gAAAA
        if data.startswith("gAAAA"):
            try:
                # Validate it's a real token
                self._fernet.decrypt(data.encode())
                return data
            except Exception:
                pass # Not a valid token, proceed to encrypt
                
        return self._fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, data: str) -> str:
        """Decrypt string data"""
        if not data:
            return data
            
        try:
            return self._fernet.decrypt(data.encode()).decode()
        except Exception:
            # If decryption fails, it might be plaintext (legacy) return as is
            # This handles migration scenario
            return data

# Singleton instance not created here to allow dependency injection
