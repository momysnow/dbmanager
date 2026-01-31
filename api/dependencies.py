"""Shared dependencies for API endpoints"""

from config import ConfigManager
from core.manager import DBManager

# Global instances
config_manager = ConfigManager()
db_manager = DBManager(config_manager)


def get_config_manager() -> ConfigManager:
    """Dependency to get ConfigManager instance"""
    return config_manager


def get_db_manager() -> DBManager:
    """Dependency to get DBManager instance"""
    return db_manager
