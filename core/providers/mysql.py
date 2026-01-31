import mysql.connector
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from .base import BaseProvider

class MySQLProvider(BaseProvider):
    def check_connection(self) -> bool:
        params = self.config["params"]
        try:
            conn = mysql.connector.connect(
                host=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
                connection_timeout=3
            )
            conn.close()
            return True
        except Exception:
            return False

    def backup(self, backup_dir: str, progress: Optional['BackupProgress'] = None) -> str:
        if progress:
            progress.start(f"Starting MySQL backup for {self.name}")
            progress.set_steps(2)  # Dump, Verify
        
        params = self.config["params"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config['name']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)
        
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        if progress:
            progress.update(message=f"Dumping database {params['database']}...", step="Dumping")

        # Complete mysqldump with all database objects
        cmd = [
            "mysqldump",
            "-h", params["host"],
            "-P", str(params["port"]),
            "-u", params["user"],
            f"--password={params['password']}",
            params["database"],
            "--result-file", filepath,
            # Advanced options for complete backup
            "--single-transaction",  # Consistent snapshot without locking tables
            "--routines",  # Include stored procedures and functions
            "--triggers",  # Include triggers
            "--events",  # Include scheduled events
            "--add-drop-database",  # Add DROP DATABASE before CREATE
            "--add-drop-table",  # Add DROP TABLE before CREATE
            "--create-options",  # Include all CREATE TABLE options
            "--extended-insert",  # Use multi-row INSERT (faster restore)
            "--set-charset",  # Add SET NAMES to output
            "--comments",  # Add informational comments
            "--dump-date"  # Add dump date as comment
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            if progress:
                progress.step_completed("Database dumped")
            
            # Verify the backup file was created and has content
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                if progress:
                    progress.fail("Backup file was not created or is empty")
                raise RuntimeError(f"Backup file was not created or is empty: {filepath}")
            
            if progress:
                progress.step_completed("Verification complete")
                progress.complete(f"Backup completed: {filename}")
            
            return filepath
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            if progress:
                progress.fail(f"mysqldump failed: {error_msg}")
            raise RuntimeError(f"Backup failed: {error_msg}")
    
    def verify_backup(self, backup_file: str) -> bool:
        """Verify the integrity of a MySQL backup file"""
        # Check if file exists and is valid SQL
        try:
            with open(backup_file, 'r') as f:
                content = f.read(1000)  # Read first 1000 chars
                # Check for MySQL dump header
                if '-- MySQL dump' in content or 'CREATE TABLE' in content:
                    return True
            return False
        except Exception:
            return False

    def restore(self, backup_file: str, progress: Optional['BackupProgress'] = None) -> bool:
        if progress:
            progress.start(f"Starting MySQL restore for {self.name}")
            progress.set_steps(1)  # Restore
        
        params = self.config["params"]
        
        if progress:
            progress.update(message=f"Restoring database {params['database']}...", step="Restoring")
        
        # MySQL/MariaDB consume dump via stdin
        cmd = [
            "mysql",
            "-h", params["host"],
            "-P", str(params["port"]),
            "-u", params["user"],
            f"--password={params['password']}",
            params["database"]
        ]

        try:
            with open(backup_file, "r") as f:
                subprocess.run(cmd, stdin=f, check=True, capture_output=True)
            
            if progress:
                progress.step_completed("Database restored")
                progress.complete("Restore completed successfully")
            
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e)
            if progress:
                progress.fail(f"Restore failed: {error_msg}")
            raise RuntimeError(f"Restore failed: {error_msg}")
