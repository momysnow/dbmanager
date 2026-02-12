"""Dashboard statistics endpoints"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends

from api.models.dashboard import (
    OverviewStats,
    DatabaseStat,
    RecentActivity,
    RecentBackup,
    StorageBreakdown,
    StorageBreakdownItem,
    HealthStatus,
)
from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager
from utils.stats import DashboardStats

router = APIRouter()


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


@router.get("/dashboard/overview", response_model=OverviewStats)
async def dashboard_overview(
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> OverviewStats:
    stats = DashboardStats(config_manager, db_manager)
    return OverviewStats(**stats.get_overview_stats())


@router.get("/dashboard/databases", response_model=List[DatabaseStat])
async def dashboard_databases(
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> List[DatabaseStat]:
    stats = DashboardStats(config_manager, db_manager)
    data = []
    for item in stats.get_database_stats():
        item = item.copy()
        item["last_backup_date"] = _to_iso(item.get("last_backup_date"))
        data.append(DatabaseStat(**item))
    return data


@router.get("/dashboard/recent", response_model=RecentActivity)
async def dashboard_recent_activity(
    days: int = 7,
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> RecentActivity:
    stats = DashboardStats(config_manager, db_manager)
    data = stats.get_recent_activity(days=days)
    recent = [
        RecentBackup(
            database=b["database"],
            date=b["date"].isoformat(),
            size_mb=b["size_mb"],
            filename=b["filename"],
        )
        for b in data.get("recent_backups", [])
    ]
    return RecentActivity(
        days=data.get("days", days),
        total_recent_backups=data.get("total_recent_backups", 0),
        recent_backups=recent,
    )


@router.get("/dashboard/storage", response_model=StorageBreakdown)
async def dashboard_storage(
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> StorageBreakdown:
    stats = DashboardStats(config_manager, db_manager)
    data = stats.get_storage_breakdown()
    breakdown = [StorageBreakdownItem(**item) for item in data.get("breakdown", [])]
    return StorageBreakdown(
        total_size_mb=data.get("total_size_mb", 0),
        total_size_gb=data.get("total_size_gb", 0),
        breakdown=breakdown,
    )


@router.get("/dashboard/health", response_model=HealthStatus)
async def dashboard_health(
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager),
) -> HealthStatus:
    stats = DashboardStats(config_manager, db_manager)
    return HealthStatus(**stats.get_health_status())
