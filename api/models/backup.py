"""Backup-related Pydantic models"""

from typing import Optional

from pydantic import BaseModel, Field


class BackupRequest(BaseModel):
    """Model for initiating a backup"""

    database_id: int = Field(..., description="Database ID to backup")


class RestoreRequest(BaseModel):
    """Model for initiating a restore"""

    database_id: int = Field(..., description="Database ID to restore to")
    backup_file: str = Field(..., description="Path to backup file")
    location: str = Field("local", description="Location of backup (local/s3)")


class BackupSyncRequest(BaseModel):
    """Model for syncing backups between local and S3"""

    action: str = Field("full", description="Sync action: upload, download, full")


class BackupSyncResult(BaseModel):
    """Model for sync result"""

    uploaded: int
    downloaded: int
    local_only: int
    s3_only: int


class TaskResponse(BaseModel):
    """Model for task creation response"""

    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    """Model for task status"""

    id: str
    type: str
    description: str
    status: str
    progress: int
    message: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None


class BackupInfo(BaseModel):
    """Model for backup file information"""

    path: str
    filename: str
    size_mb: float
    date: str
    database_id: int
    has_checksum: bool
    location: str = "local"
    checksum_verified: Optional[bool] = None
