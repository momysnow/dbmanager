"""
Storage Migrator
Handles migration of backups between storage targets
"""

import os
import tempfile
from typing import Any, Callable, Dict, Optional


class StorageMigrator:
    """
    Manages migration of database backups between storage targets
    Preserves complete backup history during storage changes
    """

    def __init__(self, storage_manager: Any) -> None:
        """
        Initialize StorageMigrator

        Args:
            storage_manager: StorageManager instance
        """
        self.storage_manager = storage_manager

    def migrate_database_backups(
        self,
        db_id: int,
        old_storage_id: int,
        new_storage_id: int,
        delete_old: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> bool:
        """
        Migrate all backups for a database from old storage to new storage

        Args:
            db_id: Database ID
            old_storage_id: Source storage ID
            new_storage_id: Destination storage ID
            delete_old: If True, delete backups from old storage after migration
            progress_callback: Optional callback function(current, total, filename)

        Returns:
            True if migration successful, False otherwise
        """
        print(f"\n🔄 Starting backup migration for database {db_id}")
        print(f"   From: {self.storage_manager.get_storage_name(old_storage_id)}")
        print(f"   To:   {self.storage_manager.get_storage_name(new_storage_id)}")

        try:
            # Get storage instances
            old_storage = self.storage_manager.get_storage(old_storage_id)
            new_storage = self.storage_manager.get_storage(new_storage_id)

            if not old_storage or not new_storage:
                print("❌ Failed to initialize storage providers")
                return False

            # List all backups in old storage
            # Note: Prefix format might need adjustment for different providers
            # if they don't use folders.
            # But we assume standard path separator "/" for now
            prefix = f"backups/{db_id}/"
            backups = old_storage.list_files(prefix)

            if not backups:
                print("ℹ️  No backups found in old storage")
                return True

            total = len(backups)
            print(f"📦 Found {total} backup(s) to migrate")

            # Migrate each backup
            success_count = 0
            failed_files = []

            with tempfile.TemporaryDirectory() as temp_dir:
                for i, backup in enumerate(backups, 1):
                    remote_key = backup["key"]
                    filename = os.path.basename(remote_key)
                    temp_path = os.path.join(temp_dir, filename)

                    if progress_callback:
                        progress_callback(i, total, filename)
                    else:
                        print(f"  [{i}/{total}] Migrating {filename}...")

                    try:
                        # Download from old storage
                        if not old_storage.download_file(remote_key, temp_path):
                            failed_files.append(filename)
                            continue

                        # Upload to new storage
                        # We use the same key structure
                        if not new_storage.upload_file(
                            temp_path, remote_key, backup.get("metadata")
                        ):
                            failed_files.append(filename)
                            continue

                        success_count += 1

                        # Delete from old storage if requested
                        if delete_old:
                            old_storage.delete_file(remote_key)

                        # Cleanup temp file
                        try:
                            # Safely remove temp file
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except Exception:
                            pass

                    except Exception as e:
                        print(f"  ⚠️  Error migrating {filename}: {e}")
                        failed_files.append(filename)

            # Summary
            print(f"\n✅ Migration complete: {success_count}/{total} successful")
            if failed_files:
                print(f"⚠️  Failed files: {', '.join(failed_files)}")
                return False

            return True

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False

    def estimate_migration_size(
        self, db_id: int, storage_id: int
    ) -> Dict[str, float | int]:
        """
        Estimate size and count of backups to migrate

        Args:
            db_id: Database ID
            storage_id: Storage ID

        Returns:
            Dictionary with count and total size in bytes
        """
        try:
            storage = self.storage_manager.get_storage(storage_id)
            if not storage:
                return {"count": 0, "size_bytes": 0, "size_mb": 0}

            prefix = f"backups/{db_id}/"
            backups = storage.list_files(prefix)

            total_size = sum(b["size"] for b in backups)

            return {
                "count": len(backups),
                "size_bytes": total_size,
                "size_mb": round(total_size / (1024 * 1024), 2),
            }
        except Exception as e:
            print(f"⚠️ Failed to estimate migration size: {e}")
            return {"count": 0, "size_bytes": 0, "size_mb": 0}
