import psycopg2
import subprocess
import os
from datetime import datetime
from pathlib import Path
from .base import BaseProvider

class PostgresProvider(BaseProvider):
    def check_connection(self) -> bool:
        params = self.config["params"]
        try:
            conn = psycopg2.connect(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                dbname=params["database"],
                connect_timeout=3
            )
            conn.close()
            return True
        except Exception:
            return False

    def backup(self, backup_dir: str) -> str:
        params = self.config["params"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config['name']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)
        
        # Ensure directory exists
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        cmd = [
            "pg_dump",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-F", "p", 
            "-f", filepath,
            params["database"]
        ]

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return filepath
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Backup failed: {e.stderr.decode()}")

    def restore(self, backup_file: str) -> bool:
        params = self.config["params"]
        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        cmd = [
            "psql",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-d", params["database"],
            "-f", backup_file
        ]

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Restore failed: {e.stderr.decode()}")
