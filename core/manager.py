from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Type
import os
from config import ConfigManager, CONFIG_DIR
from .providers.base import BaseProvider
from .providers.postgres import PostgresProvider
from .providers.mysql import MySQLProvider
from .providers.sqlserver import SQLServerProvider
from .bucket_manager import BucketManager
# from .providers.sqlite import SQLiteProvider # To be implemented

BACKUP_ROOT = CONFIG_DIR / "backups"

class DBManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.bucket_manager = BucketManager(self.config_manager)
        
        # Initialize config sync
        from .config_sync import ConfigSync
        self.config_sync = ConfigSync(self.bucket_manager, self.config_manager)
        
        # Auto-sync config from S3 on startup if enabled
        self.config_sync.auto_sync_on_startup()
        
        self.providers: Dict[str, Type[BaseProvider]] = {
            "postgres": PostgresProvider,
            "mysql": MySQLProvider,
            "sqlserver": SQLServerProvider,
            # "sqlite": SQLiteProvider
        }

    def get_supported_providers(self) -> List[str]:
        return list(self.providers.keys())

    def add_database(self, name: str, provider_type: str, connection_params: Dict[str, Any]):
        if provider_type not in self.providers:
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

    def backup_database(self, db_id: int) -> str:
        db_config = self.config_manager.get_database(db_id)
        provider = self.get_provider_instance(db_id)
        backup_dir = self._get_backup_dir(db_id)
        
        # Get options
        retention = int(db_config.get("retention", 0)) # 0 = infinite (local)
        s3_enabled = db_config.get("s3_enabled", False)
        s3_bucket_id = db_config.get("s3_bucket_id")
        s3_retention = int(db_config.get("s3_retention", 0))  # 0 = infinite (S3)

        # Run local backup
        path = provider.backup(str(backup_dir))
        
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
                    else:
                        print(f"⚠️ S3 upload failed, local backup retained")
            except Exception as e:
                print(f"⚠️ S3 upload error: {e}, local backup retained")

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

    def restore_database(self, db_id: int, backup_file: str):
        provider = self.get_provider_instance(db_id)
        # Verify file exists
        if not Path(backup_file).exists():
            raise FileNotFoundError(f"Backup file {backup_file} not found")
        
        return provider.restore(backup_file)
