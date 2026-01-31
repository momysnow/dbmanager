"""
S3 Bucket Migrator
Handles migration of backups between S3 buckets
"""
import os
import tempfile
from typing import Optional
from pathlib import Path


class BucketMigrator:
    """
    Manages migration of database backups between S3 buckets
    Preserves complete backup history during bucket changes
    """
    
    def __init__(self, bucket_manager):
        """
        Initialize BucketMigrator
        
        Args:
            bucket_manager: BucketManager instance
        """
        self.bucket_manager = bucket_manager
    
    def migrate_database_backups(
        self,
        db_id: int,
        old_bucket_id: int,
        new_bucket_id: int,
        delete_old: bool = False,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Migrate all backups for a database from old bucket to new bucket
        
        Args:
            db_id: Database ID
            old_bucket_id: Source S3 bucket ID
            new_bucket_id: Destination S3 bucket ID
            delete_old: If True, delete backups from old bucket after migration
            progress_callback: Optional callback function(current, total, filename)
        
        Returns:
            True if migration successful, False otherwise
        """
        print(f"\n🔄 Starting backup migration for database {db_id}")
        print(f"   From: {self.bucket_manager.get_bucket_name(old_bucket_id)}")
        print(f"   To:   {self.bucket_manager.get_bucket_name(new_bucket_id)}")
        
        try:
            # Get storage instances
            old_storage = self.bucket_manager.get_storage(old_bucket_id)
            new_storage = self.bucket_manager.get_storage(new_bucket_id)
            
            if not old_storage or not new_storage:
                print("❌ Failed to initialize S3 storage")
                return False
            
            # List all backups in old bucket
            prefix = f"backups/{db_id}/"
            backups = old_storage.list_files(prefix)
            
            if not backups:
                print("ℹ️  No backups found in old bucket")
                return True
            
            total = len(backups)
            print(f"📦 Found {total} backup(s) to migrate")
            
            # Migrate each backup
            success_count = 0
            failed_files = []
            
            with tempfile.TemporaryDirectory() as temp_dir:
                for i, backup in enumerate(backups, 1):
                    s3_key = backup['key']
                    filename = os.path.basename(s3_key)
                    temp_path = os.path.join(temp_dir, filename)
                    
                    if progress_callback:
                        progress_callback(i, total, filename)
                    else:
                        print(f"  [{i}/{total}] Migrating {filename}...")
                    
                    try:
                        # Download from old bucket
                        if not old_storage.download_file(s3_key, temp_path):
                            failed_files.append(filename)
                            continue
                        
                        # Upload to new bucket
                        if not new_storage.upload_file(temp_path, s3_key, backup.get('metadata')):
                            failed_files.append(filename)
                            continue
                        
                        success_count += 1
                        
                        # Delete from old bucket if requested
                        if delete_old:
                            old_storage.delete_file(s3_key)
                        
                        # Cleanup temp file
                        try:
                            os.remove(temp_path)
                        except:
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
    
    def estimate_migration_size(self, db_id: int, bucket_id: int) -> dict:
        """
        Estimate size and count of backups to migrate
        
        Args:
            db_id: Database ID
            bucket_id: S3 bucket ID
        
        Returns:
            Dictionary with count and total size in bytes
        """
        try:
            storage = self.bucket_manager.get_storage(bucket_id)
            if not storage:
                return {'count': 0, 'size_bytes': 0, 'size_mb': 0}
            
            prefix = f"backups/{db_id}/"
            backups = storage.list_files(prefix)
            
            total_size = sum(b['size'] for b in backups)
            
            return {
                'count': len(backups),
                'size_bytes': total_size,
                'size_mb': round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            print(f"⚠️ Failed to estimate migration size: {e}")
            return {'count': 0, 'size_bytes': 0, 'size_mb': 0}
