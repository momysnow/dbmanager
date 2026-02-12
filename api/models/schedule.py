"""Schedule-related Pydantic models"""

from typing import Optional

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    """Model for creating a backup schedule"""

    database_id: int = Field(..., description="Database ID")
    cron_expression: str = Field(..., description="Cron expression (e.g., '0 2 * * *')")
    enabled: bool = Field(default=True, description="Schedule enabled")


class ScheduleUpdate(BaseModel):
    """Model for updating a backup schedule"""

    cron_expression: Optional[str] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    """Model for schedule response"""

    id: int
    database_id: int
    cron_expression: str
    enabled: bool
    next_run: Optional[str] = None
    last_run: Optional[str] = None


class CronJobCreate(BaseModel):
    """Model for creating a cron job"""

    database_id: int = Field(..., description="Database ID")
    cron_expression: str = Field(..., description="Cron expression (e.g., '0 2 * * *')")


class CronJobResponse(BaseModel):
    """Model for cron job response"""

    id: str
    schedule: str
    command: str
    enabled: bool
