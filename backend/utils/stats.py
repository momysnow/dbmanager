"""Dashboard statistics module"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from config import ConfigManager
from core.manager import DBManager


class DashboardStats:
    """Calculate and display dashboard statistics"""

    def __init__(self, config_manager: ConfigManager, db_manager: DBManager) -> None:
        self.config_manager = config_manager
        self.db_manager = db_manager

    def get_overview_stats(self) -> Dict[str, Any]:
        """Get overview statistics"""
        databases = self.config_manager.get_databases()
        s3_buckets = self.config_manager.config.get("storage_targets", [])
        schedules = self.config_manager.config.get("schedules", [])

        # Calculate total backups
        total_backups = 0
        total_backup_size = 0

        for db in databases:
            db_id = db.get("id")
            if db_id is None:
                continue
            backups = self.db_manager.list_backups(int(db_id))
            total_backups += len(backups)
            total_backup_size += sum(b["size_mb"] for b in backups)

        # Active schedules
        active_schedules = len([s for s in schedules if s.get("enabled", False)])

        return {
            "total_databases": len(databases),
            "total_s3_buckets": len(s3_buckets),
            "total_schedules": len(schedules),
            "active_schedules": active_schedules,
            "total_backups": total_backups,
            "total_backup_size_mb": total_backup_size,
            "total_backup_size_gb": total_backup_size / 1024,
        }

    def get_database_stats(self) -> List[Dict[str, Any]]:
        """Get per-database statistics"""
        databases = self.config_manager.get_databases()
        stats = []

        for db in databases:
            db_id = db.get("id")
            if db_id is None:
                continue
            db_id = int(db_id)
            db_name = db.get("name")
            provider = db.get("provider")

            # Get backups
            backups = self.db_manager.list_backups(db_id)

            # Last backup
            last_backup = backups[0] if backups else None
            last_backup_date = last_backup["date"] if last_backup else None
            last_backup_size = last_backup["size_mb"] if last_backup else 0

            # Total size
            total_size = sum(b["size_mb"] for b in backups)

            # Schedule info
            schedules = self.config_manager.config.get("schedules", [])
            db_schedules = [s for s in schedules if s.get("database_id") == db_id]
            active_schedule = next((s for s in db_schedules if s.get("enabled")), None)

            stats.append(
                {
                    "id": db_id,
                    "name": db_name,
                    "provider": provider,
                    "backup_count": len(backups),
                    "total_size_mb": total_size,
                    "last_backup_date": last_backup_date,
                    "last_backup_size_mb": last_backup_size,
                    "has_schedule": active_schedule is not None,
                    "schedule_cron": (
                        active_schedule.get("cron_expression")
                        if active_schedule
                        else None
                    ),
                    "s3_enabled": db.get("s3_enabled", False),
                }
            )

        return stats

    def get_recent_activity(self, days: int = 7) -> Dict[str, Any]:
        """Get recent backup activity"""
        databases = self.config_manager.get_databases()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        recent_backups = []

        for db in databases:
            db_id = db.get("id")
            if db_id is None:
                continue
            db_id = int(db_id)
            db_name = db.get("name")
            backups = self.db_manager.list_backups(db_id)

            for backup in backups:
                if backup["date"] > cutoff_date:
                    recent_backups.append(
                        {
                            "database": db_name,
                            "date": backup["date"],
                            "size_mb": backup["size_mb"],
                            "filename": backup["filename"],
                        }
                    )

        # Sort by date descending
        recent_backups.sort(key=lambda x: x["date"], reverse=True)

        return {
            "days": days,
            "total_recent_backups": len(recent_backups),
            "recent_backups": recent_backups[:10],  # Last 10
        }

    def get_storage_breakdown(self) -> Dict[str, Any]:
        """Get storage usage breakdown"""
        databases = self.config_manager.get_databases()

        breakdown = []
        total_size = 0

        for db in databases:
            db_id = db.get("id")
            if db_id is None:
                continue
            db_id = int(db_id)
            db_name = db.get("name")
            backups = self.db_manager.list_backups(db_id)

            db_size = sum(b["size_mb"] for b in backups)
            total_size += db_size

            breakdown.append(
                {
                    "database": db_name,
                    "size_mb": db_size,
                    "size_gb": db_size / 1024,
                    "backup_count": len(backups),
                }
            )

        # Sort by size descending
        breakdown.sort(key=lambda x: x["size_mb"], reverse=True)

        # Calculate percentages
        for item in breakdown:
            item["percentage"] = (
                (item["size_mb"] / total_size * 100) if total_size > 0 else 0
            )

        return {
            "total_size_mb": total_size,
            "total_size_gb": total_size / 1024,
            "breakdown": breakdown,
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        databases = self.config_manager.get_databases()
        issues = []
        warnings = []

        for db in databases:
            db_id = db.get("id")
            if db_id is None:
                continue
            db_id = int(db_id)
            db_name = db.get("name")
            backups = self.db_manager.list_backups(db_id)

            # No backups
            if not backups:
                issues.append(f"No backups found for {db_name}")
            else:
                # Old backups (>7 days)
                last_backup = backups[0]
                days_old = (datetime.now(timezone.utc) - last_backup["date"]).days

                if days_old > 7:
                    warnings.append(f"{db_name}: Last backup is {days_old} days old")

            # No schedule
            schedules = self.config_manager.config.get("schedules", [])
            db_schedules = [
                s
                for s in schedules
                if s.get("database_id") == db_id and s.get("enabled")
            ]

            if not db_schedules:
                warnings.append(f"{db_name}: No active backup schedule")

        # Determine overall health
        if issues:
            health = "critical"
        elif warnings:
            health = "warning"
        else:
            health = "healthy"

        return {"status": health, "issues": issues, "warnings": warnings}
