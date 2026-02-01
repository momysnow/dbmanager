"""Backup schedule endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from api.models.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    CronJobCreate,
    CronJobResponse
)
from api.dependencies import get_config_manager
from config import ConfigManager
from core.cron import CronManager

router = APIRouter()
cron_manager = CronManager()


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """List all backup schedules"""
    schedules = config_manager.config.get("schedules", [])
    
    return [ScheduleResponse(**s) for s in schedules]


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get a specific schedule by ID"""
    schedules = config_manager.config.get("schedules", [])
    
    schedule = next((s for s in schedules if s.get("id") == schedule_id), None)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    return ScheduleResponse(**schedule)


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Create a new backup schedule"""
    
    # Validate database exists
    db = config_manager.get_database(schedule.database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {schedule.database_id} not found"
        )
    
    # Validate cron expression (basic validation)
    parts = schedule.cron_expression.split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cron expression. Must have 5 parts: minute hour day month weekday"
        )
    
    # Convert to dict
    schedule_dict = schedule.model_dump()
    
    # Generate ID
    schedules = config_manager.config.get("schedules", [])
    existing_ids = [s.get("id", 0) for s in schedules]
    new_id = max(existing_ids) + 1 if existing_ids else 1
    schedule_dict["id"] = new_id
    
    # Add next_run and last_run
    schedule_dict["next_run"] = None
    schedule_dict["last_run"] = None
    
    # Add to config
    if "schedules" not in config_manager.config:
        config_manager.config["schedules"] = []
    
    config_manager.config["schedules"].append(schedule_dict)
    config_manager.save_config()
    
    return ScheduleResponse(**schedule_dict)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule: ScheduleUpdate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Update an existing schedule"""
    
    schedules = config_manager.config.get("schedules", [])
    schedule_index = next((i for i, s in enumerate(schedules) if s.get("id") == schedule_id), None)
    
    if schedule_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    # Validate cron if being updated
    if schedule.cron_expression is not None:
        parts = schedule.cron_expression.split()
        if len(parts) != 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression. Must have 5 parts: minute hour day month weekday"
            )
    
    # Merge updates
    updated_schedule = schedules[schedule_index].copy()
    update_data = schedule.model_dump(exclude_unset=True)
    updated_schedule.update(update_data)
    
    # Save
    config_manager.config["schedules"][schedule_index] = updated_schedule
    config_manager.save_config()
    
    return ScheduleResponse(**updated_schedule)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Delete a schedule"""
    
    schedules = config_manager.config.get("schedules", [])
    schedule = next((s for s in schedules if s.get("id") == schedule_id), None)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    # Remove schedule
    config_manager.config["schedules"] = [s for s in schedules if s.get("id") != schedule_id]
    config_manager.save_config()
    
    return None


@router.post("/schedules/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    schedule_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Enable or disable a schedule"""
    
    schedules = config_manager.config.get("schedules", [])
    schedule_index = next((i for i, s in enumerate(schedules) if s.get("id") == schedule_id), None)
    
    if schedule_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    # Toggle enabled
    schedule = schedules[schedule_index]
    schedule["enabled"] = not schedule.get("enabled", True)
    
    # Save
    config_manager.save_config()
    
    return ScheduleResponse(**schedule)


@router.get("/schedules/cron", response_model=List[CronJobResponse])
async def list_cron_jobs():
    """List cron-based backup jobs"""
    jobs = cron_manager.list_jobs()
    return [CronJobResponse(**job) for job in jobs]


@router.post("/schedules/cron", response_model=CronJobResponse)
async def add_cron_job(
    job: CronJobCreate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Create or update a cron-based backup job"""
    db = config_manager.get_database(job.database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {job.database_id} not found"
        )

    parts = job.cron_expression.split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cron expression. Must have 5 parts: minute hour day month weekday"
        )

    cron_manager.add_backup_job(int(job.database_id), job.cron_expression)

    jobs = cron_manager.list_jobs()
    created = next((j for j in jobs if str(j.get("id")) == str(job.database_id)), None)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create cron job"
        )

    return CronJobResponse(**created)


@router.delete("/schedules/cron/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cron_job(database_id: int):
    """Delete a cron-based backup job"""
    cron_manager.remove_job(database_id)
    return None
