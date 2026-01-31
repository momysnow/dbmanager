"""MongoDB database provider"""

import subprocess
from pathlib import Path
from typing import Optional
from .base import BaseProvider


class MongoDBProvider(BaseProvider):
    """MongoDB backup and restore provider using mongodump/mongorestore"""
    
    def __init__(self, db_config: dict):
        super().__init__(db_config)
        
        # MongoDB can use URI or individual params
        self.uri = db_config.get("uri")  # Optional: mongodb://user:pass@host:port/db
        
        if not self.uri:
            # Build connection from individual params
            auth_str = ""
            if self.username and self.password:
                auth_str = f"{self.username}:{self.password}@"
            
            self.uri = f"mongodb://{auth_str}{self.host}:{self.port}/{self.database}"
    
    def test_connection(self) -> bool:
        """Test MongoDB connection"""
        try:
            # Use mongosh or mongo to test connection
            cmd = [
                "mongosh" if self._has_mongosh() else "mongo",
                self.uri,
                "--quiet",
                "--eval",
                "db.adminCommand('ping')"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.returncode == 0
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def _has_mongosh(self) -> bool:
        """Check if mongosh (new shell) is available"""
        try:
            subprocess.run(["mongosh", "--version"], capture_output=True, timeout=5)
            return True
        except:
            return False
    
    def backup(self, backup_dir: str, progress: Optional['BackupProgress'] = None) -> str:
        """
        Backup MongoDB database using mongodump
        
        Creates a BSON dump of the database
        """
        from datetime import datetime
        
        if progress:
            progress.update(0, 100, "Starting MongoDB backup...")
        
        # Create backup directory
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate backup directory name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.database}_{timestamp}"
        output_dir = Path(backup_dir) / backup_name
        
        if progress:
            progress.update(20, 100, "Running mongodump...")
        
        # Build mongodump command
        cmd = [
            "mongodump",
            f"--uri={self.uri}",
            f"--out={output_dir}",
            "--gzip"  # Compress output
        ]
        
        # Run mongodump
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"mongodump failed: {result.stderr}")
            
            if progress:
                progress.update(90, 100, "Creating archive...")
            
            # Create tar.gz archive of the dump
            import tarfile
            archive_path = Path(backup_dir) / f"{backup_name}.tar.gz"
            
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(output_dir, arcname=backup_name)
            
            # Remove temporary directory
            import shutil
            shutil.rmtree(output_dir)
            
            if progress:
                progress.update(100, 100, "Backup completed")
            
            return str(archive_path)
        
        except subprocess.TimeoutExpired:
            raise Exception("Backup timeout (>1 hour)")
        except Exception as e:
            # Cleanup on error
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
            raise
    
    def restore(self, backup_file: str, progress: Optional['BackupProgress'] = None) -> bool:
        """
        Restore MongoDB database using mongorestore
        
        Restores from a mongodump archive
        """
        import tarfile
        import tempfile
        import shutil
        
        if progress:
            progress.update(0, 100, "Starting MongoDB restore...")
        
        try:
            # Extract archive to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                if progress:
                    progress.update(20, 100, "Extracting backup archive...")
                
                # Extract tar.gz
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(temp_path)
                
                # Find the dump directory
                dump_dirs = list(temp_path.iterdir())
                if not dump_dirs:
                    raise Exception("No dump directory found in archive")
                
                dump_dir = dump_dirs[0]
                
                if progress:
                    progress.update(50, 100, "Running mongorestore...")
                
                # Build mongorestore command
                cmd = [
                    "mongorestore",
                    f"--uri={self.uri}",
                    "--gzip",
                    "--drop",  # Drop collections before restoring
                    str(dump_dir)
                ]
                
                # Run mongorestore
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600
                )
                
                if result.returncode != 0:
                    raise Exception(f"mongorestore failed: {result.stderr}")
                
                if progress:
                    progress.update(100, 100, "Restore completed")
                
                return True
        
        except subprocess.TimeoutExpired:
            raise Exception("Restore timeout (>1 hour)")
        except Exception as e:
            if progress:
                progress.update(0, 100, f"Restore failed: {e}")
            raise
