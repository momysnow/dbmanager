"""Backup and restore endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import List
import os
from pathlib import Path

from api.models.backup import (
    BackupRequest,
    RestoreRequest,
    TaskResponse,
    TaskStatus,
    BackupInfo
)
from api.dependencies import get_config_manager, get_db_manager
from api.task_manager import task_manager
from config import ConfigManager, CONFIG_DIR
from core.manager import DBManager
from core.progress import BackupProgress

router = APIRouter()


def run_backup_task(task_id: str, db_id: int, db_manager: DBManager):
    """Background task to perform backup"""
    try:
        # Update task status
        task_manager.update_task(task_id, status="running", message="Starting backup...")
        
        # Create progress tracker
        progress = BackupProgress()
        
        # Setup callback to update task
        def progress_callback(p: BackupProgress):
            task_manager.update_from_progress(task_id, p)
        
        progress._callback = progress_callback
        
        # Perform backup
        backup_path = db_manager.backup_database(db_id, progress=progress)
        
        # Complete task
        task_manager.complete_task(task_id, result={"backup_path": backup_path})
    
    except Exception as e:
        task_manager.fail_task(task_id, str(e))


def run_restore_task(task_id: str, db_id: int, backup_file: str, db_manager: DBManager):
    """Background task to perform restore"""
    try:
        # Update task status
        task_manager.update_task(task_id, status="running", message="Starting restore...")
        
        # Create progress tracker
        progress = BackupProgress()
        
        # Setup callback to update task
        def progress_callback(p: BackupProgress):
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


@router.post("/databases/{database_id}/backup", response_model=TaskResponse)
async def start_backup(
    database_id: int,
    background_tasks: BackgroundTasks,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Start a backup operation"""
    
    # Validate database exists
    db = config_manager.get_database(database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Create task
    task_id = task_manager.create_task(
        "backup",
        f"Backup database: {db.get('name', database_id)}"
    )
    
    # Start background task
    background_tasks.add_task(run_backup_task, task_id, database_id, db_manager)
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="Backup started"
    )


@router.post("/databases/{database_id}/restore", response_model=TaskResponse)
async def start_restore(
    database_id: int,
    restore_request: RestoreRequest,
    background_tasks: BackgroundTasks,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Start a restore operation"""
    
    # Validate database exists
    db = config_manager.get_database(database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Validate backup file exists
    if not os.path.exists(restore_request.backup_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {restore_request.backup_file}"
        )
    
    # Create task
    task_id = task_manager.create_task(
        "restore",
        f"Restore database: {db.get('name', database_id)}"
    )
    
    # Start background task
    background_tasks.add_task(
        run_restore_task,
        task_id,
        database_id,
        restore_request.backup_file,
        db_manager
    )
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="Restore started"
    )


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get status of a background task (polling endpoint)"""
    
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    return TaskStatus(**task)


@router.get("/databases/{database_id}/backups", response_model=List[BackupInfo])
async def list_backups(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """List backups for a specific database"""
    
    # Validate database exists
    db = config_manager.get_database(database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Get backups
    backups = db_manager.list_backups(database_id)
    
    # Convert to response model
    backup_list = []
    for backup in backups:
        # Determine checksum verification status
        # Since we don't have stored result, we could assume False or None until explicitly verified.
        # But 'has_checksum' is a good proxy for integrity availability.
        
        backup_info = BackupInfo(
            path=backup['path'],
            filename=backup['filename'],
            size_mb=backup['size_mb'],
            date=backup['date'].isoformat(),
            database_id=database_id,
            has_checksum=backup.get('has_checksum', False),
            location=backup.get('location', 'local'),
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
    # To keep simple without new model file edits for now (wait, we edited DB model, we can edit Backup model or use dict body)
    # Let's use simple body dict
    payload: dict,
    db_manager: DBManager = Depends(get_db_manager)
):
    """Verify backup integrity"""
    backup_file = payload.get("backup_file")
    location = payload.get("location", "local")
    database_id = payload.get("database_id")
    
    if not backup_file:
         raise HTTPException(status_code=400, detail="backup_file required")
    
    if location == 's3' and not database_id:
         raise HTTPException(status_code=400, detail="database_id required for S3 verification")

    if location == 'local' and not os.path.exists(backup_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {backup_file}"
        )
    
    try:
        result = db_manager.verify_backup_integrity(backup_file, location=location, db_id=database_id)
        return {
            "file": backup_file,
            "valid": result,
            "message": "Backup integrity verified" if result else "Backup integrity check failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.delete("/backups", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_file: str,
    location: str = "local",
    database_id: int = None,
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager)
):
    """Delete a backup file"""
    
    if location == "local":
        if not os.path.exists(backup_file):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {backup_file}"
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
                detail=f"Failed to delete backup: {str(e)}"
            )
            
    elif location == "s3":
        if not database_id:
            raise HTTPException(status_code=400, detail="database_id required for S3 deletion")
            
        db_config = config_manager.get_database(database_id)
        if not db_config or not db_config.get("s3_bucket_id"):
             raise HTTPException(status_code=400, detail="S3 not configured for this database")
        
        bucket_id = db_config.get("s3_bucket_id")
        storage = db_manager.bucket_manager.get_storage(bucket_id)
        if not storage:
             raise HTTPException(status_code=404, detail="Bucket storage not found")
        
        try:
            # Delete file from S3 using key (backup_file)
            storage.delete_file(backup_file)
            
            # Try delete checksum
            try:
                storage.delete_file(f"{backup_file}.sha256")
            except:
                pass
                
            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete S3 backup: {str(e)}"
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid location")
