"""Backup and restore endpoints"""

from pathlib import Path
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from api.models.backup import (
    RestoreRequest,
    TaskResponse,
    TaskStatus,
    BackupInfo,
    BackupSyncRequest,
    BackupSyncResult,
)
from api.dependencies import get_config_manager, get_db_manager
from api.task_manager import task_manager
from config import ConfigManager
from core.manager import DBManager
from core.progress import BackupProgress

router = APIRouter()


def _get_db_or_404(database_id: int, config_manager: ConfigManager) -> Dict[str, Any]:
    db = config_manager.get_database(database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )
    return db


def _get_s3_storage(
    database_id: int, config_manager: ConfigManager, db_manager: DBManager
) -> Tuple[Dict[str, Any], Any]:
    db = _get_db_or_404(database_id, config_manager)
    if not db.get("s3_enabled") or not db.get("s3_bucket_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3 not configured for this database",
        )

    bucket_id_value = db.get("s3_bucket_id")
    if bucket_id_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3 bucket ID missing from configuration",
        )
    storage = db_manager.storage_manager.get_storage(int(bucket_id_value))
    if not storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bucket storage not found"
        )
    return db, storage


def run_backup_task(task_id: str, db_id: int, db_manager: DBManager) -> None:
    """Background task to perform backup"""
    try:
        # Update task status
        task_manager.update_task(
            task_id, status="running", message="Starting backup..."
        )

        # Create progress tracker
        progress = BackupProgress()

        # Setup callback to update task
        def progress_callback(p: BackupProgress) -> None:
            task_manager.update_from_progress(task_id, p)

        progress._callback = progress_callback

        # Perform backup
        backup_path = db_manager.backup_database(db_id, progress=progress)

        # Complete task
        task_manager.complete_task(task_id, result={"backup_path": backup_path})

    except Exception as e:
        task_manager.fail_task(task_id, str(e))


def run_restore_task(
    task_id: str, db_id: int, backup_file: str, db_manager: DBManager
) -> None:
    """Background task to perform restore"""
    try:
        # Update task status
        task_manager.update_task(
            task_id, status="running", message="Starting restore..."
        )

        # Create progress tracker
        progress = BackupProgress()

        # Setup callback to update task
        def progress_callback(p: BackupProgress) -> None:
            task_manager.update_from_progress(task_id, p)

        progress._callback = progress_callback

        # Perform restore
        success = db_manager.restore_database(db_id, backup_file, progress=progress)

        if success:
            task_manager.complete_task(task_id, result={"restored": True})
        else:
            task_manager.fail_task(task_id, "Restore returned False")

    except Exception as e:
        task_manager.fail_task(task_id, str(e))


def run_restore_from_s3_task(
    task_id: str,
    db_id: int,
    s3_key: str,
    db_manager: DBManager,
    config_manager: ConfigManager,
) -> None:
    """Background task to restore from S3 backup"""
    temp_dir = None
    try:
        task_manager.update_task(
            task_id, status="running", message="Downloading backup from S3..."
        )

        _, storage = _get_s3_storage(db_id, config_manager, db_manager)
        temp_dir = tempfile.mkdtemp()
        local_path = os.path.join(temp_dir, os.path.basename(s3_key))

        if not storage.download_file(s3_key, local_path):
            raise RuntimeError("Failed to download backup from S3")

        checksum_key = f"{s3_key}.sha256"
        if storage.get_file_info(checksum_key):
            storage.download_file(checksum_key, f"{local_path}.sha256")

        task_manager.update_task(
            task_id, status="running", message="Starting restore..."
        )
        run_restore_task(task_id, db_id, local_path, db_manager)
    except Exception as e:
        task_manager.fail_task(task_id, str(e))
    finally:
        if temp_dir:
            try:
                for f in Path(temp_dir).glob("*"):
                    f.unlink(missing_ok=True)
                Path(temp_dir).rmdir()
            except Exception:
                pass


@router.post("/databases/{database_id}/backup", response_model=TaskResponse)
async def start_backup(
    database_id: int,
    background_tasks: BackgroundTasks,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> TaskResponse:
    """Start a backup operation"""

    # Validate database exists
    db = _get_db_or_404(database_id, config_manager)

    # Create task
    task_id = task_manager.create_task(
        "backup", f"Backup database: {db.get('name', database_id)}"
    )

    # Start background task
    background_tasks.add_task(run_backup_task, task_id, database_id, db_manager)

    return TaskResponse(task_id=task_id, status="pending", message="Backup started")


@router.post("/databases/{database_id}/restore", response_model=TaskResponse)
async def start_restore(
    database_id: int,
    restore_request: RestoreRequest,
    background_tasks: BackgroundTasks,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> TaskResponse:
    """Start a restore operation"""

    # Validate database exists
    db = _get_db_or_404(database_id, config_manager)

    if restore_request.location not in {"local", "s3"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid location. Must be 'local' or 's3'",
        )

    # Validate backup file exists for local restores
    if restore_request.location == "local" and not os.path.exists(
        restore_request.backup_file
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {restore_request.backup_file}",
        )

    # Create task
    task_id = task_manager.create_task(
        "restore", f"Restore database: {db.get('name', database_id)}"
    )

    # Start background task
    if restore_request.location == "s3":
        background_tasks.add_task(
            run_restore_from_s3_task,
            task_id,
            database_id,
            restore_request.backup_file,
            db_manager,
            config_manager,
        )
    else:
        background_tasks.add_task(
            run_restore_task,
            task_id,
            database_id,
            restore_request.backup_file,
            db_manager,
        )

    return TaskResponse(task_id=task_id, status="pending", message="Restore started")


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str) -> TaskStatus:
    """Get status of a background task (polling endpoint)"""

    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )

    return TaskStatus(**task)


