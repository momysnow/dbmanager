"""
S3 Storage Module
Handles S3-compatible storage (Amazon S3, Minio, Garage)
"""

import os
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from core.storage_provider import StorageProvider


class S3Storage(StorageProvider):
    """
    Manages S3-compatible storage operations
    Supports Amazon S3, Minio, Garage, and other S3-compatible services
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize S3 storage client

        Args:
            config: Dictionary with S3 configuration
                - provider: "s3", "minio", or "garage"
                - endpoint_url: Custom endpoint (optional for AWS S3)
                - access_key: AWS access key or equivalent
                - secret_key: AWS secret key or equivalent
                - bucket: Bucket name
                - region: AWS region (default: us-east-1)
        """
        super().__init__(config)
        self.bucket = config["bucket"]

        # Create S3 client with custom endpoint support
        client_config = {
            "aws_access_key_id": config["access_key"],
            "aws_secret_access_key": config["secret_key"],
            "region_name": config.get("region", "us-east-1"),
        }

        # Add custom endpoint for Minio/Garage
        if config.get("endpoint_url"):
            client_config["endpoint_url"] = config["endpoint_url"]

        self.client = boto3.client("s3", **client_config)

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict] = None,
        dedup_ref_key: Optional[str] = None,
    ) -> bool:
        """
        Upload a file to S3. Supports deduplication via reference.

        Args:
            local_path: Path to local file
            remote_path: S3 object key (path in bucket)
            metadata: Optional metadata to attach to object
            dedup_ref_key: If provided, creates a lightweight pointer object
                that references this key instead of uploading data.

        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = metadata
            else:
                extra_args["Metadata"] = {}

            if dedup_ref_key:
                # DEDUPLICATION: Create a pointer object
                print(f"♻️  Deduplication: creating pointer to {dedup_ref_key}")
                extra_args["Metadata"]["dedup_ref"] = dedup_ref_key
                # We upload an empty body or minimal marker
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=remote_path,
                    Body=b"DEDUP_POINTER",
                    Metadata=extra_args["Metadata"],
                )
                print(f"✅ Uploaded pointer {remote_path} -> {dedup_ref_key}")
                return True

            # Normal Upload
            self.client.upload_file(
                local_path, self.bucket, remote_path, ExtraArgs=extra_args
            )
            print(f"✅ Uploaded {local_path} to s3://{self.bucket}/{remote_path}")
            return True
        except FileNotFoundError:
            print(f"❌ File not found: {local_path}")
            return False
        except NoCredentialsError:
            print("❌ No valid credentials for S3")
            return False
        except ClientError as e:
            print(f"❌ S3 upload failed: {e}")
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from S3. Resolves deduplication pointers.

        Args:
            remote_path: S3 object key
            local_path: Destination path for downloaded file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Check for deduplication pointer first (Head Object)
            head = self.client.head_object(Bucket=self.bucket, Key=remote_path)
            metadata = head.get("Metadata", {})

            target_key = remote_path
            if "dedup_ref" in metadata:
                target_key = metadata["dedup_ref"]
                print(
                    f"🔗 Resolving deduplication pointer: {remote_path} -> {target_key}"
                )

            self.client.download_file(self.bucket, target_key, local_path)
            print(f"✅ Downloaded s3://{self.bucket}/{target_key} to {local_path}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print(f"❌ File not found in S3: {remote_path}")
            else:
                print(f"❌ S3 download failed: {e}")
            return False

    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[Dict]:
        """
        List files in S3 bucket with optional prefix

        Args:
            prefix: Filter by key prefix
            max_keys: Maximum number of keys to return

        Returns:
            List of file information dictionaries
        """

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=max_keys
            )

            if "Contents" not in response:
                return []

            files = []
            for obj in response["Contents"]:
                files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    }
                )

            return files
        except ClientError as e:
            print(f"❌ S3 list failed: {e}")
            return []

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3

        Args:
            s3_key: S3 object key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            print(f"✅ Deleted s3://{self.bucket}/{s3_key}")
            return True
        except ClientError as e:
            print(f"❌ S3 delete failed: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test S3 bucket connectivity and permissions

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to head the bucket
            self.client.head_bucket(Bucket=self.bucket)

            # Try to list objects (read permission)
            self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)

            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                print(f"❌ Bucket '{self.bucket}' not found")
            elif error_code == "403":
                print(f"❌ Access denied to bucket '{self.bucket}'")
            else:
                print(f"❌ Connection test failed: {e}")
            return False
        except NoCredentialsError:
            print("❌ No valid credentials")
            return False

    def get_file_info(self, s3_key: str) -> Optional[Dict]:
        """
        Get metadata about a specific file in S3

        Args:
            s3_key: S3 object key

        Returns:
            File info dictionary or None if not found
        """
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return {
                "key": s3_key,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"],
                "etag": response["ETag"].strip('"'),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            print(f"❌ Failed to get file info: {e}")
            return None
