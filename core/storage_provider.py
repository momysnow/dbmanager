"""
Storage Provider Interface
Abstract base class for all storage providers (S3, SMB, etc.)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageProvider(ABC):
    """
    Abstract base class for storage providers
    Defines the interface that all storage implementations must follow
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize storage provider

        Args:
            config: Configuration dictionary specific to the provider
        """
        self.config = config

    @abstractmethod
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict] = None,
        dedup_ref_key: Optional[str] = None,
    ) -> bool:
        """
        Upload a file to remote storage

        Args:
            local_path: Path to local file
            remote_path: Destination path in remote storage
            metadata: Optional metadata to attach (if supported)
            dedup_ref_key: Optional key for deduplication reference

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from remote storage

        Args:
            remote_path: Path to file in remote storage
            local_path: Destination path for downloaded file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[Dict]:
        """
        List files in remote storage

        Args:
            prefix: Filter by path prefix
            max_keys: Maximum number of items to return

        Returns:
            List of dictionaries containing file info:
            {
                "key": str,
                "size": int,
                "last_modified": datetime,
                "metadata": dict (optional)
            }
        """
        pass

    @abstractmethod
    def delete_file(self, remote_path: str) -> bool:
        """
        Delete a file from remote storage

        Args:
            remote_path: Path to file to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection and permissions

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_file_info(self, remote_path: str) -> Optional[Dict]:
        """
        Get metadata about a specific file

        Args:
            remote_path: Path to file in remote storage

        Returns:
            Dictionary with file info or None if not found
        """
        pass
