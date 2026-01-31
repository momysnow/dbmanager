import json
import os
from pathlib import Path
from typing import List, Dict, Any

# Allow override via env var, default to home dir
CONFIG_DIR = Path(os.getenv("DBMANAGER_DATA_DIR", Path.home() / ".dbmanager"))
CONFIG_FILE = CONFIG_DIR / "config.json"

class ConfigManager:
    def __init__(self):
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self):
        if not CONFIG_DIR.exists():
            CONFIG_DIR.mkdir()
        if not CONFIG_FILE.exists():
            default_config = {
                "databases": [],
                "s3_buckets": [],
                "config_sync_bucket_id": None,
                "global_settings": {
                    "compression": {
                        "enabled": False,
                        "algorithm": "gzip",
                        "level": 6
                    },
                    "encryption": {
                        "enabled": False,
                        "password": None
                    }
                }
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(default_config, f, indent=4)

    def _load_config(self) -> Dict[str, Any]:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)
        
        # Auto-sync to S3 if enabled
        self._sync_to_s3()
    
    def _sync_to_s3(self):
        """Sync config to S3 if configured"""
        try:
            # Avoid circular import
            from core.config_sync import ConfigSync
            from core.bucket_manager import BucketManager
            
            # Only sync if bucket is configured
            bucket_id = self.config.get('config_sync_bucket_id')
            if bucket_id:
                bucket_manager = BucketManager(self)
                config_sync = ConfigSync(bucket_manager, self)
                config_sync.sync_to_s3(silent=True)
        except Exception:
            # Silently fail to avoid breaking config saves
            pass

    def add_database(self, db_config: Dict[str, Any]):
        # Generate a simple ID if not present
        if "id" not in db_config:
            existing_ids = [db.get("id", 0) for db in self.config["databases"]]
            new_id = max(existing_ids) + 1 if existing_ids else 1
            db_config["id"] = new_id
        
        self.config["databases"].append(db_config)
        self.save_config()
        return db_config["id"]

    def get_databases(self) -> List[Dict[str, Any]]:
        return self.config.get("databases", [])

    def get_database(self, db_id: int) -> Dict[str, Any]:
        for db in self.config["databases"]:
            if db.get("id") == db_id:
                return db
        return None

    def remove_database(self, db_id: int):
        self.config["databases"] = [db for db in self.config["databases"] if db.get("id") != db_id]
        self.save_config()

    def update_database(self, db_id: int, new_config: Dict[str, Any]):
        for i, db in enumerate(self.config["databases"]):
            if db.get("id") == db_id:
                # Keep the ID, update everything else
                new_config["id"] = db_id
                self.config["databases"][i] = new_config
                self.save_config()
                return True
        return False
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings (compression, etc.)"""
        return self.config.get("global_settings", {
            "compression": {
                "enabled": False,
                "algorithm": "gzip",
                "level": 6
            }
        })
    
    def update_global_settings(self, settings: Dict[str, Any]):
        """Update global settings"""
        if "global_settings" not in self.config:
            self.config["global_settings"] = {}
        self.config["global_settings"].update(settings)
        self.save_config()
    
    def get_compression_settings(self) -> Dict[str, Any]:
        """Get compression settings"""
        global_settings = self.get_global_settings()
        return global_settings.get("compression", {
            "enabled": False,
            "algorithm": "gzip",
            "level": 6
        })
    
    def update_compression_settings(self, enabled: bool = None, 
                                   algorithm: str = None, level: int = None):
        """Update compression settings"""
        settings = self.get_compression_settings()
        
        if enabled is not None:
            settings["enabled"] = enabled
        if algorithm is not None:
            settings["algorithm"] = algorithm
        if level is not None:
            settings["level"] = level
        
        global_settings = self.get_global_settings()
        global_settings["compression"] = settings
        self.update_global_settings(global_settings)
    
    def get_encryption_settings(self) -> Dict[str, Any]:
        """Get encryption settings"""
        global_settings = self.get_global_settings()
        return global_settings.get("encryption", {
            "enabled": False,
            "password": None
        })
    
    def update_encryption_settings(self, enabled: bool = None, password: str = None):
        """Update encryption settings"""
        settings = self.get_encryption_settings()
        
        if enabled is not None:
            settings["enabled"] = enabled
        if password is not None:
            settings["password"] = password
        
        global_settings = self.get_global_settings()
        global_settings["encryption"] = settings
        self.update_global_settings(global_settings)
