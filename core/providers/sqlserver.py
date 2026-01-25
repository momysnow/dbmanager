import pymssql
import subprocess
import os
from datetime import datetime
from pathlib import Path
from .base import BaseProvider

class SQLServerProvider(BaseProvider):
    def check_connection(self) -> bool:
        params = self.config["params"]
        try:
            conn = pymssql.connect(
                server=params["host"],
                port=int(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
                timeout=3
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

        env = os.environ.copy()
        env["MSSQL_SCRIPTER_PASSWORD"] = params["password"]

        cmd = [
            "mssql-scripter",
            "-S", f"{params['host']},{params['port']}",
            "-U", params["user"],
            "-d", params["database"],
            "--schema-and-data",
            "-f", filepath
        ]

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return filepath
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Backup failed (mssql-scripter): {e.stderr.decode() if e.stderr else 'Unknown error'}")

    def restore(self, backup_file: str) -> bool:
        params = self.config["params"]
        env = os.environ.copy()
        env["SQLCMDPASSWORD"] = params["password"]

        cmd = [
            "sqlcmd",
            "-S", f"{params['host']},{params['port']}",
            "-U", params["user"],
            "-d", params["database"],
            "-i", backup_file
        ]

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Restore failed using sqlcmd. Ensure sqlcmd is installed. Error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