@router.get("/databases/{database_id}/backups", response_model=List[BackupInfo])
async def list_backups(
    database_id: int,
    location: Optional[str] = None,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> List[BackupInfo]:
    """List backups for a specific database"""

    # Validate database exists
    _get_db_or_404(database_id, config_manager)

    if location and location not in {"local", "s3"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid location. Must be 'local' or 's3'",
        )

    # Get backups
    backups = db_manager.list_backups(database_id)
    if location:
        backups = [b for b in backups if b.get("location") == location]

    # Convert to response model
    backup_list: List[BackupInfo] = []
    for backup in backups:
        # Determine checksum verification status
        # Since we don't have stored result, we could assume False or None
        # until explicitly verified. "has_checksum" is a good proxy.

        backup_info = BackupInfo(
            path=backup["path"],
            filename=backup["filename"],
            size_mb=backup["size_mb"],
            date=backup["date"].isoformat(),
            database_id=database_id,
            has_checksum=backup.get("has_checksum", False),
            location=backup.get("location", "local"),
            # checksum_verified could be populated if we stored verification status,
            # but for now let's leave it as None (unknown) or check file existence?
            # It's an optional field.
        )
        backup_list.append(backup_info)

    return backup_list


@router.post("/backups/verify", response_model=dict)
async def verify_backup(
    # We need to accept complex object or query params.
    # Use Body or improved Request model.
    # To keep it simple without new model file edits for now, use dict body.
    # Let's use simple body dict
    payload: Dict[str, Any],
    db_manager: DBManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Verify backup integrity"""
    backup_file = payload.get("backup_file")
    location = payload.get("location", "local")
    database_id = payload.get("database_id")

    if not backup_file:
        raise HTTPException(status_code=400, detail="backup_file required")

    if location == "s3" and not database_id:
        raise HTTPException(
            status_code=400, detail="database_id required for S3 verification"
        )

    if location == "local" and not os.path.exists(backup_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {backup_file}",
        )

    try:
        result = db_manager.verify_backup_integrity(
            backup_file, location=location, db_id=database_id
        )
        return {
            "file": backup_file,
            "valid": result,
            "message": (
                "Backup integrity verified"
                if result
                else "Backup integrity check failed"
            ),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )


@router.delete("/backups", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_file: str,
    location: str = "local",
    database_id: Optional[int] = None,
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> None:
    """Delete a backup file"""

    if location == "local":
        if not os.path.exists(backup_file):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {backup_file}",
            )

        try:
            # Delete backup file
            os.remove(backup_file)

            # Also delete checksum if exists
            checksum_file = f"{backup_file}.sha256"
            if os.path.exists(checksum_file):
                os.remove(checksum_file)

            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete backup: {str(e)}",
            )

    elif location == "s3":
        if not database_id:
            raise HTTPException(
                status_code=400, detail="database_id required for S3 deletion"
            )

        db_config = config_manager.get_database(database_id)
        if not db_config or not db_config.get("s3_bucket_id"):
            raise HTTPException(
                status_code=400, detail="S3 not configured for this database"
            )

        bucket_id_value = db_config.get("s3_bucket_id")
        if bucket_id_value is None:
            raise HTTPException(
                status_code=400, detail="S3 bucket ID missing from configuration"
            )
        storage = db_manager.storage_manager.get_storage(int(bucket_id_value))
        if not storage:
            raise HTTPException(status_code=404, detail="Bucket storage not found")

        try:
            # Delete file from S3 using key (backup_file)
            storage.delete_file(backup_file)

            # Try delete checksum
            try:
                storage.delete_file(f"{backup_file}.sha256")
            except Exception:
                pass

            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete S3 backup: {str(e)}",
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid location")


@router.post("/databases/{database_id}/backups/sync", response_model=BackupSyncResult)
async def sync_backups(
    database_id: int,
    sync_request: BackupSyncRequest,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> BackupSyncResult:
    """Sync backups between local and S3"""
    if sync_request.action not in {"upload", "download", "full"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    _, storage = _get_s3_storage(database_id, config_manager, db_manager)

    local_backups = [
        b for b in db_manager.list_backups(database_id) if b.get("location") == "local"
    ]
    local_files = {b["filename"] for b in local_backups}

    prefix = f"backups/{database_id}/"
    s3_backups = storage.list_files(prefix)
    s3_files = {
        b["key"].split("/")[-1] for b in s3_backups if not b["key"].endswith(".sha256")
    }

    only_local = local_files - s3_files
    only_s3 = s3_files - local_files

    uploaded = 0
    downloaded = 0

    backup_dir = db_manager._get_backup_dir(database_id)
    backup_dir.mkdir(parents=True, exist_ok=True)

    if sync_request.action in {"upload", "full"}:
        for filename in only_local:
            local_path = backup_dir / filename
            s3_key = f"backups/{database_id}/{filename}"
            if storage.upload_file(str(local_path), s3_key):
                uploaded += 1

    if sync_request.action in {"download", "full"}:
        for filename in only_s3:
            s3_key = f"backups/{database_id}/{filename}"
            local_path = backup_dir / filename
            if storage.download_file(s3_key, str(local_path)):
                downloaded += 1

    return BackupSyncResult(
        uploaded=uploaded,
        downloaded=downloaded,
        local_only=len(only_local),
        s3_only=len(only_s3),
    )
