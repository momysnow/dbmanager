from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Type, Optional
import os
from config import ConfigManager, CONFIG_DIR
from .providers.base import BaseProvider
from .providers.postgres import PostgresProvider
from .providers.mysql import MySQLProvider
from .providers.sqlserver import SQLServerProvider
from .providers.mongodb import MongoDBProvider
from .providers.mariadb import MariaDBProvider
from .bucket_manager import BucketManager
from .backup_utils import save_checksum, verify_backup, verify_checksum
from .compression import compress_file, get_compression_ratio
from .encryption import encrypt_file, decrypt_file
from .notifications import NotificationManager
from .progress import ProgressStatus


BACKUP_ROOT = CONFIG_DIR / "backups"

class DBManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.bucket_manager = BucketManager(self.config_manager)
        self.notification_manager = NotificationManager(self.config_manager.config)
        
        # Initialize config sync
        from .config_sync import ConfigSync
        self.config_sync = ConfigSync(self.bucket_manager, self.config_manager)
        
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

    def add_database(self, name: str, provider_type: str, connection_params: Dict[str, Any]):
        if provider_type not in self.provider_map:
            raise ValueError(f"Provider {provider_type} not supported.")
        
        db_config = {
            "name": name,
            "provider": provider_type,
            "params": connection_params
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

    def delete_database(self, db_id: int):
        self.config_manager.remove_database(db_id)

    def update_database(self, db_id: int, name: str, provider_type: str, 
                       connection_params: Dict[str, Any], retention: int = 0,
                       s3_enabled: bool = False, s3_bucket_id: int = None, 
                       s3_retention: int = 0):
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
        old_bucket_id = current_config.get('s3_bucket_id') if current_config else None
        
        # Prepare new config
        db_config = {
            "name": name,
            "provider": provider_type,
            "params": connection_params,
            "retention": retention,
            "s3_enabled": s3_enabled,
            "s3_bucket_id": s3_bucket_id,
            "s3_retention": s3_retention
        }
        
        # Check if S3 bucket changed
        bucket_changed = (
            old_bucket_id != s3_bucket_id and 
            old_bucket_id is not None and 
            s3_bucket_id is not None and
            s3_enabled
        )
        
        # Update config
        result = self.config_manager.update_database(db_id, db_config)
        
        # Trigger bucket migration if needed
        if bucket_changed and result:
            print(f"\n⚠️  S3 bucket changed - migration required")
            from .bucket_migrator import BucketMigrator
            migrator = BucketMigrator(self.bucket_manager)
            
            # Ask user for confirmation
            print(f"   Old bucket: {self.bucket_manager.get_bucket_name(old_bucket_id)}")
            print(f"   New bucket: {self.bucket_manager.get_bucket_name(s3_bucket_id)}")
            
            # Estimate migration size
            estimate = migrator.estimate_migration_size(db_id, old_bucket_id)
            print(f"   Backups to migrate: {estimate['count']} ({estimate['size_mb']} MB)")
            
            response = input("\n   Migrate backups now? (y/n): ").lower().strip()
            if response == 'y':
                # Ask about cleanup
                delete_response = input("   Delete backups from old bucket after migration? (y/n): ").lower().strip()
                delete_old = delete_response == 'y'
                
                migrator.migrate_database_backups(
                    db_id, 
                    old_bucket_id, 
                    s3_bucket_id,
                    delete_old=delete_old
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
        safe_name = "".join([c for c in db_config["name"] if c.isalnum() or c in ('-', '_')])
        return BACKUP_ROOT / f"{db_id}_{safe_name}"

    def backup_database(self, db_id: int, tag: str = None, progress: Optional['BackupProgress'] = None) -> str:
        db_config = self.config_manager.get_database(db_id)
        provider = self.get_provider_instance(db_id)
        backup_dir = self._get_backup_dir(db_id)

        if progress and progress.status == ProgressStatus.IDLE:
            progress.start(f"Starting backup for {db_config.get('name', db_id)}")
        
        # Get options
        retention = int(db_config.get("retention", 0)) # 0 = infinite (local)
        s3_enabled = db_config.get("s3_enabled", False)
        s3_bucket_id = db_config.get("s3_bucket_id")
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
                # Handle .dump.gz or similar if provider adds it, closely looking at extension
                if filename.endswith('.tar.gz'):
                    name_part = filename[:-7]
                    ext = '.tar.gz'
                elif filename.endswith('.gz'):
                    name_part, ext = os.path.splitext(filename[:-3])
                    ext = ext + '.gz'
                
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
                compressed_path = compress_file(path, algorithm=algorithm, level=level, remove_original=True)
                
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
                    print(f"✅ Compressed: {os.path.basename(compressed_path)} ({ratio:.2%} of original)")
                else:
                    print(f"✅ Compressed: {os.path.basename(compressed_path)}")
            except Exception as e:
                print(f"⚠️  Compression failed: {e}, using uncompressed backup")
        
        # Encrypt backup if enabled
        encryption_settings = self.config_manager.get_encryption_settings()
        if encryption_settings.get("enabled", False):
            password = encryption_settings.get("password")
            if not password:
                print(f"⚠️  Encryption enabled but no password set, skipping encryption")
            else:
                try:
                    print(f"🔐 Encrypting backup...")
                    encrypted_path = encrypt_file(path, password, remove_original=True)
                    
                    # Update path to encrypted file
                    old_path = path
                    path = encrypted_path
                    
                    # Update checksum file reference
                    if checksum_file:
                        # Rename checksum file to match encrypted file
                        old_checksum = checksum_file
                        checksum_file = f"{encrypted_path}.sha256"
                        try:
                            os.rename(old_checksum, checksum_file)
                        except:
                            # If rename fails, regenerate checksum for encrypted file
                            checksum_file = save_checksum(encrypted_path)
                    
                    print(f"✅ Encrypted: {os.path.basename(encrypted_path)}")
                except Exception as e:
                    print(f"⚠️  Encryption failed: {e}, using unencrypted backup")
        
        # Upload to S3 if configured
        if s3_enabled and s3_bucket_id:
            try:
                storage = self.bucket_manager.get_storage(s3_bucket_id)
                if storage:
                    filename = os.path.basename(path)
                    s3_key = f"backups/{db_id}/{filename}"
                    
                    # Calculate or retrieve checksum (hash)
                    current_hash = None
                    if checksum_file:
                         # Read checksum from file
                         try:
                             with open(checksum_file, 'r') as f:
                                 current_hash = f.read().strip()
                         except:
                             pass
                    
                    # Check for Deduplication
                    dedup_ref_key = None
                    if current_hash:
                        # Fetch latest backup from S3
                        try:
                            prefix = f"backups/{db_id}/"
                            # List 5 latest to be safe
                            existing_backups = storage.list_files(prefix, max_keys=5)
                            # Sort by date desc (list_files might not guarantee order)
                            existing_backups.sort(key=lambda x: x['last_modified'], reverse=True)
                            
                            if existing_backups:
                                latest = existing_backups[0]
                                # Get full info to access Metadata
                                info = storage.get_file_info(latest['key'])
                                if info and 'metadata' in info:
                                    last_hash = info['metadata'].get('hash')
                                    if last_hash == current_hash:
                                        # Identical content! Use pointer
                                        # But wait, if the latest is ITSELF a pointer, we should point to ITS target
                                        # to avoid long chains? Or just point to it. 
                                        # Pointer resolution is recursive-ish in logic, but single-hop is safer.
                                        # Let's check if 'dedup_ref' is in its metadata
                                        if 'dedup_ref' in info['metadata']:
                                            dedup_ref_key = info['metadata']['dedup_ref']
                                        else:
                                            dedup_ref_key = latest['key']
                        except Exception as e:
                            print(f"⚠️  Deduplication check failed: {e}")

                    # Add metadata
                    metadata = {
                        'database_id': str(db_id),
                        'database_name': db_config.get('name', ''),
                        'provider': db_config.get('provider', ''),
                        'backup_date': datetime.now().isoformat(),
                        'tag': tag if tag else '',
                        'hash': current_hash if current_hash else ''
                    }
                    
                    if storage.upload_file(path, s3_key, metadata, dedup_ref_key=dedup_ref_key):
                        print(f"✅ Backup uploaded to S3: {s3_key}")
                        
                        # Upload checksum file if it exists AND we didn't deduplicate (or should we always?)
                        # If we deduplicated, the data is safe. The checksum file is tiny, let's just upload it normally
                        # so verification tools work locally if downloaded.
                        if checksum_file and Path(checksum_file).exists():
                            checksum_s3_key = f"{s3_key}.sha256"
                            if storage.upload_file(checksum_file, checksum_s3_key):
                                print(f"✅ Checksum uploaded to S3")
                    else:
                        print(f"⚠️  S3 upload failed, local backup retained")
            except Exception as e:
                print(f"⚠️  S3 upload error: {e}, local backup retained")

        # Handle local retention
        if retention > 0:
            self._enforce_retention(db_id, retention)
        
        # Handle S3 retention
        if s3_enabled and s3_bucket_id and s3_retention > 0:
            self._enforce_s3_retention(db_id, s3_bucket_id, s3_retention)
            
        if progress and progress.status not in (ProgressStatus.COMPLETED, ProgressStatus.FAILED):
            progress.complete(f"Backup completed: {os.path.basename(path)}")

        return path

    def _enforce_retention(self, db_id: int, keep_last: int):
        backups = self.list_backups(db_id) # already sorted desc
        if len(backups) > keep_last:
            to_delete = backups[keep_last:]
            for b in to_delete:
                try:
                    Path(b["path"]).unlink()
                    checksum_path = Path(f"{b['path']}.sha256")
                    checksum_path.unlink(missing_ok=True)
                except Exception:
                    pass
    
    def _enforce_s3_retention(self, db_id: int, bucket_id: int, keep_last: int):
        """
        Enforce retention policy on S3 backups
        
        Args:
            db_id: Database ID
            bucket_id: S3 bucket ID
            keep_last: Number of backups to keep
        """
        try:
            storage = self.bucket_manager.get_storage(bucket_id)
            if not storage:
                return
            
            # List all backups for this database in S3
            prefix = f"backups/{db_id}/"
            s3_backups = storage.list_files(prefix)
            
            # Sort by last_modified descending
            s3_backups = sorted(s3_backups, key=lambda x: x['last_modified'], reverse=True)
            
            # Delete old backups
            if len(s3_backups) > keep_last:
                to_delete = s3_backups[keep_last:]
                for backup in to_delete:
                    try:
                        storage.delete_file(backup['key'])
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
            # Support multiple backup formats
            for pattern in ["*.sql", "*.dump", "*.bak", "*.tar.gz", "*.gz"]:
                for f in backup_dir.glob(pattern):
                    # Skip checksum files
                    if f.suffix == '.sha256':
                        continue
                        
                    try:
                        stat = f.stat()
                        backups.append({
                            "filename": f.name,
                            "path": str(f),
                            "date": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                            "size_mb": stat.st_size / (1024 * 1024),
                            "location": "local",
                            "has_checksum": Path(f"{f}.sha256").exists()
                        })
                    except Exception as e:
                        print(f"Error reading local backup {f}: {e}")

        # 2. S3 BACKUPS
        try:
            db_config = self.config_manager.get_database(db_id)
            if db_config and db_config.get("s3_enabled") and db_config.get("s3_bucket_id"):
                bucket_id = db_config.get("s3_bucket_id")
                storage = self.bucket_manager.get_storage(bucket_id)
                if storage:
                    prefix = f"backups/{db_id}/"
                    s3_files = storage.list_files(prefix)
                    
                    for s3_file in s3_files:
                        key = s3_file['key']
                        # Skip checksum files
                        if key.endswith('.sha256'):
                            continue
                            
                        # Check metadata for hash
                        # s3_file usually contains: key, size, last_modified, etag
                        # list_files might not return full metadata, might need separate head calls if we want 'hash', 
                        # but that's expensive for list. 
                        # Let's assume list_files returns basic info.
                        
                        # Check if a .sha256 sibling exists in the list?
                        # It's expensive to search list for every item. 
                        # For now, let's assume if it's in S3 and we uploaded it, it likely has integrity.
                        # Or check if key + .sha256 is in the s3_files list logic?
                        has_checksum = any(f['key'] == f"{key}.sha256" for f in s3_files)
                        
                        backups.append({
                            "filename": os.path.basename(key),
                            "path": key, # S3 Key
                            "date": s3_file['last_modified'], # Should be datetime
                            "size_mb": s3_file['size'] / (1024 * 1024),
                            "location": "s3",
                            "has_checksum": has_checksum
                        })
        except Exception as e:
            print(f"Error listing S3 backups: {e}")
        
        # Sort by date desc
        return sorted(backups, key=lambda x: x["date"], reverse=True)

    def verify_backup_integrity(self, backup_path: str, location: str = 'local', db_id: int = None) -> bool:
        """
        Verify backup integrity using checksum.
        
        Args:
            backup_path: Path to backup file (or S3 key)
            location: 'local' or 's3'
            db_id: Database ID (required for S3 to find bucket)
        
        Returns:
            True if valid
        """
        if location == 'local':
            return verify_backup(backup_path)['valid']
        elif location == 's3':
            if not db_id:
                raise ValueError("db_id required for S3 verification")

            db_config = self.config_manager.get_database(db_id)
            if not db_config or not db_config.get("s3_bucket_id"):
                raise ValueError("S3 not configured for this database")

            storage = self.bucket_manager.get_storage(db_config.get("s3_bucket_id"))
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
                    return verify_backup(local_file)['valid']

                # If no checksum, use metadata hash if present
                stored_hash = info.get('metadata', {}).get('hash')
                if stored_hash:
                    return verify_checksum(local_file, expected_hash=stored_hash)

                # No checksum available
                raise FileNotFoundError("S3 checksum not found")
        return False
    
    def restore_database(self, db_id: int, backup_file: str, progress: Optional['BackupProgress'] = None, create_safety_snapshot: bool = True):
        provider = self.get_provider_instance(db_id)
        # Verify file exists
        if not Path(backup_file).exists():
            raise FileNotFoundError(f"Backup file {backup_file} not found")
        
        # Verify checksum if available
        checksum_file = Path(f"{backup_file}.sha256")
        if checksum_file.exists():
            print(f"🔍 Verifying backup integrity...")
            if progress: progress.update(message="Verifying backup integrity...", step="Pre-check")
            try:
                if verify_checksum(backup_file):
                    print(f"✅ Checksum verified - backup is intact")
                else:
                    raise ValueError("Checksum verification failed - backup may be corrupted")
            except Exception as e:
                print(f"⚠️  Checksum verification failed: {e}")
                # For critical integrity check, we normally generally abort, 
                # but might allow user override if CLI. For API/Auto, we should abort or warn.
                # Assuming strict mode for Safety.
                raise RuntimeError(f"Restore aborted: Checksum verification failed ({e})")
        
        # SAFETY SNAPSHOT
        safety_snapshot_path = None
        if create_safety_snapshot:
            print(f"📸 Creating safety snapshot before restore...")
            if progress: progress.update(message="Creating safety snapshot...", step="Safety Snapshot")
            try:
                # We use a special tag and don't track progress for this internal step to avoid confusing the main progress bar
                safety_snapshot_path = self.backup_database(db_id, tag="safety_snapshot")
                print(f"✅ Safety snapshot created: {os.path.basename(safety_snapshot_path)}")
            except Exception as e:
                print(f"⚠️  Failed to create safety snapshot: {e}")
                # We should probably abort restore if safety snapshot fails, to be safe.
                raise RuntimeError(f"Restore aborted: Could not create safety snapshot ({e})")

        # PERFORM RESTORE
        try:
            result = provider.restore(backup_file, progress=progress)
            
            # If we got here, success. We can optionally clean up safety snapshot or keep it.
            # Keeping it is safer (can be deleted by retention later).
            return result

        except Exception as e:
            print(f"❌ RESTORE FAILED: {e}")
            if progress: progress.fail(f"Restore failed: {e}")
            
            # ROLLBACK LOGIC
            if safety_snapshot_path and os.path.exists(safety_snapshot_path):
                print(f"🔄 Attempting ROLLBACK to safety snapshot...")
                if progress: 
                    progress.update(message="Restoring from safety snapshot...", step="Rolling Back")
                    # Reset progress for rollback? Or just update message.
                
                try:
                    # Recursive call with create_safety_snapshot=False to avoid infinite loop
                    self.restore_database(db_id, safety_snapshot_path, create_safety_snapshot=False)
                    msg = "Restore failed, but database was successfully rolled back to previous state."
                    print(f"✅ {msg}")
                    # Re-raise original error but with rollback info
                    raise RuntimeError(f"Restore failed: {e}. ROLLBACK SUCCESSFUL.")
                except Exception as rollback_error:
                    msg = f"CRITICAL: Restore failed AND Rollback failed! Database may be in inconsistent state. ({rollback_error})"
                    print(f"⛔️ {msg}")
                    raise RuntimeError(msg)
            else:
                raise RuntimeError(f"Restore failed: {e}. No safety snapshot available for rollback.")

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
            return {'success': [], 'failed': []}
        
        print(f"🚀 Starting backup for {len(databases)} databases (Parallel: {max_workers})...")
        
        results = {'success': [], 'failed': []}
        
        # Helper function for thread
        def _job(db_config):
            db_id = db_config['id']
            name = db_config['name']
            try:
                # We don't pass progress tracker for batch jobs mostly to avoid stdout collision,
                # unless we have a sophisticated multi-bar UI.
                path = self.backup_database(db_id)
                return {'id': db_id, 'name': name, 'status': 'success', 'path': path}
            except Exception as e:
                return {'id': db_id, 'name': name, 'status': 'error', 'error': str(e)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_db = {executor.submit(_job, db): db for db in databases}
            
            for future in as_completed(future_to_db):
                db = future_to_db[future]
                try:
                    res = future.result()
                    if res['status'] == 'success':
                        print(f"✅ [{res['name']}] Backup completed.")
                        results['success'].append(res)
                    else:
                        print(f"❌ [{res['name']}] Backup failed: {res['error']}")
                        results['failed'].append(res)
                except Exception as exc:
                    print(f"❌ [{db['name']}] Thread exception: {exc}")
                    results['failed'].append({'id': db['id'], 'name': db['name'], 'error': str(exc)})
                    
        return results
