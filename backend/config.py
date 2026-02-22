import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

# Allow override via env var, default to home dir
CONFIG_DIR = Path(os.getenv("DBMANAGER_DATA_DIR", Path.home() / ".dbmanager"))
CONFIG_FILE = CONFIG_DIR / "config.json"

# Sensitive fields that should be encrypted
SENSITIVE_FIELDS = [
    "password",
    "smtp_password",
    "aws_secret_access_key",
    "secret_key",
    "webhook_url",  # Often contains tokens
    "connection_string",
    "smb_password",
]


class ConfigManager:
    def __init__(self) -> None:
        self._ensure_config_exists()
        # Initialize security manager
        from core.security import SecurityManager

        self.security = SecurityManager(CONFIG_DIR / ".secret.key")
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        if not CONFIG_DIR.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            default_config: Dict[str, Any] = {
                "databases": [],
                "s3_buckets": [],
                "config_sync_bucket_id": None,
                "global_settings": {
                    "compression": {"enabled": False, "algorithm": "gzip", "level": 6},
                    "encryption": {"enabled": False, "password": None},
                },
                "notifications": {
                    "email": {
                        "enabled": False,
                        "smtp_host": "smtp.gmail.com",
                        "smtp_port": 587,
                        "smtp_username": "",
                        "smtp_password": "",
                        "from_email": "",
                        "to_emails": [],
                    },
                    "slack": {"enabled": False, "webhook_url": ""},
                    "teams": {"enabled": False, "webhook_url": ""},
                    "discord": {"enabled": False, "webhook_url": ""},
                },
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(default_config, f, indent=4)

    def _process_config(self, data: Any, encrypt: bool = True) -> Any:
        """Recursively encrypt or decrypt sensitive fields in config"""
        if isinstance(data, dict):
            new_data = {}
            for k, v in data.items():
                if k in SENSITIVE_FIELDS and isinstance(v, str) and v:
                    # Encrypt or decrypt
                    new_data[k] = (
                        self.security.encrypt(v)
                        if encrypt
                        else self.security.decrypt(v)
                    )
                else:
                    new_data[k] = self._process_config(v, encrypt)
            return new_data
        elif isinstance(data, list):
            return [self._process_config(item, encrypt) for item in data]
        else:
            return data

    def _load_config(self) -> Dict[str, Any]:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        # Decrypt loaded config so it's usable in memory
        processed = self._process_config(data, encrypt=False)
        return cast(Dict[str, Any], processed)

    def save_config(self) -> None:
        # Create a deep copy with encrypted values for saving
        encrypted_config = self._process_config(self.config, encrypt=True)

        with open(CONFIG_FILE, "w") as f:
            json.dump(encrypted_config, f, indent=4)

        # Auto-sync to Storage if enabled
        self._sync_to_storage()

    def _sync_to_storage(self) -> None:
        """Sync config to Storage if configured"""
        try:
            # Avoid circular import
            from core.config_sync import ConfigSync
            from core.storage_manager import StorageManager

            # Only sync if target is configured
            target_id = self.config.get("config_sync_bucket_id")
            if target_id:
                storage_manager = StorageManager(self)
                config_sync = ConfigSync(storage_manager, self)
                config_sync.sync_to_storage(silent=True)
        except Exception:
            # Silently fail to avoid breaking config saves
            pass

    def add_database(self, db_config: Dict[str, Any]) -> int:
        # Generate a simple ID if not present
        if "id" not in db_config:
            existing_ids = [db.get("id", 0) for db in self.config["databases"]]
            new_id = max(existing_ids) + 1 if existing_ids else 1
            db_config["id"] = new_id

        self.config["databases"].append(db_config)
        self.save_config()
        return int(db_config["id"])

    def get_databases(self) -> List[Dict[str, Any]]:
        return cast(List[Dict[str, Any]], self.config.get("databases", []))

    def get_database(self, db_id: int) -> Optional[Dict[str, Any]]:
        for db in self.config["databases"]:
            if db.get("id") == db_id:
                return cast(Dict[str, Any], db)
        return None

    def remove_database(self, db_id: int) -> None:
        self.config["databases"] = [
            db for db in self.config["databases"] if db.get("id") != db_id
        ]
        self.save_config()

    def update_database(self, db_id: int, new_config: Dict[str, Any]) -> bool:
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
        return cast(
            Dict[str, Any],
            self.config.get(
                "global_settings",
                {"compression": {"enabled": False, "algorithm": "gzip", "level": 6}},
            ),
        )

    def update_global_settings(self, settings: Dict[str, Any]) -> None:
        """Update global settings"""
        if "global_settings" not in self.config:
            self.config["global_settings"] = {}
        self.config["global_settings"].update(settings)
        self.save_config()

    def get_compression_settings(self) -> Dict[str, Any]:
        """Get compression settings"""
        global_settings = self.get_global_settings()
        return cast(
            Dict[str, Any],
            global_settings.get(
                "compression", {"enabled": False, "algorithm": "gzip", "level": 6}
            ),
        )

    def update_compression_settings(
        self,
        enabled: Optional[bool] = None,
        algorithm: Optional[str] = None,
        level: Optional[int] = None,
    ) -> None:
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
        return cast(
            Dict[str, Any],
            global_settings.get("encryption", {"enabled": False, "password": None}),
        )

    def update_encryption_settings(
        self, enabled: Optional[bool] = None, password: Optional[str] = None
    ) -> None:
        """Update encryption settings"""
        settings = self.get_encryption_settings()

        if enabled is not None:
            settings["enabled"] = enabled
        if password is not None:
            settings["password"] = password

        global_settings = self.get_global_settings()
        global_settings["encryption"] = settings
        self.update_global_settings(global_settings)

    def get_notification_settings(
        self, provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get notification settings for a specific provider or all"""
        notifications = cast(Dict[str, Any], self.config.get("notifications", {}))

        if provider:
            return cast(Dict[str, Any], notifications.get(provider, {}))

        return notifications

    def update_notification_settings(self, provider: str, **settings: Any) -> None:
        """Update notification settings for a provider"""
        if "notifications" not in self.config:
            self.config["notifications"] = {}

        if provider not in self.config["notifications"]:
            self.config["notifications"][provider] = {}

        self.config["notifications"][provider].update(settings)
        self.save_config()
