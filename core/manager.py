from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Type
from config import ConfigManager, CONFIG_DIR
from .providers.base import BaseProvider
from .providers.postgres import PostgresProvider
from .providers.mysql import MySQLProvider
from .providers.sqlserver import SQLServerProvider
# from .providers.sqlite import SQLiteProvider # To be implemented

BACKUP_ROOT = CONFIG_DIR / "backups"

class DBManager:
    def __init__(self):
        self.config_manager = ConfigManager()
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
                       connection_params: Dict[str, Any], retention: int = 0):
        if provider_type not in self.providers:
            raise ValueError(f"Provider {provider_type} not supported.")
        
        db_config = {
            "name": name,
            "provider": provider_type,
            "params": connection_params,
            # "backup_type": "full", # Implicit default
            "retention": retention
        }
        return self.config_manager.update_database(db_id, db_config)

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
        # backup_type = db_config.get("backup_type", "full") # Deprecated, assuming full
        retention = int(db_config.get("retention", 0)) # 0 = infinite

        # Run backup
        path = provider.backup(str(backup_dir))

        # Handle retention
        if retention > 0:
            self._enforce_retention(db_id, retention)
            
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

