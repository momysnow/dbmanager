"""
S3 Bucket Manager
Handles S3 bucket configuration CRUD operations
"""
import json
from typing import List, Dict, Optional
from core.s3_storage import S3Storage


class BucketManager:
    """
    Manages S3 bucket configurations
    Provides CRUD operations for bucket configs and connection testing
    """
    
    def __init__(self, config_manager):
        """
        Initialize BucketManager
        
        Args:
            config_manager: ConfigManager instance
        """
        self.config_manager = config_manager
    
    def list_buckets(self) -> List[Dict]:
        """
        Get list of configured S3 buckets
        
        Returns:
            List of bucket configuration dictionaries
        """
        return self.config_manager.config.get('s3_buckets', [])
    
    def get_bucket(self, bucket_id: int) -> Optional[Dict]:
        """
        Get bucket configuration by ID
        
        Args:
            bucket_id: Bucket ID
        
        Returns:
            Bucket config dict or None if not found
        """
        for bucket in self.list_buckets():
            if bucket.get('id') == bucket_id:
                return bucket
        return None
    
    def add_bucket(self, bucket_config: Dict) -> int:
        """
        Add new S3 bucket configuration
        
        Args:
            bucket_config: Dictionary with bucket configuration
                - name: Display name
                - provider: "s3", "minio", or "garage"
                - endpoint_url: Custom endpoint (optional for AWS S3)
                - access_key: Access key
                - secret_key: Secret key
                - bucket: Bucket name
                - region: AWS region (default: us-east-1)
        
        Returns:
            New bucket ID
        """
        # Ensure s3_buckets key exists
        if 's3_buckets' not in self.config_manager.config:
            self.config_manager.config['s3_buckets'] = []
        
        # Generate ID
        existing_ids = [b.get('id', 0) for b in self.list_buckets()]
        new_id = max(existing_ids) + 1 if existing_ids else 1
        bucket_config['id'] = new_id
        
        # Add to config
        self.config_manager.config['s3_buckets'].append(bucket_config)
        self.config_manager.save_config()
        
        return new_id
    
    def update_bucket(self, bucket_id: int, new_config: Dict) -> bool:
        """
        Update existing bucket configuration
        
        Args:
            bucket_id: Bucket ID to update
            new_config: New configuration dictionary
        
        Returns:
            True if successful, False if bucket not found
        """
        if 's3_buckets' not in self.config_manager.config:
            return False
        
        for i, bucket in enumerate(self.config_manager.config['s3_buckets']):
            if bucket.get('id') == bucket_id:
                # Preserve ID
                new_config['id'] = bucket_id
                self.config_manager.config['s3_buckets'][i] = new_config
                self.config_manager.save_config()
                return True
        
        return False
    
    def delete_bucket(self, bucket_id: int) -> bool:
        """
        Delete bucket configuration
        
        Args:
            bucket_id: Bucket ID to delete
        
        Returns:
            True if successful, False if bucket not found or in use
        """
        # Check if bucket is in use by any database
        for db in self.config_manager.get_databases():
            if db.get('s3_bucket_id') == bucket_id:
                print(f"❌ Cannot delete bucket: in use by database '{db.get('name')}'")
                return False
        
        # Check if bucket is used for config sync
        if self.config_manager.config.get('config_sync_bucket_id') == bucket_id:
            print(f"❌ Cannot delete bucket: used for config sync")
            return False
        
        # Remove bucket
        if 's3_buckets' in self.config_manager.config:
            original_count = len(self.config_manager.config['s3_buckets'])
            self.config_manager.config['s3_buckets'] = [
                b for b in self.config_manager.config['s3_buckets']
                if b.get('id') != bucket_id
            ]
            
            if len(self.config_manager.config['s3_buckets']) < original_count:
                self.config_manager.save_config()
                return True
        
        return False
    
    def test_bucket(self, bucket_id: int) -> bool:
        """
        Test connection to S3 bucket
        
        Args:
            bucket_id: Bucket ID to test
        
        Returns:
            True if connection successful, False otherwise
        """
        bucket_config = self.get_bucket(bucket_id)
        if not bucket_config:
            print(f"❌ Bucket ID {bucket_id} not found")
            return False
        
        try:
            storage = S3Storage(bucket_config)
            return storage.test_connection()
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
    
    def get_storage(self, bucket_id: int) -> Optional[S3Storage]:
        """
        Get S3Storage instance for bucket
        
        Args:
            bucket_id: Bucket ID
        
        Returns:
            S3Storage instance or None if bucket not found
        """
        bucket_config = self.get_bucket(bucket_id)
        if not bucket_config:
            return None
        
        try:
            return S3Storage(bucket_config)
        except Exception as e:
            print(f"❌ Failed to create S3Storage: {e}")
            return None
    
    def get_bucket_name(self, bucket_id: int) -> Optional[str]:
        """
        Get display name of bucket
        
        Args:
            bucket_id: Bucket ID
        
        Returns:
            Bucket display name or None
        """
        bucket = self.get_bucket(bucket_id)
        return bucket.get('name') if bucket else None
