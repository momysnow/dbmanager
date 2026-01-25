import mysql.connector
import subprocess
import os
from datetime import datetime
from pathlib import Path
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

    def backup(self, backup_dir: str) -> str:
        params = self.config["params"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config['name']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)
        
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            "mysqldump",
            "-h", params["host"],
            "-P", str(params["port"]),
            "-u", params["user"],
            f"--password={params['password']}",
            params["database"],
            f"--result-file={filepath}"
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return filepath
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Backup failed: {e.stderr.decode()}")

    def restore(self, backup_file: str) -> bool:
        params = self.config["params"]
        
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
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Restore failed: {e.stderr.decode()}")
