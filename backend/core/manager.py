import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from config import ConfigManager, CONFIG_DIR
from .providers.base import BaseProvider
from .providers.postgres import PostgresProvider
from .providers.mysql import MySQLProvider
from .providers.sqlserver import SQLServerProvider
from .providers.mongodb import MongoDBProvider
from .providers.mariadb import MariaDBProvider
from .storage_manager import StorageManager
from .backup_utils import save_checksum, verify_backup, verify_checksum

from .compression import compress_file
from .encryption import encrypt_file
from .notifications import NotificationManager
from .progress import ProgressStatus

if TYPE_CHECKING:
    from .progress import BackupProgress


BACKUP_ROOT = CONFIG_DIR / "backups"


class DBManager:
    def __init__(self) -> None:
        self.config_manager = ConfigManager()
        self.storage_manager = StorageManager(self.config_manager)
        self.notification_manager = NotificationManager(self.config_manager.config)

        # Initialize config sync
        from .config_sync import ConfigSync

        self.config_sync = ConfigSync(self.storage_manager, self.config_manager)

        # Auto-sync config from S3 on startup if enabled
        self.config_sync.auto_sync_on_startup()

        self.provider_map: Dict[str, Type[BaseProvider]] = {
            "postgres": PostgresProvider,
            "mysql": MySQLProvider,
            "mariadb": MariaDBProvider,
            "sqlserver": SQLServerProvider,
            "mongodb": MongoDBProvider,
        }

    def get_supported_providers(self) -> List[str]:
        return list(self.provider_map.keys())

    def add_database(
        self, name: str, provider_type: str, connection_params: Dict[str, Any]
    ) -> int:
        if provider_type not in self.provider_map:
            raise ValueError(f"Provider {provider_type} not supported.")

        db_config = {
            "name": name,
            "provider": provider_type,
            "params": connection_params,
        }
        return self.config_manager.add_database(db_config)

    def list_databases(self) -> List[Dict[str, Any]]:
        return self.config_manager.get_databases()

    def get_provider_instance(self, db_id: int) -> BaseProvider:
        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database with ID {db_id} not found.")

        provider_type = db_config["provider"]
        provider_class = self.provider_map.get(provider_type)
        if not provider_class:
            raise ValueError(f"Provider {provider_type} implementation not found.")

        return provider_class(db_config)

    def delete_database(self, db_id: int) -> None:
        self.config_manager.remove_database(db_id)

    def update_database(
        self,
        db_id: int,
        name: str,
        provider_type: str,
        connection_params: Dict[str, Any],
        retention: int = 0,
        s3_enabled: bool = False,
        s3_bucket_id: Optional[int] = None,
        s3_retention: int = 0,
    ) -> bool:
        """
        Update database configuration

        Args:
            db_id: Database ID
            name: Database name
            provider_type: Provider type ('postgres', 'mysql', 'sqlserver')
            connection_params: Connection parameters dict
            retention: Local retention policy (number of backups to keep)
            s3_enabled: Enable S3 backups
            s3_bucket_id: S3 bucket ID to use
            s3_retention: S3 retention policy (number of backups to keep on S3)

        Returns:
            True if successful
        """
        if provider_type not in self.provider_map:
            raise ValueError(f"Provider {provider_type} not supported.")

        # Get current config to check for bucket change
        current_config = self.config_manager.get_database(db_id)
        old_bucket_id = current_config.get("s3_bucket_id") if current_config else None

        # Prepare new config
        db_config = {
            "name": name,
            "provider": provider_type,
            "params": connection_params,
            "retention": retention,
            "s3_enabled": s3_enabled,
            "s3_bucket_id": s3_bucket_id,
            "s3_retention": s3_retention,
        }

        # Check if S3 bucket changed
        bucket_changed = (
            old_bucket_id != s3_bucket_id
            and old_bucket_id is not None
            and s3_bucket_id is not None
            and s3_enabled
        )

        # Update config
        result = self.config_manager.update_database(db_id, db_config)

        # Trigger storage migration if needed
        if bucket_changed and result:
            assert old_bucket_id is not None
            assert s3_bucket_id is not None
            print("\n⚠️  Storage target changed - migration required")
            from .storage_migrator import StorageMigrator

            migrator = StorageMigrator(self.storage_manager)

            # Ask user for confirmation
            print(
                f"   Old storage: "
                f"{self.storage_manager.get_storage_name(old_bucket_id)}"
            )
            print(
                f"   New storage: {self.storage_manager.get_storage_name(s3_bucket_id)}"
            )

            # Estimate migration size
            estimate = migrator.estimate_migration_size(db_id, old_bucket_id)
            print(
                f"   Backups to migrate: {estimate['count']} ({estimate['size_mb']} MB)"
            )

            response = input("\n   Migrate backups now? (y/n): ").lower().strip()
            if response == "y":
                # Ask about cleanup
                delete_response = (
                    input("   Delete backups from old bucket after migration? (y/n): ")
                    .lower()
                    .strip()
                )
                delete_old = delete_response == "y"

                migrator.migrate_database_backups(
                    db_id, old_bucket_id, s3_bucket_id, delete_old=delete_old
                )

                if delete_old:
                    print("   ✅ Migration complete - old backups deleted")
                else:
                    print("   ✅ Migration complete - old backups preserved")
            else:
                print("   ⚠️  Migration skipped - backups remain in old bucket")

        return result

    def _get_backup_dir(self, db_id: int) -> Path:
        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found")

        # Folder name: id_name (sanitized)
        safe_name = "".join(
            [c for c in db_config["name"] if c.isalnum() or c in ("-", "_")]
        )
        return BACKUP_ROOT / f"{db_id}_{safe_name}"

    def backup_database(
        self,
        db_id: int,
        tag: Optional[str] = None,
        progress: Optional["BackupProgress"] = None,
    ) -> str:
        db_config = self.config_manager.get_database(db_id)
        if db_config is None:
            raise ValueError(f"Database {db_id} not found")
        provider = self.get_provider_instance(db_id)
        backup_dir = self._get_backup_dir(db_id)

        if progress and progress.status == ProgressStatus.IDLE:
            progress.start(f"Starting backup for {db_config.get('name', db_id)}")

        # Get options
        retention = int(db_config.get("retention", 0))  # 0 = infinite (local)
        s3_retention = int(db_config.get("s3_retention", 0))  # 0 = infinite (S3)

        try:
            # Run local backup with progress tracking
            path = provider.backup(str(backup_dir), progress=progress)
        except Exception as e:
            if progress:
                progress.fail(str(e))
            raise

        # Apply Tag if requested (Rename file)
        if tag:
            try:
                directory = os.path.dirname(path)
                filename = os.path.basename(path)
                # Inject tag before extension
                name_part, ext = os.path.splitext(filename)
                # Handle .dump.gz or similar if provider adds it.
                if filename.endswith(".tar.gz"):
                    name_part = filename[:-7]
                    ext = ".tar.gz"
                elif filename.endswith(".gz"):
                    name_part, ext = os.path.splitext(filename[:-3])
                    ext = ext + ".gz"

                new_filename = f"{name_part}_{tag}{ext}"
                new_path = os.path.join(directory, new_filename)
                os.rename(path, new_path)
                path = new_path
                print(f"🏷️  Tagged backup: {new_filename}")
            except Exception as e:
                print(f"⚠️  Failed to tag backup: {e}")

        # Generate checksum for backup integrity
        try:
            checksum_file = save_checksum(path)
            print(f"✅ Checksum generated: {os.path.basename(checksum_file)}")
        except Exception as e:
            print(f"⚠️  Checksum generation failed: {e}")
            checksum_file = None

        # Compress backup if enabled
        compression_settings = self.config_manager.get_compression_settings()
        if compression_settings.get("enabled", False):
            try:
                algorithm = compression_settings.get("algorithm", "gzip")
                level = compression_settings.get("level", 6)

                print(f"🗜️  Compressing with {algorithm} (level {level})...")
                original_size = os.path.getsize(path)
                compressed_path = compress_file(
                    path, algorithm=algorithm, level=level, remove_original=True
                )

                # Update path to compressed file
                path = compressed_path

                # Update checksum file reference
                if checksum_file:
                    try:
                        Path(checksum_file).unlink(missing_ok=True)
                    except Exception:
                        pass
                    checksum_file = save_checksum(compressed_path)

                if original_size:
                    ratio = os.path.getsize(compressed_path) / original_size
                    print(
                        f"✅ Compressed: {os.path.basename(compressed_path)} "
                        f"({ratio:.2%} of original)"
                    )
                else:
                    print(f"✅ Compressed: {os.path.basename(compressed_path)}")
            except Exception as e:
                print(f"⚠️  Compression failed: {e}, using uncompressed backup")

        # Encrypt backup if enabled
        encryption_settings = self.config_manager.get_encryption_settings()
        if encryption_settings.get("enabled", False):
            password = encryption_settings.get("password")
            if not password:
                print(
                    "⚠️  Encryption enabled but no password set, " "skipping encryption"
                )
            else:
                try:
                    print("🔐 Encrypting backup...")
                    encrypted_path = encrypt_file(path, password, remove_original=True)

                    # Update path to encrypted file
                    path = encrypted_path

                    # Update checksum file reference
                    if checksum_file:
                        # Rename checksum file to match encrypted file
                        old_checksum = checksum_file
                        checksum_file = f"{encrypted_path}.sha256"
                        try:
                            os.rename(old_checksum, checksum_file)
                        except Exception:
                            # If rename fails, regenerate checksum for encrypted file
                            checksum_file = save_checksum(encrypted_path)

                    print(f"✅ Encrypted: {os.path.basename(encrypted_path)}")
                except Exception as e:
                    print(f"⚠️  Encryption failed: {e}, using unencrypted backup")

        # Upload to Storage targets (supports multiple)
        # New field: storage_target_ids (list of ints)
        # Legacy field: s3_bucket_id (single int) + s3_enabled
        target_ids: list = db_config.get("storage_target_ids", [])
        if (
            not target_ids
            and db_config.get("s3_enabled")
            and db_config.get("s3_bucket_id")
        ):
            target_ids = [db_config["s3_bucket_id"]]

        s3_retention = int(db_config.get("s3_retention", 0))

        for target_id in target_ids:
            try:
                storage = self.storage_manager.get_storage(int(target_id))
                if not storage:
                    print(f"⚠️  Storage target {target_id} not found, skipping")
                    continue

                target_name = self.storage_manager.get_storage_name(
                    int(target_id)
                ) or str(target_id)
                filename = os.path.basename(path)
                remote_key = f"backups/{db_id}/{filename}"

                # Calculate checksum hash
                current_hash = None
                if checksum_file:
                    try:
                        with open(checksum_file, "r") as f:
                            current_hash = f.read().strip()
                    except Exception:
                        pass

                # Metadata
                metadata = {
                    "database_id": str(db_id),
                    "database_name": db_config.get("name", ""),
                    "provider": db_config.get("provider", ""),
                    "backup_date": datetime.now().isoformat(),
                    "tag": tag if tag else "",
                    "hash": current_hash if current_hash else "",
                }

                if storage.upload_file(path, remote_key, metadata):
                    print(f"✅ Uploaded to [{target_name}]: {remote_key}")

                    # Upload checksum too
                    if checksum_file and Path(checksum_file).exists():
                        storage.upload_file(checksum_file, f"{remote_key}.sha256")
                else:
                    print(f"⚠️  Upload to [{target_name}] failed")
            except Exception as e:
                print(f"⚠️  Upload to storage {target_id} error: {e}")

        # Handle local retention
        if retention > 0:
            self._enforce_retention(db_id, retention)

        # Handle remote retention on each target
        if s3_retention > 0:
            for target_id in target_ids:
                self._enforce_s3_retention(db_id, int(target_id), s3_retention)

        if progress and progress.status not in (
            ProgressStatus.COMPLETED,
            ProgressStatus.FAILED,
        ):
            progress.complete(f"Backup completed: {os.path.basename(path)}")

        return path

    def _enforce_retention(self, db_id: int, keep_last: int) -> None:
        backups = self.list_backups(db_id)  # already sorted desc
        if len(backups) > keep_last:
            to_delete = backups[keep_last:]
            for b in to_delete:
                try:
                    Path(b["path"]).unlink()
                    checksum_path = Path(f"{b['path']}.sha256")
                    checksum_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _enforce_s3_retention(self, db_id: int, bucket_id: int, keep_last: int) -> None:
        """
        Enforce retention policy on S3 backups

        Args:
            db_id: Database ID
            bucket_id: S3 bucket ID
            keep_last: Number of backups to keep
        """
        try:
            storage = self.storage_manager.get_storage(bucket_id)
            if not storage:
                return

            # List all backups for this database in S3
            prefix = f"backups/{db_id}/"
            s3_backups = storage.list_files(prefix)

            # Sort by last_modified descending
            s3_backups = sorted(
                s3_backups, key=lambda x: x["last_modified"], reverse=True
            )

            # Delete old backups
            if len(s3_backups) > keep_last:
                to_delete = s3_backups[keep_last:]
                for backup in to_delete:
                    try:
                        storage.delete_file(backup["key"])
                        storage.delete_file(f"{backup['key']}.sha256")
                        print(f"🗑️ Deleted old S3 backup: {backup['key']}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete S3 backup {backup['key']}: {e}")
        except Exception as e:
            print(f"⚠️ S3 retention cleanup failed: {e}")

    def list_backups(self, db_id: int) -> List[Dict[str, Any]]:
        backups = []

        # 1. LOCAL BACKUPS
        backup_dir = self._get_backup_dir(db_id)
        if backup_dir.exists():
            # Support multiple backup formats (including compressed/encrypted variants)
            for pattern in [
                "*.sql",
                "*.dump",
                "*.bak",
                "*.tar.gz",
                "*.gz",
                "*.enc",
                "*.zst",
                "*.lz4",
            ]:
                for f in backup_dir.glob(pattern):
                    # Skip checksum files
                    if f.name.endswith(".sha256"):
                        continue

                    try:
                        stat = f.stat()
                        backups.append(
                            {
                                "filename": f.name,
                                "path": str(f),
                                "date": datetime.fromtimestamp(
                                    stat.st_mtime, tz=timezone.utc
                                ),
                                "size_mb": stat.st_size / (1024 * 1024),
                                "location": "local",
                                "has_checksum": Path(f"{f}.sha256").exists(),
                            }
                        )
                    except Exception as e:
                        print(f"Error reading local backup {f}: {e}")

        # 2. S3 BACKUPS
        try:
            db_config = self.config_manager.get_database(db_id)
            if (
                db_config
                and db_config.get("s3_enabled")
                and db_config.get("s3_bucket_id")
            ):
                bucket_id_value = db_config.get("s3_bucket_id")
                if bucket_id_value is None:
                    raise ValueError("Storage ID missing from configuration")
                storage = self.storage_manager.get_storage(int(bucket_id_value))
                if storage:
                    prefix = f"backups/{db_id}/"
                    s3_files = storage.list_files(prefix)

                    for s3_file in s3_files:
                        key = s3_file["key"]
                        # Skip checksum files
                        if key.endswith(".sha256"):
                            continue

                        # Check metadata for hash
                        # s3_file usually contains: key, size, last_modified, etag.
                        # list_files may not include metadata; head calls are expensive.

                        # Check if a .sha256 sibling exists in the list?
                        # It's expensive to search list for every item.
                        # Assume integrity if it's in S3 and we uploaded it.
                        # Or check if key + .sha256 is in the s3_files list logic?
                        has_checksum = any(
                            f["key"] == f"{key}.sha256" for f in s3_files
                        )

                        backups.append(
                            {
                                "filename": os.path.basename(key),
                                "path": key,  # S3 Key
                                "date": s3_file["last_modified"],  # Should be datetime
                                "size_mb": s3_file["size"] / (1024 * 1024),
                                "location": "s3",
                                "has_checksum": has_checksum,
                            }
                        )
        except Exception as e:
            print(f"Error listing S3 backups: {e}")

        # Sort by date desc
        return sorted(backups, key=lambda x: x["date"], reverse=True)

    def verify_backup_integrity(
        self,
        backup_path: str,
        location: str = "local",
        db_id: Optional[int] = None,
    ) -> bool:
        """
        Verify backup integrity using checksum.

        Args:
            backup_path: Path to backup file (or S3 key)
            location: 'local' or 's3'
            db_id: Database ID (required for S3 to find bucket)

        Returns:
            True if valid
        """
        import tempfile
        import shutil
        from .encryption import decrypt_file
        from .backup_utils import calculate_checksum

        if location == "local":
            # For encrypted files, we need to decrypt first before verifying checksum
            # because the .sha256 file contains the checksum of the compressed file, not the encrypted one
            filename = os.path.basename(backup_path)

            if filename.endswith(".enc"):
                # Read expected checksum from .sha256 file
                checksum_file_path = f"{backup_path}.sha256"
                if not os.path.exists(checksum_file_path):
                    raise FileNotFoundError(
                        f"Checksum file not found: {checksum_file_path}"
                    )

                try:
                    with open(checksum_file_path, "r") as f:
                        line = f.read().strip()
                        parts = line.split()
                        if len(parts) < 2:
                            raise ValueError("Invalid checksum file format")
                        expected_hash = parts[0]
                except Exception as e:
                    raise RuntimeError(f"Could not read checksum file: {e}")

                # Get encryption password
                encryption_settings = self.config_manager.get_encryption_settings()
                password = encryption_settings.get("password")
                if not password:
                    raise RuntimeError(
                        "Backup is encrypted but no encryption password is configured. "
                        "Set the encryption password in Settings → Encryption."
                    )

                # Decrypt to temp directory and verify checksum
                temp_dir = tempfile.mkdtemp()
                try:
                    temp_file = os.path.join(temp_dir, filename)
                    shutil.copy2(backup_path, temp_file)
                    decrypted_file = decrypt_file(
                        temp_file, password, remove_encrypted=True
                    )

                    # Calculate checksum on decrypted file
                    actual_hash = calculate_checksum(decrypted_file)

                    # Cleanup
                    shutil.rmtree(temp_dir, ignore_errors=True)

                    if actual_hash == expected_hash:
                        return True
                    else:
                        raise ValueError(
                            f"Checksum mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
                        )
                except Exception as e:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise RuntimeError(f"Integrity verification failed: {e}")
            else:
                # Non-encrypted file - verify directly
                result = verify_backup(backup_path)
                return bool(result.get("valid"))
        elif location == "s3":
            if not db_id:
                raise ValueError("db_id required for S3 verification")

            db_config = self.config_manager.get_database(db_id)
            if not db_config or not db_config.get("s3_bucket_id"):
                raise ValueError("S3 not configured for this database")

            bucket_id_value = db_config.get("s3_bucket_id")
            if bucket_id_value is None:
                raise ValueError("Storage ID missing from configuration")
            storage = self.storage_manager.get_storage(int(bucket_id_value))
            if not storage:
                raise ValueError("Bucket storage not found")

            info = storage.get_file_info(backup_path)
            if not info:
                raise FileNotFoundError(f"S3 file {backup_path} not found")

            from tempfile import TemporaryDirectory
            from pathlib import Path

            checksum_key = f"{backup_path}.sha256"
            with TemporaryDirectory() as temp_dir:
                local_file = str(Path(temp_dir) / Path(backup_path).name)
                local_checksum = f"{local_file}.sha256"

                if not storage.download_file(backup_path, local_file):
                    raise RuntimeError("Failed to download S3 backup for verification")

                if storage.get_file_info(checksum_key):
                    storage.download_file(checksum_key, local_checksum)
                    result = verify_backup(local_file)
                    return bool(result.get("valid"))

                # If no checksum, use metadata hash if present
                stored_hash = info.get("metadata", {}).get("hash")
                if stored_hash:
                    return bool(verify_checksum(local_file, expected_hash=stored_hash))

                # No checksum available
                raise FileNotFoundError("S3 checksum not found")
        return False

    def restore_database(
        self,
        db_id: int,
        backup_file: str,
        progress: Optional["BackupProgress"] = None,
        create_safety_snapshot: bool = True,
    ) -> bool:
        import tempfile
        import shutil
        from .encryption import decrypt_file
        from .compression import decompress_file

        provider = self.get_provider_instance(db_id)
        # Verify file exists
        if not Path(backup_file).exists():
            raise FileNotFoundError(f"Backup file {backup_file} not found")

        # Check if checksum file exists (for later verification after decrypt)
        checksum_file = Path(f"{backup_file}.sha256")
        has_checksum = checksum_file.exists()

        # Read expected checksum from file if available
        expected_hash = None
        expected_filename = None
        if has_checksum:
            try:
                with open(checksum_file, "r") as f:
                    line = f.read().strip()
                    parts = line.split()
                    if len(parts) >= 2:
                        expected_hash = parts[0]
                        expected_filename = parts[1]
            except Exception as e:
                print(f"⚠️  Could not read checksum file: {e}")

        # SAFETY SNAPSHOT
        safety_snapshot_path = None
        if create_safety_snapshot:
            print("📸 Creating safety snapshot before restore...")
            if progress:
                progress.update(
                    message="Creating safety snapshot...", step="Safety Snapshot"
                )
            try:
                # Use a special tag and avoid progress updates to keep UI clean.
                safety_snapshot_path = self.backup_database(
                    db_id, tag="safety_snapshot"
                )
                print(
                    "✅ Safety snapshot created: "
                    f"{os.path.basename(safety_snapshot_path)}"
                )
            except Exception as e:
                print(f"⚠️  Failed to create safety snapshot: {e}")
                # We should probably abort restore if safety snapshot fails, to be safe.
                raise RuntimeError(
                    f"Restore aborted: Could not create safety snapshot ({e})"
                )

        # DECRYPT + DECOMPRESS if needed before restore
        # Work in a temp dir so we don't modify the original backup
        temp_dir_obj = None
        actual_restore_file = backup_file
        decrypted_file = None  # Track decrypted file for checksum verification

        try:
            filename = os.path.basename(backup_file)
            needs_decrypt = filename.endswith(".enc")
            needs_decompress = (
                ".gz" in filename or ".zst" in filename or ".lz4" in filename
            ) and not filename.endswith(".enc")
            # Handle chained: .dump.gz.enc → decrypt → .dump.gz → decompress → .dump
            if (
                needs_decrypt
                or needs_decompress
                or ".enc" in filename
                or ".gz" in filename
            ):
                temp_dir_obj = tempfile.mkdtemp()
                work_file = os.path.join(temp_dir_obj, filename)
                shutil.copy2(backup_file, work_file)

                # Step 1: Decrypt if encrypted
                if work_file.endswith(".enc"):
                    if progress:
                        progress.update(
                            message="Decrypting backup...", step="Decrypting"
                        )
                    encryption_settings = self.config_manager.get_encryption_settings()
                    password = encryption_settings.get("password")
                    if not password:
                        raise RuntimeError(
                            "Backup is encrypted but no encryption password is configured. "
                            "Set the encryption password in Settings → Encryption."
                        )
                    work_file = decrypt_file(work_file, password, remove_encrypted=True)
                    decrypted_file = work_file  # Save for checksum verification
                    print(f"🔓 Decrypted: {os.path.basename(work_file)}")

                # VERIFY CHECKSUM after decrypt (checksum is for compressed file, not encrypted)
                if has_checksum and expected_hash and decrypted_file:
                    print("🔍 Verifying backup integrity...")
                    if progress:
                        progress.update(
                            message="Verifying backup integrity...", step="Checksum"
                        )
                    try:
                        # Verify checksum on the decrypted (compressed) file
                        from .backup_utils import calculate_checksum

                        actual_hash = calculate_checksum(decrypted_file)
                        if actual_hash == expected_hash:
                            print("✅ Checksum verified - backup is intact")
                        else:
                            raise ValueError(
                                f"Checksum mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
                            )
                    except Exception as e:
                        print(f"⚠️  Checksum verification failed: {e}")
                        raise RuntimeError(
                            f"Restore aborted: Checksum verification failed ({e})"
                        )

                # Step 2: Decompress if compressed
                compressed_exts = (".gz", ".zst", ".lz4")
                if any(work_file.endswith(ext) for ext in compressed_exts):
                    if progress:
                        progress.update(
                            message="Decompressing backup...", step="Decompressing"
                        )
                    work_file = decompress_file(work_file, remove_compressed=True)
                    print(f"📦 Decompressed: {os.path.basename(work_file)}")

                actual_restore_file = work_file
            else:
                # No encryption/compression - verify checksum directly
                if has_checksum:
                    print("🔍 Verifying backup integrity...")
                    if progress:
                        progress.update(
                            message="Verifying backup integrity...", step="Checksum"
                        )
                    try:
                        if verify_checksum(backup_file):
                            print("✅ Checksum verified - backup is intact")
                        else:
                            raise ValueError(
                                "Checksum verification failed - backup may be corrupted"
                            )
                    except Exception as e:
                        print(f"⚠️  Checksum verification failed: {e}")
                        raise RuntimeError(
                            f"Restore aborted: Checksum verification failed ({e})"
                        )
        except Exception as prep_err:
            if temp_dir_obj:
                shutil.rmtree(temp_dir_obj, ignore_errors=True)
            raise RuntimeError(f"Failed to prepare backup for restore: {prep_err}")

        # PERFORM RESTORE
        try:
            result = provider.restore(actual_restore_file, progress=progress)

            # Cleanup temp dir
            if temp_dir_obj:
                import shutil as _shutil

                _shutil.rmtree(temp_dir_obj, ignore_errors=True)

            # If we got here, success. We can keep the safety snapshot.
            # Keeping it is safer (can be deleted by retention later).
            return result

        except Exception as e:
            # Cleanup temp dir on failure too
            if temp_dir_obj:
                import shutil as _shutil

                _shutil.rmtree(temp_dir_obj, ignore_errors=True)

            print(f"❌ RESTORE FAILED: {e}")
            if progress:
                progress.fail(f"Restore failed: {e}")

            # ROLLBACK LOGIC
            if safety_snapshot_path and os.path.exists(safety_snapshot_path):
                print("🔄 Attempting ROLLBACK to safety snapshot...")
                if progress:
                    progress.update(
                        message="Restoring from safety snapshot...", step="Rolling Back"
                    )
                    # Reset progress for rollback? Or just update message.

                try:
                    # Recursive call with create_safety_snapshot=False to avoid loop.
                    self.restore_database(
                        db_id, safety_snapshot_path, create_safety_snapshot=False
                    )
                    msg = (
                        "Restore failed, but database was successfully rolled back "
                        "to previous state."
                    )
                    print(f"✅ {msg}")
                    # Re-raise original error but with rollback info
                    raise RuntimeError(f"Restore failed: {e}. ROLLBACK SUCCESSFUL.")
                except Exception as rollback_error:
                    msg = (
                        "CRITICAL: Restore failed AND Rollback failed! "
                        "Database may be in inconsistent state. "
                        f"({rollback_error})"
                    )
                    print(f"⛔️ {msg}")
                    raise RuntimeError(msg)
            else:
                raise RuntimeError(
                    f"Restore failed: {e}. No safety snapshot available for rollback."
                )

    def backup_all_databases(self, max_workers: int = 2) -> Dict[str, Any]:
        """
        Backup all configured databases, potentially in parallel.

        Args:
            max_workers: Number of concurrent backup jobs. Default 2.

        Returns:
            Dictionary with results: {'success': [], 'failed': []}
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        databases = self.list_databases()
        if not databases:
            print("No databases configured.")
            return {"success": [], "failed": []}

        print(
            f"🚀 Starting backup for {len(databases)} databases "
            f"(Parallel: {max_workers})..."
        )

        results: Dict[str, List[Dict[str, Any]]] = {"success": [], "failed": []}

        # Helper function for thread
        def _job(db_config: Dict[str, Any]) -> Dict[str, Any]:
            db_id = db_config["id"]
            name = db_config["name"]
            try:
                # Avoid progress tracker in batch jobs to prevent stdout collisions.
                path = self.backup_database(db_id)
                return {"id": db_id, "name": name, "status": "success", "path": path}
            except Exception as e:
                return {"id": db_id, "name": name, "status": "error", "error": str(e)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_db = {executor.submit(_job, db): db for db in databases}

            for future in as_completed(future_to_db):
                db = future_to_db[future]
                try:
                    res = future.result()
                    if res["status"] == "success":
                        print(f"✅ [{res['name']}] Backup completed.")
                        results["success"].append(res)
                    else:
                        print(f"❌ [{res['name']}] Backup failed: {res['error']}")
                        results["failed"].append(res)
                except Exception as exc:
                    print(f"❌ [{db['name']}] Thread exception: {exc}")
                    results["failed"].append(
                        {"id": db["id"], "name": db["name"], "error": str(exc)}
                    )

        return results

    def execute_query(
        self, db_id: int, query: str, limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute a SELECT query on a database and return results.

        Args:
            db_id: Database ID
            query: SQL query
            limit: Maximum rows to return

        Returns:
            {
                "columns": ["col1", "col2", ...],
                "rows": [[val1, val2, ...], ...],
                "row_count": 10,
                "execution_time_ms": 50
            }
        """
        import time

        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found")

        provider_type = db_config["provider"]
        params = db_config["params"]

        start_time = time.time()

        if provider_type == "postgres":
            import psycopg2

            conn = psycopg2.connect(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                dbname=params["database"],
            )
        elif provider_type in ("mysql", "mariadb"):
            import pymysql

            conn = pymysql.connect(
                host=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
            )
        else:
            raise ValueError(
                f"Query execution not supported for provider: {provider_type}"
            )

        try:
            cursor = conn.cursor()
            cursor.execute(query)

            # If the query mutates data, commit it
            conn.commit()

            # Fetch results with limit if it was a statement that returns rows
            if cursor.description:
                rows = cursor.fetchmany(limit)
                columns = [desc[0] for desc in cursor.description]
                row_count = len(rows)
            else:
                rows = []
                columns = []
                # `rowcount` can signify rows affected in an UPDATE/DELETE/INSERT
                row_count = cursor.rowcount if hasattr(cursor, "rowcount") else 0

            execution_time_ms = int((time.time() - start_time) * 1000)

            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": row_count,
                "execution_time_ms": execution_time_ms,
            }
        finally:
            conn.close()

    def list_tables(self, db_id: int) -> List[Dict[str, Any]]:
        """List all tables in a database"""
        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found")

        provider_type = db_config["provider"]
        params = db_config["params"]

        if provider_type == "postgres":
            import psycopg2

            conn = psycopg2.connect(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                dbname=params["database"],
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """
            )
            tables = [{"name": row[0], "type": row[1]} for row in cursor.fetchall()]
            conn.close()
            return tables

        elif provider_type in ("mysql", "mariadb"):
            import pymysql

            conn = pymysql.connect(
                host=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = %s
                ORDER BY table_name
            """,
                (params["database"],),
            )
            tables = [{"name": row[0], "type": row[1]} for row in cursor.fetchall()]
            conn.close()
            return tables
        else:
            raise ValueError(f"List tables not supported for provider: {provider_type}")

    def get_table_schema(self, db_id: int, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found")

        provider_type = db_config["provider"]
        params = db_config["params"]

        if provider_type == "postgres":
            import psycopg2

            conn = psycopg2.connect(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                dbname=params["database"],
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """,
                (table_name,),
            )
            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "default": row[3],
                }
                for row in cursor.fetchall()
            ]
            conn.close()
            return {"table": table_name, "columns": columns}

        elif provider_type in ("mysql", "mariadb"):
            import pymysql

            conn = pymysql.connect(
                host=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """,
                (params["database"], table_name),
            )
            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "default": row[3],
                }
                for row in cursor.fetchall()
            ]
            conn.close()
            return {"table": table_name, "columns": columns}
        else:
            raise ValueError(
                f"Get table schema not supported for provider: {provider_type}"
            )

    def get_database_schema(self, db_id: int) -> Dict[str, Any]:
        """Get full schema mapping for the database (tables, columns, foreign keys)"""
        db_config = self.config_manager.get_database(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found")

        provider_type = db_config["provider"]
        params = db_config["params"]

        schema = {"tables": [], "edges": []}

        if provider_type == "postgres":
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                dbname=params["database"],
            )
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Fetch tables & columns
                cursor.execute(
                    """
                    SELECT 
                        c.table_name, 
                        c.column_name, 
                        c.data_type, 
                        c.is_nullable,
                        tc.constraint_type
                    FROM information_schema.columns c
                    LEFT JOIN information_schema.key_column_usage kcu
                        ON c.table_name = kcu.table_name 
                        AND c.column_name = kcu.column_name
                    LEFT JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name 
                        AND tc.constraint_type = 'PRIMARY KEY'
                    WHERE c.table_schema = 'public'
                    ORDER BY c.table_name, c.ordinal_position
                """
                )

                tables_map = {}
                for row in cursor.fetchall():
                    t_name = row["table_name"]
                    if t_name not in tables_map:
                        tables_map[t_name] = {
                            "id": t_name,
                            "name": t_name,
                            "columns": [],
                        }

                    tables_map[t_name]["columns"].append(
                        {
                            "name": row["column_name"],
                            "type": row["data_type"],
                            "nullable": row["is_nullable"] == "YES",
                            "isPrimary": row["constraint_type"] == "PRIMARY KEY",
                        }
                    )

                schema["tables"] = list(tables_map.values())

                # Fetch Foreign Keys
                cursor.execute(
                    """
                    SELECT
                        tc.table_name AS source_table,
                        kcu.column_name AS source_column,
                        ccu.table_name AS target_table,
                        ccu.column_name AS target_column
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema='public';
                """
                )

                for row in cursor.fetchall():
                    schema["edges"].append(
                        {
                            "id": f"edge-{row['source_table']}-{row['source_column']}-{row['target_table']}",
                            "source": row["source_table"],
                            "target": row["target_table"],
                            "sourceHandle": row["source_column"],
                            "targetHandle": row["target_column"],
                        }
                    )

            finally:
                conn.close()

            return schema

        elif provider_type in ("mysql", "mariadb"):
            import pymysql
            from pymysql.cursors import DictCursor

            conn = pymysql.connect(
                host=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
                cursorclass=DictCursor,
            )
            try:
                cursor = conn.cursor()

                # Fetch tables & columns
                cursor.execute(
                    """
                    SELECT 
                        TABLE_NAME as table_name,
                        COLUMN_NAME as column_name,
                        DATA_TYPE as data_type,
                        IS_NULLABLE as is_nullable,
                        COLUMN_KEY as column_key
                    FROM information_schema.columns
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                    (params["database"],),
                )

                tables_map = {}
                for row in cursor.fetchall():
                    t_name = row["table_name"]
                    if t_name not in tables_map:
                        tables_map[t_name] = {
                            "id": t_name,
                            "name": t_name,
                            "columns": [],
                        }

                    tables_map[t_name]["columns"].append(
                        {
                            "name": row["column_name"],
                            "type": row["data_type"],
                            "nullable": row["is_nullable"] == "YES",
                            "isPrimary": row["column_key"] == "PRI",
                        }
                    )

                schema["tables"] = list(tables_map.values())

                # Fetch Foreign Keys
                cursor.execute(
                    """
                    SELECT 
                        TABLE_NAME as source_table,
                        COLUMN_NAME as source_column,
                        REFERENCED_TABLE_NAME as target_table,
                        REFERENCED_COLUMN_NAME as target_column
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                    (params["database"],),
                )

                for row in cursor.fetchall():
                    schema["edges"].append(
                        {
                            "id": f"edge-{row['source_table']}-{row['source_column']}-{row['target_table']}",
                            "source": row["source_table"],
                            "target": row["target_table"],
                            "sourceHandle": row["source_column"],
                            "targetHandle": row["target_column"],
                        }
                    )

            finally:
                conn.close()

            return schema

        else:
            raise ValueError(
                f"Full schema extraction not supported for provider: {provider_type}"
            )
