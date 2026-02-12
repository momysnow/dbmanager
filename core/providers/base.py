from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..progress import BackupProgress


class BaseProvider(ABC):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def check_connection(self) -> bool:
        """Checks if the database is reachable."""
        raise NotImplementedError

    @abstractmethod
    def backup(
        self, backup_path: str, progress: Optional[BackupProgress] = None
    ) -> str:
        """
        Performs a backup and returns the path to the backup file.

        Args:
            backup_path: Directory where backup should be saved
            progress: Optional progress tracker for reporting status
        """
        raise NotImplementedError

    @abstractmethod
    def restore(
        self, backup_file: str, progress: Optional[BackupProgress] = None
    ) -> bool:
        """
        Restores the database from a backup file.

        Args:
            backup_file: Path to backup file
            progress: Optional progress tracker for reporting status
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        return str(self.config.get("name", "Unknown DB"))
