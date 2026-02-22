import io
import os
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pymssql

from .base import BaseProvider
from ..progress import BackupProgress


class SQLServerProvider(BaseProvider):
    def check_connection(self) -> bool:
        params = self.config["params"]
        try:
            conn = pymssql.connect(
                server=params["host"],
                port=str(params["port"]),
                user=params["user"],
                password=params["password"],
                database=params["database"],
                timeout=3,
            )
            conn.close()
            return True
        except Exception:
            return False

    def _can_use_mssql_scripter(self) -> bool:
        """Check if mssql-scripter is available (works on x86/AMD64, not ARM)"""
        try:
            result = subprocess.run(
                ["mssql-scripter", "--version"], capture_output=True, timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    def _can_use_docker_api(self) -> bool:
        """Check if SQL Server is accessible as a Docker container"""
        try:
            import docker

            client = docker.from_env()

            # Try to get container by name (host might be container name)
            container_name = self.config["params"]["host"]
            try:
                container = client.containers.get(container_name)
                is_running = container.status == "running"

                if not is_running:
                    print(
                        f"[DEBUG] Docker API: Container '{container_name}' not running "
                        f"(status: {container.status})"
                    )
                    return False

                # Test if we can actually execute commands (network connectivity)
                try:
                    exit_code, output = container.exec_run("echo test")
                    if exit_code == 0:
                        print(
                            f"[DEBUG] Docker API: Container '{container_name}' "
                            "accessible ✅"
                        )
                        return True
                    else:
                        print(
                            f"[DEBUG] Docker API: Container '{container_name}' "
                            f"not executable (exit: {exit_code})"
                        )
                        return False
                except Exception as e:
                    print(
                        f"[DEBUG] Docker API: Container '{container_name}' exec failed "
                        f"- {e}"
                    )
                    return False

            except Exception as e:
                print(
                    f"[DEBUG] Docker API: Container '{container_name}' not found "
                    f"- {type(e).__name__}"
                )
                # Container not found by name, can't use Docker API
                return False
        except Exception as e:
            print(f"[DEBUG] Docker API unavailable: {type(e).__name__}")
            # Docker not available or other error
            return False

    def backup(
        self,
        backup_dir: str,
        progress: Optional[BackupProgress] = None,
        backup_type: str = "full",
    ) -> str:
        """
        Triple-priority backup strategy (ordered by completeness):
        1. mssql-scripter (BEST - complete schema+data, works on x86/AMD64)
        2. Native .bak via Docker API (GOOD - native format, requires local container)
        3. sqlcmd script (FALLBACK - basic but universal)

        Args:
            backup_type: 'full' or 'differential' (Only supported by Native .bak method)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Priority 1: mssql-scripter (most complete)
        # Does NOT support differential. Proceed only if backup_type is full.
        if backup_type == "full" and self._can_use_mssql_scripter():
            try:
                print("Using mssql-scripter (complete backup with all objects)")
                return self._backup_mssql_scripter(backup_dir, timestamp)
            except Exception as e:
                print(f"mssql-scripter failed ({e}), trying Docker API...")
        elif backup_type != "full":
            print(f"mssql-scripter skipped (does not support {backup_type})")

        # Priority 2: Docker API for native .bak
        # Supports DIFFERENTIAL
        if self._can_use_docker_api():
            try:
                print(f"Using Docker API (native .bak format, type={backup_type})")
                return self._backup_native_bak(
                    backup_dir, timestamp, differential=(backup_type == "differential")
                )
            except Exception as e:
                print(f"Docker API failed ({e}), using sqlcmd fallback...")

        # Priority 3: sqlcmd fallback (basic but works everywhere)
        # Does NOT support differential
        if backup_type == "full":
            print("Using sqlcmd fallback (basic schema+data)")
            return self._backup_sql_script(backup_dir, timestamp)
        else:
            raise ValueError(
                "Differential backup is only supported via Native .bak (Docker) method."
            )

    def _backup_mssql_scripter(self, backup_dir: str, timestamp: str) -> str:
        """Complete backup using mssql-scripter (includes all objects)"""
        params = self.config["params"]
        filename = f"{self.config['name']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)

        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # mssql-scripter requires password via stdin
        cmd = [
            "mssql-scripter",
            "-S",
            f"{params['host']},{params['port']}",
            "-U",
            params["user"],
            "-d",
            params["database"],
            "-P",
            params["password"],  # Pass password directly
            "--schema-and-data",  # Include both schema and data
            "--script-create",  # CREATE statements
            "-f",
            filepath,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            # Verify backup was created
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise RuntimeError(
                    f"Backup file was not created or is empty: {filepath}"
                )

            return filepath
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"mssql-scripter backup failed: {error_msg}")

    def _backup_native_bak(
        self, backup_dir: str, timestamp: str, differential: bool = False
    ) -> str:
        """Native .bak backup using Docker API"""
        import docker
        import tarfile
        import io

        params = self.config["params"]
        suffix = "_diff.bak" if differential else ".bak"
        filename = f"{self.config['name']}_{timestamp}{suffix}"
        filepath = os.path.join(backup_dir, filename)

        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Get Docker container
        client = docker.from_env()
        container = client.containers.get(params["host"])

        # SQL Server internal path for backup
        backup_path_in_container = f"/tmp/{filename}"

        # Construct Query
        type_clause = "WITH DIFFERENTIAL," if differential else "WITH"
        # Always use FORMAT/COMPRESSION for full.
        # For differential, usually just DIFFERENTIAL argument in T-SQL:
        # BACKUP DATABASE db TO DISK = '...' WITH DIFFERENTIAL

        backup_query = (
            f"BACKUP DATABASE [{params['database']}] "
            f"TO DISK = N'{backup_path_in_container}' "
            f"{type_clause} COMPRESSION, STATS = 10;"
        )

        # Get trust certificate setting (default: true)
        trust_cert = params.get("trust_certificate", True)

        cmd = [
            "/opt/mssql-tools18/bin/sqlcmd",
            "-S",
            "localhost",
            "-U",
            params["user"],
            "-P",
            params["password"],
        ]

        if trust_cert:
            cmd.append("-C")  # Trust server certificate

        cmd.extend(["-Q", backup_query, "-b"])  # Exit with error code on failure

        # Execute backup command inside SQL Server container
        exit_code, output = container.exec_run(cmd)

        if exit_code != 0:
            raise RuntimeError(f"Backup failed: {output.decode()}")

        # Copy backup file from container using Docker API
        bits, stat = container.get_archive(backup_path_in_container)

        # Extract tar archive to get the actual .bak file
        file_obj = io.BytesIO()
        for chunk in bits:
            file_obj.write(chunk)
        file_obj.seek(0)

        # Extract from tar
        with tarfile.open(fileobj=file_obj) as tar:
            member = tar.getmembers()[0]
            source = tar.extractfile(member)
            if source is None:
                raise RuntimeError("Failed to extract backup file from archive")
            with source:
                with open(filepath, "wb") as target:
                    target.write(source.read())

        # Clean up backup file in container
        try:
            container.exec_run(f"rm {backup_path_in_container}")
        except Exception:
            pass

        # Verify backup was created
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise RuntimeError(f"Backup file was not created or is empty: {filepath}")

        return filepath

    def _backup_sql_script(self, backup_dir: str, timestamp: str) -> str:
        """
        Complete SQL script generation including ALL database objects:
        - Tables (with proper constraints, keys, indexes)
        - Stored Procedures
        - Functions
        - Views
        - Triggers
        - Data
        """
        params = self.config["params"]
        filename = f"{self.config['name']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)

        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Connect and generate SQL script
        conn = pymssql.connect(
            server=params["host"],
            port=str(params["port"]),
            user=params["user"],
            password=params["password"],
            database=params["database"],
        )
        cursor = conn.cursor()

        with open(filepath, "w", encoding="utf-8") as f:
            # Write header
            f.write("-- ==========================================================\n")
            f.write("-- SQL Server Complete Backup Script\n")
            f.write(f"-- Database: {params['database']}\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Server: {params['host']}:{params['port']}\n")
            f.write("-- ==========================================================\n\n")
            f.write(f"USE [{params['database']}];\nGO\n\n")

            # 1. EXPORT STORED PROCEDURES
            f.write("-- ==========================================================\n")
            f.write("-- STORED PROCEDURES\n")
            f.write("-- ==========================================================\n\n")
            cursor.execute(
                """
                SELECT OBJECT_SCHEMA_NAME(object_id) AS schema_name,
                       name AS procedure_name,
                       OBJECT_DEFINITION(object_id) AS definition
                FROM sys.procedures
                WHERE is_ms_shipped = 0
                ORDER BY schema_name, procedure_name
            """
            )
            procedures = cursor.fetchall() or []
            for schema, name, definition in procedures:
                if definition:
                    f.write(f"\n-- Procedure: [{schema}].[{name}]\n")
                    f.write(f"IF OBJECT_ID('[{schema}].[{name}]', 'P') IS NOT NULL\n")
                    f.write(f"    DROP PROCEDURE [{schema}].[{name}];\nGO\n\n")
                    f.write(f"{definition}\nGO\n\n")

            # 2. EXPORT FUNCTIONS
            f.write("-- ==========================================================\n")
            f.write("-- FUNCTIONS\n")
            f.write("-- ==========================================================\n\n")
            cursor.execute(
                """
                SELECT OBJECT_SCHEMA_NAME(object_id) AS schema_name,
                       name AS function_name,
                       OBJECT_DEFINITION(object_id) AS definition
                FROM sys.objects
                WHERE type IN ('FN', 'IF', 'TF')  -- Scalar, Inline, Table functions
                  AND is_ms_shipped = 0
                ORDER BY schema_name, function_name
            """
            )
            functions = cursor.fetchall() or []
            for schema, name, definition in functions:
                if definition:
                    f.write(f"\n-- Function: [{schema}].[{name}]\n")
                    f.write(f"IF OBJECT_ID('[{schema}].[{name}]', 'FN') IS NOT NULL\n")
                    f.write(f"    DROP FUNCTION [{schema}].[{name}];\nGO\n\n")
                    f.write(f"{definition}\nGO\n\n")

            # 3. EXPORT VIEWS
            f.write("-- ==========================================================\n")
            f.write("-- VIEWS\n")
            f.write("-- ==========================================================\n\n")
            cursor.execute(
                """
                SELECT OBJECT_SCHEMA_NAME(object_id) AS schema_name,
                       name AS view_name,
                       OBJECT_DEFINITION(object_id) AS definition
                FROM sys.views
                WHERE is_ms_shipped = 0
                ORDER BY schema_name, view_name
            """
            )
            views = cursor.fetchall() or []
            for schema, name, definition in views:
                if definition:
                    f.write(f"\n-- View: [{schema}].[{name}]\n")
                    f.write(f"IF OBJECT_ID('[{schema}].[{name}]', 'V') IS NOT NULL\n")
                    f.write(f"    DROP VIEW [{schema}].[{name}];\nGO\n\n")
                    f.write(f"{definition}\nGO\n\n")

            # 4. EXPORT TABLES (Schema + Data)
            f.write("-- ==========================================================\n")
            f.write("-- TABLES & DATA\n")
            f.write("-- ==========================================================\n\n")

            cursor.execute(
                """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                  AND TABLE_SCHEMA != 'sys'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            )
            tables = cursor.fetchall() or []

            for schema, table in tables:
                f.write(f"\n-- Table: [{schema}].[{table}]\n")

                # Drop existing table
                f.write(f"IF OBJECT_ID('[{schema}].[{table}]', 'U') IS NOT NULL\n")
                f.write(f"    DROP TABLE [{schema}].[{table}];\nGO\n\n")

                # Get column definitions
                cursor.execute(
                    f"""
                    SELECT
                        c.COLUMN_NAME,
                        c.DATA_TYPE,
                        c.CHARACTER_MAXIMUM_LENGTH,
                        c.NUMERIC_PRECISION,
                        c.NUMERIC_SCALE,
                        c.IS_NULLABLE,
                        c.COLUMN_DEFAULT,
                        COLUMNPROPERTY(
                            OBJECT_ID('[{schema}].[{table}]'),
                            c.COLUMN_NAME,
                            'IsIdentity'
                        ) AS is_identity
                    FROM INFORMATION_SCHEMA.COLUMNS c
                    WHERE c.TABLE_SCHEMA = '{schema}' AND c.TABLE_NAME = '{table}'
                    ORDER BY c.ORDINAL_POSITION
                """
                )
                columns = cursor.fetchall() or []

                f.write(f"CREATE TABLE [{schema}].[{table}] (\n")
                col_defs = []
                for (
                    col_name,
                    data_type,
                    max_len,
                    num_prec,
                    num_scale,
                    nullable,
                    default,
                    is_identity,
                ) in columns:
                    col_def = f"    [{col_name}] {data_type.upper()}"

                    # Add length/precision
                    if max_len and data_type.lower() in (
                        "varchar",
                        "nvarchar",
                        "char",
                        "nchar",
                        "varbinary",
                        "binary",
                    ):
                        col_def += f"({max_len if max_len != -1 else 'MAX'})"
                    elif num_prec and data_type.lower() in ("decimal", "numeric"):
                        col_def += f"({num_prec},{num_scale or 0})"

                    # Identity column
                    if is_identity:
                        col_def += " IDENTITY(1,1)"

                    # Nullable
                    col_def += " NULL" if nullable == "YES" else " NOT NULL"

                    # Default value
                    if default:
                        col_def += f" DEFAULT {default}"

                    col_defs.append(col_def)

                f.write(",\n".join(col_defs))
                f.write("\n);\nGO\n\n")

                # Get column names for INSERT
                cursor.execute(
                    f"""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
                    ORDER BY ORDINAL_POSITION
                """
                )
                columns = [row[0] for row in (cursor.fetchall() or [])]
                column_list = ", ".join(f"[{col}]" for col in columns)

                # Export data
                cursor.execute(f"SELECT * FROM [{schema}].[{table}]")
                rows = cursor.fetchall() or []

                if rows:
                    f.write(f"-- Data for [{schema}].[{table}] ({len(rows)} rows)\n")
                    f.write(f"SET IDENTITY_INSERT [{schema}].[{table}] ON;\n")

                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, str):
                                escaped_val = val.replace("'", "''")
                                values.append(f"'{escaped_val}'")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, datetime):
                                values.append(f"'{val.isoformat()}'")
                            else:
                                values.append(f"'{str(val)}'")

                        insert_stmt = (
                            f"INSERT INTO [{schema}].[{table}] "
                            f"({column_list}) VALUES ({', '.join(values)});\n"
                        )
                        f.write(insert_stmt)

                    f.write(f"SET IDENTITY_INSERT [{schema}].[{table}] OFF;\nGO\n\n")

            # 5. EXPORT TRIGGERS
            f.write("-- ==========================================================\n")
            f.write("-- TRIGGERS\n")
            f.write("-- ==========================================================\n\n")
            cursor.execute(
                """
                SELECT OBJECT_SCHEMA_NAME(parent_id) AS schema_name,
                       OBJECT_NAME(parent_id) AS table_name,
                       name AS trigger_name,
                       OBJECT_DEFINITION(object_id) AS definition
                FROM sys.triggers
                WHERE is_ms_shipped = 0
                  AND parent_class = 1  -- Table triggers only
                ORDER BY schema_name, table_name, trigger_name
            """
            )
            triggers = cursor.fetchall() or []
            for schema, table, name, definition in triggers:
                if definition:
                    f.write(f"\n-- Trigger: [{name}] on [{schema}].[{table}]\n")
                    f.write(f"{definition}\nGO\n\n")

            f.write("\n-- ==========================================================\n")
            f.write("-- Backup completed successfully\n")
            f.write("-- ==========================================================\n")

        cursor.close()
        conn.close()

        # Verify backup was created
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise RuntimeError(f"Backup file was not created or is empty: {filepath}")

        return filepath

    def verify_backup(self, backup_file: str) -> bool:
        """Verify the integrity of a SQL Server backup"""
        if backup_file.endswith(".bak"):
            # For .bak files, we'd need to use RESTORE VERIFYONLY
            # This requires connection to SQL Server, so just check file exists
            return os.path.exists(backup_file) and os.path.getsize(backup_file) > 0
        else:
            # For .sql files, check it's valid SQL
            try:
                with open(backup_file, "r") as f:
                    content = f.read(1000)
                    return "CREATE TABLE" in content or "INSERT INTO" in content
            except Exception:
                return False

    def restore(
        self, backup_file: str, progress: Optional[BackupProgress] = None
    ) -> bool:
        if backup_file.endswith(".bak"):
            # Native restore from .bak file
            return self._restore_native_bak(backup_file)
        else:
            # Restore from SQL script
            return self._restore_sql_script(backup_file)

    def _restore_native_bak(self, backup_file: str) -> bool:
        """Restore from native .bak file"""
        params = self.config["params"]

        # This requires the .bak file to be accessible to SQL Server
        # For Docker containers, we'd need to copy it into the container first
        if self._can_use_docker_api():
            import docker

            client = docker.from_env()
            container = client.containers.get(params["host"])

            # Copy .bak file into container
            backup_filename = os.path.basename(backup_file)
            container_path = f"/tmp/{backup_filename}"

            # Create tar archive with the backup file
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(backup_file, arcname=backup_filename)
            tar_stream.seek(0)

            # Put the file in container
            container.put_archive("/tmp", tar_stream)

            # Execute RESTORE DATABASE
            restore_query = f"""
            RESTORE DATABASE [{params['database']}]
            FROM DISK = N'{container_path}'
            WITH REPLACE, RECOVERY;
            """

            env = os.environ.copy()
            env["SQLCMDPASSWORD"] = params["password"]

            cmd = [
                "sqlcmd",
                "-S",
                f"{params['host']},{params['port']}",
                "-U",
                params["user"],
                "-Q",
                restore_query,
                "-b",
            ]

            try:
                subprocess.run(cmd, env=env, check=True, capture_output=True)
                # Clean up
                container.exec_run(f"rm {container_path}")
                return True
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                raise RuntimeError(f"Restore failed: {error_msg}")
        else:
            raise RuntimeError(
                "Cannot restore .bak file: SQL Server container not accessible "
                "via Docker API"
            )

    def _restore_sql_script(self, backup_file: str) -> bool:
        """Restore from SQL script"""
        params = self.config["params"]

        # First, drop all user tables to ensure clean restore
        print("Cleaning database: dropping all user tables...")
        conn = pymssql.connect(
            server=params["host"],
            port=str(params["port"]),
            user=params["user"],
            password=params["password"],
            database=params["database"],
        )
        cursor = conn.cursor()

        # Get all user tables (excluding system tables)
        cursor.execute(
            """
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
              AND TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
              AND TABLE_NAME NOT IN (
                  'spt_fallback_db',
                  'spt_fallback_dev',
                  'spt_fallback_usg',
                  'spt_monitor',
                  'MSreplication_options',
                  'spt_values'
              )
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        )
        tables_to_drop = cursor.fetchall() or []

        # Drop all user tables
        for schema, table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE [{schema}].[{table}]")
                print(f"  Dropped [{schema}].[{table}]")
            except Exception as e:
                print(f"  Warning: Could not drop [{schema}].[{table}]: {e}")

        conn.commit()
        conn.close()

        print(f"Dropped {len(tables_to_drop)} user tables. Starting restore...")

        # Now restore from SQL script
        env = os.environ.copy()
        env["SQLCMDPASSWORD"] = params["password"]

        # Get trust certificate setting (default: true)
        trust_cert = params.get("trust_certificate", True)

        cmd = [
            "sqlcmd",
            "-S",
            f"{params['host']},{params['port']}",
            "-U",
            params["user"],
            "-d",
            params["database"],
        ]

        if trust_cert:
            cmd.append("-C")  # Trust server certificate

        cmd.extend(["-i", backup_file, "-b"])

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            # Show actual error from sqlcmd
            error_output = e.stderr if e.stderr else e.stdout if e.stdout else str(e)
            raise RuntimeError(f"Restore failed: {error_output}")
