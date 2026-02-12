"""
Config Sync Module
Handles automatic synchronization of config.json to S3
"""

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, cast


class ConfigSync:
    """
    Manages synchronization of config.json with S3 bucket
    Provides automatic upload on changes and download on startup
    """

    def __init__(self, storage_manager: Any, config_manager: Any) -> None:
        """
        Initialize ConfigSync

        Args:
            storage_manager: StorageManager instance
            config_manager: ConfigManager instance

        """
        self.storage_manager = storage_manager

        self.config_manager = config_manager
        self.config_backup_key = "config/config.json"
        self.config_metadata_key = "config/metadata.json"

    def get_config_target_id(self) -> Optional[int]:
        """
        Get the target ID configured for config sync

        Returns:
            Target ID or None if not configured
        """
        # We keep the old key 'config_sync_bucket_id' for backward compatibility
        # or we could migrate it. For now, just reading the same key.
        return cast(
            Optional[int], self.config_manager.config.get("config_sync_bucket_id")
        )

    def set_config_target(self, target_id: Optional[int]) -> None:
        """
        Set the target for config sync

        Args:
            target_id: Target ID or None to disable sync
        """
        self.config_manager.config["config_sync_bucket_id"] = target_id
        self.config_manager.save_config()

    def is_enabled(self) -> bool:
        """Check if config sync is enabled"""
        target_id = self.get_config_target_id()
        return target_id is not None

    def sync_to_storage(self, silent: bool = False) -> bool:
        """
        Upload current config.json to Storage

        Args:
            silent: If True, suppress output messages

        Returns:
            True if successful, False otherwise
        """
        target_id = self.get_config_target_id()
        if not target_id:
            return False

        try:
            storage = self.storage_manager.get_storage(target_id)
            if not storage:
                if not silent:
                    print("⚠️ Failed to get storage for config sync")
                return False

            # Get config file path
            from config import CONFIG_FILE

            config_path = str(CONFIG_FILE)

            if not os.path.exists(config_path):
                if not silent:
                    print("⚠️ Config file not found")
                return False

            # Create metadata
            metadata = {
                "sync_time": datetime.now().isoformat(),
                "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
                "version": "1.0",
            }

            # Upload config
            if storage.upload_file(config_path, self.config_backup_key, metadata):
                # Also upload metadata separately for easier access
                metadata_str = json.dumps(metadata, indent=2)
                temp_metadata = "/tmp/config_metadata.json"
                with open(temp_metadata, "w") as f:
                    f.write(metadata_str)
                storage.upload_file(temp_metadata, self.config_metadata_key)
                os.remove(temp_metadata)

                if not silent:
                    target_name = self.storage_manager.get_storage_name(target_id)
                    print(f"✅ Config synced to Storage ({target_name})")

                return True
            else:
                if not silent:
                    print("⚠️ Failed to upload config to storage provider")
                return False

        except Exception as e:
            if not silent:
                print(f"⚠️ Config sync failed: {e}")
            return False

    def sync_from_storage(self, force: bool = False, interactive: bool = True) -> bool:
        """
        Download config.json from Storage

        Args:
            force: If True, overwrite local config without checking timestamps
            interactive: If True, prompt user when local config is newer

        Returns:
            True if successful, False otherwise
        """
        target_id = self.get_config_target_id()
        if not target_id:
            return False

        try:
            storage = self.storage_manager.get_storage(target_id)
            if not storage:
                print("⚠️ Failed to get storage for config sync")
                return False

            # Check if config exists on remote
            remote_config_info = storage.get_file_info(self.config_backup_key)
            if not remote_config_info:
                print("ℹ️  No config found on remote storage")
                return False

            from config import CONFIG_FILE

            local_config_path = str(CONFIG_FILE)

            # Conflict resolution
            # Conflict resolution
            if os.path.exists(local_config_path) and not force:
                local_mtime = datetime.fromtimestamp(
                    os.path.getmtime(local_config_path)
                )
                remote_mtime = remote_config_info["last_modified"]

                # Make both timezone-aware or both naive for comparison
                if remote_mtime.tzinfo is not None:
                    remote_mtime = remote_mtime.replace(tzinfo=None)

                if local_mtime > remote_mtime:
                    print(
                        "ℹ️  Local config is newer "
                        f"(local: {local_mtime}, Remote: {remote_mtime})"
                    )
                    if not interactive:
                        print("   Skipping download in non-interactive mode")
                        return False
                    response = (
                        input("   Overwrite with remote version? (y/n): ")
                        .lower()
                        .strip()
                    )
                    if response != "y":
                        print("   Keeping local config")
                        return False

            # Backup local config before downloading
            if os.path.exists(local_config_path):
                backup_path = (
                    f"{local_config_path}.backup."
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                shutil.copy2(local_config_path, backup_path)
                print(f"📋 Local config backed up to: {backup_path}")

            # Download from remote
            if storage.download_file(self.config_backup_key, local_config_path):
                print("✅ Config downloaded from storage")

                # Reload config in memory
                self.config_manager.config = self.config_manager._load_config()
                return True
            else:
                print("⚠️ Failed to download config from storage")
                return False

        except Exception as e:
            print(f"⚠️ Config download failed: {e}")
            return False

    def get_storage_config_info(self) -> Optional[Dict[str, Any]]:
        """
        Get metadata about config stored on remote storage

        Returns:
            Dictionary with config info or None
        """
        target_id = self.get_config_target_id()
        if not target_id:
            return None

        try:
            storage = self.storage_manager.get_storage(target_id)
            if not storage:
                return None

            return cast(Dict[str, Any], storage.get_file_info(self.config_backup_key))

        except Exception:
            return None

    def auto_sync_on_startup(self) -> None:
        """
        Automatically sync from Storage on application startup if configured
        Only downloads if remote version is newer
        """
        if not self.is_enabled():
            return

        print("\n🔄 Checking for config updates from storage...")

        remote_info = self.get_storage_config_info()
        if not remote_info:
            print("ℹ️  No config found on storage")
            return

        from config import CONFIG_FILE

        local_config_path = str(CONFIG_FILE)

        if os.path.exists(local_config_path):
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_config_path))
            remote_mtime = remote_info["last_modified"]

            # Make both timezone-aware or both naive
            if remote_mtime.tzinfo is not None:
                remote_mtime = remote_mtime.replace(tzinfo=None)

            if remote_mtime > local_mtime:
                print("📥 Remote config is newer - downloading...")
                self.sync_from_storage(force=True)
            else:
                print("✅ Local config is up to date")
        else:
            # No local config, download from storage
            print("📥 Downloading config from storage...")
            self.sync_from_storage(force=True)
