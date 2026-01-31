import json
import os
from config import ConfigManager, CONFIG_FILE

def test_config_encryption_on_save(temp_home):
    """Test that sensitive fields are encrypted when saved to disk"""
    config = ConfigManager()
    
    # Add a database with password
    db_config = {
        "name": "TestDB",
        "provider": "postgres",
        "params": {
            "host": "localhost",
            "password": "my_secret_password"
        }
    }
    
    config.add_database(db_config)
    
    # Read raw file from disk
    with open(CONFIG_FILE, "r") as f:
        saved_data = json.load(f)
        
    saved_db = saved_data["databases"][0]
    saved_password = saved_db["params"]["password"]
    
    assert saved_password != "my_secret_password"
    assert saved_password.startswith("gAAAA")

def test_config_decryption_on_load(temp_home):
    """Test that encrypted config is decrypted when loaded into memory"""
    config = ConfigManager()
    
    # Add DB (saves encrypted)
    db_config = {
        "name": "TestDB",
        "provider": "postgres",
        "params": {
            "host": "localhost",
            "password": "my_secret_password"
        }
    }
    config.add_database(db_config)
    
    # Reload config
    new_config = ConfigManager()
    loaded_db = new_config.get_databases()[0]
    
    assert loaded_db["params"]["password"] == "my_secret_password"
