"""
Storage Manager
Handles storage configuration CRUD operations and provider instantiation
"""

from typing import Any, Dict, List, Optional, cast
from core.storage_provider import StorageProvider
from core.s3_storage import S3Storage


class StorageManager:
    """
    Manages storage configurations (S3, SMB, etc.)
    Provides CRUD operations for storage configs and factory for providers
    """

    def __init__(self, config_manager: Any) -> None:
        """
        Initialize StorageManager

        Args:
            config_manager: ConfigManager instance
        """
        self.config_manager = config_manager
        self._ensure_storage_config()

    def _ensure_storage_config(self) -> None:
        """Ensure storage configuration exists and migrate legacy S3 config"""
        if "storage_targets" not in self.config_manager.config:
            self.config_manager.config["storage_targets"] = []

        # Migration: Move s3_buckets to storage_targets if exists
        if "s3_buckets" in self.config_manager.config:
            s3_buckets = self.config_manager.config.pop("s3_buckets")
            if s3_buckets and not self.config_manager.config["storage_targets"]:
                print("🔄 Migrating legacy S3 buckets to storage targets...")
                self.config_manager.config["storage_targets"] = s3_buckets
                self.config_manager.save_config()

    def list_storage(self) -> List[Dict[str, Any]]:
        """
        Get list of configured storage targets

        Returns:
            List of storage configuration dictionaries
        """
        return cast(
            List[Dict[str, Any]], self.config_manager.config.get("storage_targets", [])
        )

    def get_storage_config(self, storage_id: int) -> Optional[Dict[str, Any]]:
        """
        Get storage configuration by ID

        Args:
            storage_id: Storage ID

        Returns:
            Storage config dict or None if not found
        """
        for target in self.list_storage():
            if target.get("id") == storage_id:
                return target
        return None

    def add_storage(self, storage_config: Dict) -> int:
        """
        Add new storage configuration

        Args:
            storage_config: Dictionary with storage configuration

        Returns:
            New storage ID
        """
        # Ensure key exists
        if "storage_targets" not in self.config_manager.config:
            self.config_manager.config["storage_targets"] = []

        # Generate ID
        existing_ids = [s.get("id", 0) for s in self.list_storage()]
        new_id: int = max(existing_ids) + 1 if existing_ids else 1
        storage_config["id"] = new_id

        # Add to config
        self.config_manager.config["storage_targets"].append(storage_config)
        self.config_manager.save_config()

        return new_id

    def update_storage(self, storage_id: int, new_config: Dict) -> bool:
        """
        Update existing storage configuration

        Args:
            storage_id: Storage ID to update
            new_config: New configuration dictionary

        Returns:
            True if successful, False if storage not found
        """
        if "storage_targets" not in self.config_manager.config:
            return False

        for i, target in enumerate(self.config_manager.config["storage_targets"]):
            if target.get("id") == storage_id:
                # Preserve ID
                new_config["id"] = storage_id
                self.config_manager.config["storage_targets"][i] = new_config
                self.config_manager.save_config()
                return True

        return False

    def delete_storage(self, storage_id: int) -> bool:
        """
        Delete storage configuration

        Args:
            storage_id: Storage ID to delete

        Returns:
            True if successful, False if storage not found or in use
        """
        # Check if storage is in use by any database
        for db in self.config_manager.get_databases():
            # Support both old key s3_bucket_id and new key storage_id if we want
            # But let's assume we might migrate db configs too?
            # For now, let's just check s3_bucket_id (mapping to storage_id)
            if db.get("s3_bucket_id") == storage_id:
                print(
                    f"❌ Cannot delete storage: in use by database '{db.get('name')}'"
                )
                return False

        # Check if storage is used for config sync
        if self.config_manager.config.get("config_sync_bucket_id") == storage_id:
            print("❌ Cannot delete storage: used for config sync")
            return False

        # Remove storage
        if "storage_targets" in self.config_manager.config:
            original_count = len(self.config_manager.config["storage_targets"])
            self.config_manager.config["storage_targets"] = [
                s
                for s in self.config_manager.config["storage_targets"]
                if s.get("id") != storage_id
            ]

            if len(self.config_manager.config["storage_targets"]) < original_count:
                self.config_manager.save_config()
                return True

        return False

    def test_storage(self, storage_id: int) -> bool:
        """
        Test connection to storage target

        Args:
            storage_id: Storage ID to test

        Returns:
            True if connection successful, False otherwise
        """
        storage = self.get_storage(storage_id)
        if not storage:
            print(f"❌ Storage ID {storage_id} not found or failed to initialize")
            return False

        try:
            return storage.test_connection()
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

    def get_storage(self, storage_id: int) -> Optional[StorageProvider]:
        """
        Get StorageProvider instance for target

        Args:
            storage_id: Storage ID

        Returns:
            StorageProvider instance or None if not found
        """
        config = self.get_storage_config(storage_id)
        if not config:
            return None

        provider_type = config.get("provider", "s3")

        try:
            if provider_type == "s3" or provider_type in ("minio", "garage", "other"):
                return S3Storage(config)
            elif provider_type == "smb":
                try:
                    # Lazy import to avoid circular dependencies
                    # or crashes if lib missing
                    from core.smb_storage import SMBStorage

                    return SMBStorage(config)
                except ImportError:
                    print("⚠️  SMB support not available. Install smbprotocol.")
                    return None
            else:
                print(f"❌ Unknown storage provider: {provider_type}")
                return None
        except Exception as e:
            print(f"❌ Failed to create storage provider: {e}")
            return None

    def get_storage_name(self, storage_id: int) -> Optional[str]:
        """
        Get display name of storage target

        Args:
            storage_id: Storage ID

        Returns:
            Display name or None
        """
        config = self.get_storage_config(storage_id)
        return config.get("name") if config else None
