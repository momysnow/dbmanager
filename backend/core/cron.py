import sys
from pathlib import Path
from typing import Any, Dict, List

import os
from crontab import CronTab

PYTHON_EXEC = sys.executable
# main.py lives at the repo root relative to this file.
MAIN_SCRIPT = str(Path(__file__).resolve().parent.parent / "main.py")


class CronManager:
    def __init__(self) -> None:
        self.cron = CronTab(user=True)

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs = []
        for job in self.cron:
            if "dbmanager-backup" in job.comment:
                db_id = job.comment.split(":")[-1]
                jobs.append(
                    {
                        "id": db_id,
                        "schedule": str(job.slices),
                        "command": job.command,
                        "enabled": job.is_enabled(),
                    }
                )
        return jobs

    def add_backup_job(self, db_id: int, schedule: str = "0 0 * * *") -> bool:
        # Remove existing job for this db
        self.remove_job(db_id)

        # Pass DBMANAGER_DATA_DIR explicitly if set in the environment.

        env_prefix = ""
        if os.environ.get("DBMANAGER_DATA_DIR"):
            env_prefix = f"DBMANAGER_DATA_DIR={os.environ['DBMANAGER_DATA_DIR']} "

        # We rely on absolute MAIN_SCRIPT to avoid cron working directory issues.

        command = (
            f"{env_prefix}{PYTHON_EXEC} {MAIN_SCRIPT} perform-backup --db-id {db_id}"
        )

        job = self.cron.new(command=command, comment=f"dbmanager-backup:{db_id}")
        job.setall(schedule)
        self.cron.write()
        return True

    def update_schedule(self, db_id: int, schedule: str) -> bool:
        """Update schedule for an existing job (or create if missing)."""
        self.remove_job(db_id)
        return self.add_backup_job(db_id, schedule)

    def set_job_enabled(self, db_id: int, enabled: bool) -> bool:
        """Enable or disable a job by db_id."""
        updated = False
        for job in self.cron:
            if job.comment == f"dbmanager-backup:{db_id}":
                if enabled:
                    job.enable(True)
                else:
                    job.enable(False)
                updated = True
        if updated:
            self.cron.write()
        return updated

    def remove_job(self, db_id: int) -> None:
        self.cron.remove_all(comment=f"dbmanager-backup:{db_id}")
        self.cron.write()
