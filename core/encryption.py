"""Encryption utilities for backup files using AES-256.

Provides secure encryption/decryption for database backups.
Uses AES-256 in GCM mode for authenticated encryption.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


def is_encryption_available() -> bool:
    """Check if encryption is available (cryptography library installed)"""
    return ENCRYPTION_AVAILABLE


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit encryption key from a password using PBKDF2.
    
    Args:
        password: User password
        salt: Random salt (should be 16 bytes)
    
    Returns:
        32-byte encryption key
    """
    if not ENCRYPTION_AVAILABLE:
        raise EncryptionError("Encryption not available. Install: pip install cryptography")
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=100000,  # OWASP recommended minimum
    )
    return kdf.derive(password.encode())


def encrypt_file(file_path: str, password: str, remove_original: bool = False) -> str:
    """
    Encrypt a file using AES-256-GCM.
    
    File format:
    - 16 bytes: salt for key derivation
    - 12 bytes: nonce/IV for AES-GCM
    - N bytes: encrypted data + 16 bytes authentication tag
    
    Args:
        file_path: Path to file to encrypt
        password: Encryption password
        remove_original: Whether to delete original file after encryption
    
    Returns:
        Path to encrypted file (.enc extension)
    
    Raises:
        EncryptionError: If encryption fails
    """
    if not ENCRYPTION_AVAILABLE:
        raise EncryptionError("Encryption not available. Install: pip install cryptography")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Generate random salt and nonce
    salt = os.urandom(16)  # 128 bits
    nonce = os.urandom(12)  # 96 bits (recommended for GCM)
    
    # Derive key from password
    key = derive_key_from_password(password, salt)
    
    # Read plaintext
    try:
        with open(file_path, 'rb') as f:
            plaintext = f.read()
    except Exception as e:
        raise EncryptionError(f"Failed to read file: {e}")
    
    # Encrypt with AES-GCM
    try:
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}")
    
    # Write encrypted file
    encrypted_path = f"{file_path}.enc"
    try:
        with open(encrypted_path, 'wb') as f:
            f.write(salt)        # 16 bytes
            f.write(nonce)       # 12 bytes
            f.write(ciphertext)  # encrypted data + auth tag
    except Exception as e:
        raise EncryptionError(f"Failed to write encrypted file: {e}")
    
    # Remove original if requested
    if remove_original and os.path.exists(encrypted_path):
        os.remove(file_path)
    
    return encrypted_path


def decrypt_file(file_path: str, password: str, output_path: Optional[str] = None,
                remove_encrypted: bool = False) -> str:
    """
    Decrypt a file encrypted with encrypt_file().
    
    Args:
        file_path: Path to encrypted file (.enc)
        password: Decryption password
        output_path: Optional output path (auto-generated if None)
        remove_encrypted: Whether to delete encrypted file after decryption
    
    Returns:
        Path to decrypted file
    
    Raises:
        EncryptionError: If decryption fails (wrong password or corrupted file)
    """
    if not ENCRYPTION_AVAILABLE:
        raise EncryptionError("Encryption not available. Install: pip install cryptography")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Read encrypted file
    try:
        with open(file_path, 'rb') as f:
            salt = f.read(16)       # 16 bytes
            nonce = f.read(12)      # 12 bytes
            ciphertext = f.read()   # rest of file
    except Exception as e:
        raise EncryptionError(f"Failed to read encrypted file: {e}")
    
    # Validate file format
    if len(salt) != 16 or len(nonce) != 12:
        raise EncryptionError("Invalid encrypted file format")
    
    # Derive key from password
    try:
        key = derive_key_from_password(password, salt)
    except Exception as e:
        raise EncryptionError(f"Key derivation failed: {e}")
    
    # Decrypt with AES-GCM
    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise EncryptionError(f"Decryption failed (wrong password or corrupted file): {e}")
    
    # Determine output path
    if output_path is None:
        # Remove .enc extension
        file_path_obj = Path(file_path)
        if file_path_obj.suffix == '.enc':
            output_path = str(file_path_obj.with_suffix(''))
        else:
            output_path = f"{file_path}.dec"
    
    # Write decrypted file
    try:
        with open(output_path, 'wb') as f:
            f.write(plaintext)
    except Exception as e:
        raise EncryptionError(f"Failed to write decrypted file: {e}")
    
    # Remove encrypted file if requested
    if remove_encrypted and os.path.exists(output_path):
        os.remove(file_path)
    
    return output_path


def generate_random_password(length: int = 32) -> str:
    """
    Generate a cryptographically secure random password.
    
    Args:
        length: Password length (default 32 characters)
    
    Returns:
        Random password (base64-like characters)
    """
    import base64
    random_bytes = os.urandom(length)
    return base64.urlsafe_b64encode(random_bytes).decode()[:length]


def get_encryption_info() -> dict:
    """
    Get information about encryption capabilities.
    
    Returns:
        Dictionary with encryption details
    """
    return {
        'available': ENCRYPTION_AVAILABLE,
        'algorithm': 'AES-256-GCM',
        'key_derivation': 'PBKDF2-SHA256 (100k iterations)',
        'features': [
            'Authenticated encryption (prevents tampering)',
            'Password-based encryption',
            'Automatic random salt and nonce',
            'OWASP recommended parameters'
        ]
    }
