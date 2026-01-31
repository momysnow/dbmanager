import os
from pathlib import Path
from core.security import SecurityManager

def test_key_generation(temp_home):
    """Test that a master key is generated if not present"""
    key_path = temp_home / ".dbmanager" / ".secret.key"
    assert not key_path.exists()
    
    sec = SecurityManager(key_path)
    assert key_path.exists()
    assert key_path.stat().st_mode & 0o777 == 0o600 # Check permissions

def test_encryption_decryption(temp_home):
    """Test roundtrip encryption/decryption"""
    sec = SecurityManager()
    
    original = "secret_password_123"
    encrypted = sec.encrypt(original)
    
    assert encrypted != original
    assert encrypted.startswith("gAAAA") # Fernet token format
    
    decrypted = sec.decrypt(encrypted)
    assert decrypted == original

def test_decrypt_plaintext(temp_home):
    """Test that decrypting plaintext returns it as is (migration scenario)"""
    sec = SecurityManager()
    
    plaintext = "not_encrypted"
    assert sec.decrypt(plaintext) == plaintext

def test_env_var_key(temp_home):
    """Test using key from env var"""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    os.environ["DBMANAGER_MASTER_KEY"] = key
    
    sec = SecurityManager()
    encrypted = sec.encrypt("foo")
    
    # Manually decrypt with same key
    f = Fernet(key.encode())
    assert f.decrypt(encrypted.encode()).decode() == "foo"
