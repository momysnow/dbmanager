"""Audit log endpoints (admin only)."""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_role
from db.engine import get_db
from db.repositories.audit_repo import (
    count_audit_logs,
    list_audit_logs,
    list_distinct_actions,
)

router = APIRouter()

_admin_only = [Depends(require_role("admin"))]


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username_snapshot: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Any] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    logs: List[AuditLogResponse]


@router.get("/audit-logs", response_model=AuditLogListResponse, dependencies=_admin_only)
async def list_audit_log_entries(
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    logs = await list_audit_logs(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        status=status,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
        offset=offset,
    )
    total = await count_audit_logs(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        status=status,
        from_dt=from_dt,
        to_dt=to_dt,
    )
    return AuditLogListResponse(
        total=total,
        logs=[AuditLogResponse.model_validate(log) for log in logs],
    )


@router.get("/audit-logs/actions", dependencies=_admin_only)
async def get_distinct_actions(db: AsyncSession = Depends(get_db)) -> List[str]:
    return await list_distinct_actions(db)
