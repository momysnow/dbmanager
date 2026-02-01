"""Dashboard statistics models"""

from pydantic import BaseModel
from typing import List, Optional


class OverviewStats(BaseModel):
    total_databases: int
    total_s3_buckets: int
    total_schedules: int
    active_schedules: int
    total_backups: int
    total_backup_size_mb: float
    total_backup_size_gb: float


class DatabaseStat(BaseModel):
    id: int
    name: str
    provider: str
    backup_count: int
    total_size_mb: float
    last_backup_date: Optional[str] = None
    last_backup_size_mb: float
    has_schedule: bool
    schedule_cron: Optional[str] = None
    s3_enabled: bool


class RecentBackup(BaseModel):
    database: str
    date: str
    size_mb: float
    filename: str


class RecentActivity(BaseModel):
    days: int
    total_recent_backups: int
    recent_backups: List[RecentBackup]


class StorageBreakdownItem(BaseModel):
    database: str
    size_mb: float
    size_gb: float
    backup_count: int
    percentage: float


class StorageBreakdown(BaseModel):
    total_size_mb: float
    total_size_gb: float
    breakdown: List[StorageBreakdownItem]


class HealthStatus(BaseModel):
    status: str
    issues: List[str]
    warnings: List[str]
