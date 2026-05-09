from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.audit_log import AuditLog


async def create_audit_log(
    session: AsyncSession,
    *,
    action: str,
    status: str = "success",
    user_id: Optional[int] = None,
    username_snapshot: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Any] = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        status=status,
        user_id=user_id,
        username_snapshot=username_snapshot,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        details=details,
    )
    session.add(log)
    await session.flush()
    return log


async def list_audit_logs(
    session: AsyncSession,
    *,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[AuditLog]:
    query = select(AuditLog)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if status:
        query = query.where(AuditLog.status == status)
    if from_dt:
        query = query.where(AuditLog.timestamp >= from_dt)
    if to_dt:
        query = query.where(AuditLog.timestamp <= to_dt)
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def count_audit_logs(
    session: AsyncSession,
    *,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
) -> int:
    query = select(func.count(AuditLog.id))
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if status:
        query = query.where(AuditLog.status == status)
    if from_dt:
        query = query.where(AuditLog.timestamp >= from_dt)
    if to_dt:
        query = query.where(AuditLog.timestamp <= to_dt)
    result = await session.execute(query)
    return result.scalar_one()


async def list_distinct_actions(session: AsyncSession) -> List[str]:
    result = await session.execute(
        select(distinct(AuditLog.action)).order_by(AuditLog.action)
    )
    return list(result.scalars().all())
