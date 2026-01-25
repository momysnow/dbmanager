import os
from crontab import CronTab
import sys
from pathlib import Path
from config import CONFIG_DIR

# We need the executable to run main.py
PYTHON_EXEC = sys.executable
# Assuming main.py is in the parent directory of this file's package (core) -> dbmanager/main.py
# But we are running from root now in the refactored version.
# Adjust MAIN_SCRIPT path logic.
# If __file__ is core/cron.py, then parent is core, parent.parent is root.
MAIN_SCRIPT = str(Path(__file__).resolve().parent.parent / "main.py")

class CronManager:
    def __init__(self):
        self.cron = CronTab(user=True)

    def list_jobs(self):
        jobs = []
        for job in self.cron:
            if "dbmanager-backup" in job.comment:
                db_id = job.comment.split(":")[-1]
                jobs.append({
                    "id": db_id,
                    "schedule": str(job.slices),
                    "command": job.command,
                    "enabled": job.is_enabled()
                })
        return jobs

    def add_backup_job(self, db_id: int, schedule: str = "0 0 * * *"):
        # Remove existing job for this db
        self.remove_job(db_id)
        
        # Pass the CONFIG_DIR environment variable explicitly
        data_dir = str(CONFIG_DIR.parent) # Assuming CONFIG_DIR is .../data/.dbmanager or similar? 
        # Actually CONFIG_DIR is defined in config.py as Path(os.getenv("DBMANAGER_DATA_DIR", ...))
        # If running in Docker, DBMANAGER_DATA_DIR=/app/data.
        # We should capture the current environment variable or the resolved path.
        
        # Let's use the resolved CONFIG_DIR root.
        # But wait, CONFIG_DIR is where config.json lives. 
        # If we just pass DBMANAGER_DATA_DIR env var if set.
        
        env_prefix = ""
        if os.environ.get("DBMANAGER_DATA_DIR"):
            env_prefix = f"DBMANAGER_DATA_DIR={os.environ['DBMANAGER_DATA_DIR']} "
        
        # Also need to ensure we run from the correct working directory or use absolute paths?
        # Docker CMD: workdir is /app. main.py is in /app/main.py.
        # Cron runs in /root usually.
        # Safest is to cd to /app first (if in docker) or project root.
        # Let's try to detect if we are in docker by checking /app existence or just relying on MAIN_SCRIPT path.
        
        command = f"{env_prefix}{PYTHON_EXEC} {MAIN_SCRIPT} perform-backup --db-id {db_id}"
        
        job = self.cron.new(command=command, comment=f"dbmanager-backup:{db_id}")
        job.setall(schedule)
        self.cron.write()
        return True

    def remove_job(self, db_id: int):
        self.cron.remove_all(comment=f"dbmanager-backup:{db_id}")
        self.cron.write()
