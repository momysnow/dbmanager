from datetime import datetime
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
        provider_class = self.providers.get(provider_type)
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
        if provider_type not in self.providers:
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

    def backup_database(self, db_id: int, progress: Optional['BackupProgress'] = None) -> str:
        db_config = self.config_manager.get_database(db_id)
        provider = self.get_provider_instance(db_id)
        backup_dir = self._get_backup_dir(db_id)
        
        # Get options
        retention = int(db_config.get("retention", 0)) # 0 = infinite (local)
        s3_enabled = db_config.get("s3_enabled", False)
        s3_bucket_id = db_config.get("s3_bucket_id")
        s3_retention = int(db_config.get("s3_retention", 0))  # 0 = infinite (S3)

        # Run local backup with progress tracking
        path = provider.backup(str(backup_dir), progress=progress)
        
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
                compressed_path = compress_file(path, algorithm=algorithm, level=level, remove_original=True)
                
                # Calculate compression ratio
                # Since original is removed, we need to use file sizes from before compression
                original_size = os.path.getsize(compressed_path) / get_compression_ratio(path, compressed_path) if os.path.exists(compressed_path) else 0
                
                # Update path to compressed file
                old_path = path
                path = compressed_path
                
                # Update checksum file reference
                if checksum_file:
                    # Rename checksum file to match compressed file
                    old_checksum = checksum_file
                    checksum_file = f"{compressed_path}.sha256"
                    try:
                        os.rename(old_checksum, checksum_file)
                    except:
                        # If rename fails, regenerate checksum for compressed file
                        checksum_file = save_checksum(compressed_path)
                
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
                    
                    # Add metadata
                    metadata = {
                        'database_id': str(db_id),
                        'database_name': db_config.get('name', ''),
                        'provider': db_config.get('provider', ''),
                        'backup_date': datetime.now().isoformat()
                    }
                    
                    if storage.upload_file(path, s3_key, metadata):
                        print(f"✅ Backup uploaded to S3: {s3_key}")
                        
                        # Upload checksum file if it exists
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
            
        return path

    def _enforce_retention(self, db_id: int, keep_last: int):
        backups = self.list_backups(db_id) # already sorted desc
        if len(backups) > keep_last:
            to_delete = backups[keep_last:]
            for b in to_delete:
                try:
                    Path(b["path"]).unlink()
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
                        print(f"🗑️ Deleted old S3 backup: {backup['key']}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete S3 backup {backup['key']}: {e}")
        except Exception as e:
            print(f"⚠️ S3 retention cleanup failed: {e}")

    def list_backups(self, db_id: int) -> List[Dict[str, Any]]:
        backup_dir = self._get_backup_dir(db_id)
        if not backup_dir.exists():
            return []
        
        backups = []
        # Support multiple backup formats: .sql, .dump (PostgreSQL), .bak (SQL Server)
        for pattern in ["*.sql", "*.dump", "*.bak"]:
            for f in backup_dir.glob(pattern):
                stat = f.stat()
                backups.append({
                    "filename": f.name,
                    "path": str(f),
                    "date": datetime.fromtimestamp(stat.st_mtime),
                    "size_mb": stat.st_size / (1024 * 1024)
                })
        
        # Sort by date desc
        return sorted(backups, key=lambda x: x["date"], reverse=True)

    def verify_backup_integrity(self, backup_path: str) -> dict:
        """
        Verify backup integrity using checksum.
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            Verification result dictionary with status and details
        """
        return verify_backup(backup_path)
    
    def restore_database(self, db_id: int, backup_file: str, progress: Optional['BackupProgress'] = None):
        provider = self.get_provider_instance(db_id)
        # Verify file exists
        if not Path(backup_file).exists():
            raise FileNotFoundError(f"Backup file {backup_file} not found")
        
        # Verify checksum if available
        checksum_file = Path(f"{backup_file}.sha256")
        if checksum_file.exists():
            print(f"🔍 Verifying backup integrity...")
            try:
                if verify_checksum(backup_file):
                    print(f"✅ Checksum verified - backup is intact")
                else:
                    raise ValueError("Checksum verification failed - backup may be corrupted")
            except Exception as e:
                print(f"⚠️  Checksum verification failed: {e}")
                response = input("Continue with restore anyway? (y/n): ").lower().strip()
                if response != 'y':
                    raise RuntimeError("Restore cancelled due to checksum mismatch")
        
        return provider.restore(backup_file, progress=progress)
