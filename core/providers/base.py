from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def check_connection(self) -> bool:
        """Checks if the database is reachable."""
        pass

    @abstractmethod
    def backup(self, backup_path: str) -> str:
        """Performs a backup and returns the path to the backup file."""
        pass

    @abstractmethod
    def restore(self, backup_file: str) -> bool:
        """Restores the database from a backup file."""
        pass
    
    @property
    def name(self):
        return self.config.get("name", "Unknown DB")
