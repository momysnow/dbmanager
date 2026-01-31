"""SQLite database provider"""

import subprocess
from pathlib import Path
from typing import Optional
from .base import BaseProvider


class SQLiteProvider(BaseProvider):
    """SQLite backup and restore provider"""
    
    def __init__(self, db_config: dict):
        super().__init__(db_config)
        self.db_file = db_config.get("database")  # SQLite uses database field for file path
    
    def test_connection(self) -> bool:
        """Test if SQLite database file exists and is valid"""
        try:
            db_path = Path(self.db_file)
            
            if not db_path.exists():
                return False
            
            # Try to open with sqlite3
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
            cursor.fetchone()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def backup(self, backup_dir: str, progress: Optional['BackupProgress'] = None) -> str:
        """
        Backup SQLite database
        
        Uses .backup command for consistent backup
        """
        from datetime import datetime
        import shutil
        
        if progress:
            progress.update(0, 100, "Starting SQLite backup...")
        
        # Create backup directory
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = Path(self.db_file).stem
        backup_file = Path(backup_dir) / f"{db_name}_{timestamp}.sqlite"
        
        if progress:
            progress.update(20, 100, "Copying database file...")
        
        # Method 1: Use sqlite3 .backup command (recommended)
        try:
            import sqlite3
            
            # Open source database
            source_conn = sqlite3.connect(self.db_file)
            
            # Open destination database
            dest_conn = sqlite3.connect(str(backup_file))
            
            # Perform backup
            with dest_conn:
                source_conn.backup(dest_conn)
            
            source_conn.close()
            dest_conn.close()
            
            if progress:
                progress.update(100, 100, "Backup completed")
            
            return str(backup_file)
        
        except Exception as e:
            # Fallback: Simple file copy
            if progress:
                progress.update(50, 100, f"Using file copy method... ({e})")
            
            shutil.copy2(self.db_file, backup_file)
            
            if progress:
                progress.update(100, 100, "Backup completed (file copy)")
            
            return str(backup_file)
    
    def restore(self, backup_file: str, progress: Optional['BackupProgress'] = None) -> bool:
        """
        Restore SQLite database from backup
        
        WARNING: This will overwrite the current database file
        """
        import shutil
        
        if progress:
            progress.update(0, 100, "Starting SQLite restore...")
        
        try:
            # Backup current file first
            if Path(self.db_file).exists():
                backup_current = f"{self.db_file}.before_restore"
                shutil.copy2(self.db_file, backup_current)
                
                if progress:
                    progress.update(30, 100, f"Current database backed up to {backup_current}")
            
            if progress:
                progress.update(50, 100, "Restoring database...")
            
            # Copy backup to database location
            shutil.copy2(backup_file, self.db_file)
            
            if progress:
                progress.update(90, 100, "Verifying restored database...")
            
            # Verify restored database
            if not self.test_connection():
                raise Exception("Restored database verification failed")
            
            if progress:
                progress.update(100, 100, "Restore completed")
            
            return True
        
        except Exception as e:
            if progress:
                progress.update(0, 100, f"Restore failed: {e}")
            raise
