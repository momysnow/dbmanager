import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2

from .base import BaseProvider
from ..progress import BackupProgress


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
                connect_timeout=3,
            )
            conn.close()
            return True
        except Exception:
            return False

    def backup(self, backup_dir: str, progress: Optional[BackupProgress] = None) -> str:
        if progress:
            progress.start(f"Starting PostgreSQL backup for {self.name}")
            progress.set_steps(3)  # Prepare, Dump, Verify

        params = self.config["params"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use .dump extension for custom format (compressed)
        filename = f"{self.config['name']}_{timestamp}.dump"
        filepath = os.path.join(backup_dir, filename)

        # Step 1: Prepare
        if progress:
            progress.update(message="Preparing backup directory...", step="Preparing")

        # Ensure directory exists
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        if progress:
            progress.step_completed("Preparation complete")

        # Step 2: Dump database
        if progress:
            progress.update(
                message=f"Dumping database {params['database']}...", step="Dumping"
            )

        # Use custom format (-F c) for compression and better performance
        # This is the native PostgreSQL backup format
        cmd = [
            "pg_dump",
            "-h",
            params["host"],
            "-p",
            str(params["port"]),
            "-U",
            params["user"],
            "-F",
            "c",  # Custom format (compressed, native)
            "-f",
            filepath,
            params["database"],
            "--verbose",  # Show progress
        ]

        try:
            result = subprocess.run(
                cmd, env=env, check=False, capture_output=True, text=True
            )

            # pg_dump with -f may return exit code 0 even on auth/connection errors
            # Always check stderr for fatal errors AND file size
            if result.returncode != 0 or (
                result.stderr and "error:" in result.stderr.lower()
            ):
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"pg_dump exited with code {result.returncode}"
                )
                if progress:
                    progress.fail(f"pg_dump failed: {error_msg}")
                raise RuntimeError(f"Backup failed: {error_msg}")

            if progress:
                progress.step_completed("Database dumped")

            # Step 3: Verify the backup file was created and has content
            if progress:
                progress.update(message="Verifying backup file...", step="Verifying")

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                # Try to get error from stderr
                error_detail = (
                    result.stderr.strip() if result.stderr else "unknown error"
                )
                # Clean up empty file
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                if progress:
                    progress.fail("Backup file was not created or is empty")
                raise RuntimeError(
                    f"Backup file is empty (pg_dump may have failed silently): {error_detail}"
                )

            if progress:
                progress.step_completed("Verification complete")
                progress.complete(f"Backup completed: {filename}")

            return filepath
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            if progress:
                progress.fail(f"pg_dump failed: {error_msg}")
            raise RuntimeError(f"Backup failed: {error_msg}")

    def verify_backup(self, backup_file: str) -> bool:
        """Verify the integrity of a PostgreSQL backup file"""
        params = self.config["params"]
        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        # Use pg_restore with --list to verify the backup
        cmd = ["pg_restore", "--list", backup_file]

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def restore(
        self, backup_file: str, progress: Optional[BackupProgress] = None
    ) -> bool:
        if progress:
            progress.start(f"Starting PostgreSQL restore for {self.name}")
            progress.set_steps(3)  # Detect format, Restore, Verify

        params = self.config["params"]
        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        # Step 1: Auto-detect format
        if progress:
            progress.update(message="Detecting backup format...", step="Detecting")

        is_custom_format = backup_file.endswith(".dump")

        if progress:
            format_type = "custom (compressed)" if is_custom_format else "plain SQL"
            progress.step_completed(f"Format detected: {format_type}")

        # Step 2: Restore database
        if progress:
            progress.update(
                message=f"Restoring database {params['database']}...", step="Restoring"
            )

        if is_custom_format:
            # Use pg_restore for custom format
            cmd = [
                "pg_restore",
                "-h",
                params["host"],
                "-p",
                str(params["port"]),
                "-U",
                params["user"],
                "-d",
                params["database"],
                "--clean",  # Drop existing objects before restore
                "--if-exists",  # Don't error if objects don't exist
                "--verbose",  # Show progress
                backup_file,
            ]
        else:
            # Use psql for plain SQL files
            cmd = [
                "psql",
                "-h",
                params["host"],
                "-p",
                str(params["port"]),
                "-U",
                params["user"],
                "-d",
                params["database"],
                "-f",
                backup_file,
            ]

        try:
            result = subprocess.run(
                cmd, env=env, check=False, capture_output=True, text=True
            )

            # pg_restore may report warnings like "transaction_timeout" which are not fatal
            stderr_lower = result.stderr.lower() if result.stderr else ""

            # Fatal errors that usually indicate the restore completely failed
            # Skip "could not" since it matches non-fatal "could not execute query" for transaction_timeout
            # Skip "does not exist" since it matches non-fatal drops for --clean
            fatal_errors = [
                "password authentication failed",
                "connection refused",
                "fatal:",
            ]
            has_fatal_error = any(err in stderr_lower for err in fatal_errors)

            # If pg_restore explicitly says it ignored errors, it's usually a successful restore
            # despite version incompatibilities (like SET transaction_timeout) or missing objects to drop
            errors_ignored = "errors ignored on restore" in stderr_lower

            if result.returncode != 0:
                if has_fatal_error or not errors_ignored:
                    error_msg = (
                        result.stderr.strip()
                        if result.stderr
                        else f"pg_restore exited with code {result.returncode}"
                    )
                    if progress:
                        progress.fail(f"Restore failed: {error_msg}")
                    raise RuntimeError(f"Restore failed: {error_msg}")
                else:
                    # Has errors but it ignored them and completed
                    if progress:
                        progress.step_completed("Database restored (with warnings)")
                        progress.complete(
                            f"Restore completed with warnings: {result.stderr.strip()[:200]}"
                        )
                    return True

            if progress:
                progress.step_completed("Database restored")
                progress.complete("Restore completed successfully")

            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if hasattr(e.stderr, "decode") else str(e)
            if progress:
                progress.fail(f"Restore failed: {error_msg}")
            raise RuntimeError(f"Restore failed: {error_msg}")
