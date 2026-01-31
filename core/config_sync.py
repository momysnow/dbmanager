"""
Config Sync Module
Handles automatic synchronization of config.json to S3
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class ConfigSync:
    """
    Manages synchronization of config.json with S3 bucket
    Provides automatic upload on changes and download on startup
    """
    
    def __init__(self, bucket_manager, config_manager):
        """
        Initialize ConfigSync
        
        Args:
            bucket_manager: BucketManager instance
            config_manager: ConfigManager instance
        """
        self.bucket_manager = bucket_manager
        self.config_manager = config_manager
        self.config_backup_key = "config/config.json"
        self.config_metadata_key = "config/metadata.json"
    
    def get_config_bucket_id(self) -> Optional[int]:
        """
        Get the bucket ID configured for config sync
        
        Returns:
            Bucket ID or None if not configured
        """
        return self.config_manager.config.get('config_sync_bucket_id')
    
    def set_config_bucket(self, bucket_id: Optional[int]):
        """
        Set the bucket for config sync
        
        Args:
            bucket_id: Bucket ID or None to disable sync
        """
        self.config_manager.config['config_sync_bucket_id'] = bucket_id
        self.config_manager.save_config()
    
    def is_enabled(self) -> bool:
        """Check if config sync is enabled"""
        bucket_id = self.get_config_bucket_id()
        return bucket_id is not None
    
    def sync_to_s3(self, silent: bool = False) -> bool:
        """
        Upload current config.json to S3
        
        Args:
            silent: If True, suppress output messages
        
        Returns:
            True if successful, False otherwise
        """
        bucket_id = self.get_config_bucket_id()
        if not bucket_id:
            return False
        
        try:
            storage = self.bucket_manager.get_storage(bucket_id)
            if not storage:
                if not silent:
                    print("⚠️ Failed to get S3 storage for config sync")
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
                'sync_time': datetime.now().isoformat(),
                'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
                'version': '1.0'
            }
            
            # Upload config
            if storage.upload_file(config_path, self.config_backup_key, metadata):
                # Also upload metadata separately for easier access
                metadata_str = json.dumps(metadata, indent=2)
                temp_metadata = '/tmp/config_metadata.json'
                with open(temp_metadata, 'w') as f:
                    f.write(metadata_str)
                storage.upload_file(temp_metadata, self.config_metadata_key)
                os.remove(temp_metadata)
                
                if not silent:
                    print(f"✅ Config synced to S3 ({self.bucket_manager.get_bucket_name(bucket_id)})")
                return True
            else:
                if not silent:
                    print("⚠️ Failed to upload config to S3")
                return False
                
        except Exception as e:
            if not silent:
                print(f"⚠️ Config sync failed: {e}")
            return False
    
    def sync_from_s3(self, force: bool = False) -> bool:
        """
        Download config.json from S3
        
        Args:
            force: If True, overwrite local config without checking timestamps
        
        Returns:
            True if successful, False otherwise
        """
        bucket_id = self.get_config_bucket_id()
        if not bucket_id:
            return False
        
        try:
            storage = self.bucket_manager.get_storage(bucket_id)
            if not storage:
                print("⚠️ Failed to get S3 storage for config sync")
                return False
            
            # Check if config exists on S3
            s3_config_info = storage.get_file_info(self.config_backup_key)
            if not s3_config_info:
                print("ℹ️  No config found on S3")
                return False
            
            from config import CONFIG_FILE
            local_config_path = str(CONFIG_FILE)
            
            # Conflict resolution
            if os.path.exists(local_config_path) and not force:
                local_mtime = datetime.fromtimestamp(os.path.getmtime(local_config_path))
                s3_mtime = s3_config_info['last_modified']
                
                # Make both timezone-aware or both naive for comparison
                if s3_mtime.tzinfo is not None:
                    s3_mtime = s3_mtime.replace(tzinfo=None)
                
                if local_mtime > s3_mtime:
                    print(f"ℹ️  Local config is newer (local: {local_mtime}, S3: {s3_mtime})")
                    response = input("   Overwrite with S3 version? (y/n): ").lower().strip()
                    if response != 'y':
                        print("   Keeping local config")
                        return False
            
            # Backup local config before downloading
            if os.path.exists(local_config_path):
                backup_path = f"{local_config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(local_config_path, backup_path)
                print(f"📋 Local config backed up to: {backup_path}")
            
            # Download from S3
            if storage.download_file(self.config_backup_key, local_config_path):
                print(f"✅ Config downloaded from S3")
                
                # Reload config in memory
                self.config_manager.config = self.config_manager._load_config()
                return True
            else:
                print("⚠️ Failed to download config from S3")
                return False
                
        except Exception as e:
            print(f"⚠️ Config download failed: {e}")
            return False
    
    def get_s3_config_info(self) -> Optional[dict]:
        """
        Get metadata about config stored on S3
        
        Returns:
            Dictionary with config info or None
        """
        bucket_id = self.get_config_bucket_id()
        if not bucket_id:
            return None
        
        try:
            storage = self.bucket_manager.get_storage(bucket_id)
            if not storage:
                return None
            
            return storage.get_file_info(self.config_backup_key)
        except:
            return None
    
    def auto_sync_on_startup(self):
        """
        Automatically sync from S3 on application startup if configured
        Only downloads if S3 version is newer
        """
        if not self.is_enabled():
            return
        
        print("\n🔄 Checking for config updates from S3...")
        
        s3_info = self.get_s3_config_info()
        if not s3_info:
            print("ℹ️  No config found on S3")
            return
        
        from config import CONFIG_FILE
        local_config_path = str(CONFIG_FILE)
        
        if os.path.exists(local_config_path):
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_config_path))
            s3_mtime = s3_info['last_modified']
            
            # Make both timezone-aware or both naive
            if s3_mtime.tzinfo is not None:
                s3_mtime = s3_mtime.replace(tzinfo=None)
            
            if s3_mtime > local_mtime:
                print(f"📥 S3 config is newer - downloading...")
                self.sync_from_s3(force=True)
            else:
                print(f"✅ Local config is up to date")
        else:
            # No local config, download from S3
            print(f"📥 Downloading config from S3...")
            self.sync_from_s3(force=True)
