"""Audit logging helpers. Never raises — write failures are silently logged."""

import logging
import os
from typing import Any, Optional

from fastapi import Request

from db.models.user import User

logger = logging.getLogger(__name__)


def _get_client_ip(request: Request) -> Optional[str]:
    """Return a best-effort client IP.

    Only honors X-Forwarded-For when DBMANAGER_TRUST_PROXY is set. In that case
    takes the right-most entry (closest to the trusted edge) instead of the
    left-most, since left-most values are attacker-controllable.
    """
    if os.getenv("DBMANAGER_TRUST_PROXY", "").lower() in ("1", "true", "yes"):
        # X-Real-IP is preferred if the proxy sets it explicitly.
        real = request.headers.get("X-Real-IP")
        if real:
            return real.strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[-1]
    if request.client:
        return request.client.host
    return None


_MAX_DETAIL_BYTES = 4096


def _sanitize_details(details: Any) -> Any:
    """Truncate oversized details and strip obvious secret-looking values."""
    if details is None:
        return None
    if isinstance(details, dict):
        out = {}
        for k, v in details.items():
            key = str(k).lower()
            if any(tag in key for tag in ("password", "secret", "token", "apikey", "api_key")):
                out[k] = "***"
            elif isinstance(v, str) and len(v) > 500:
                out[k] = v[:500] + "…"
            else:
                out[k] = v
        return out
    if isinstance(details, str) and len(details) > _MAX_DETAIL_BYTES:
        return details[:_MAX_DETAIL_BYTES] + "…"
    return details


async def record_audit(
    *,
    action: str,
    status: str = "success",
    user: Optional[User] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[Any] = None,
) -> None:
    """Write an audit log entry. Never propagates exceptions."""
    try:
        from db.engine import AsyncSessionLocal
        from db.repositories.audit_repo import create_audit_log

        ip = _get_client_ip(request) if request else None
        ua = request.headers.get("user-agent") if request else None

        async with AsyncSessionLocal() as session:
            await create_audit_log(
                session,
                action=action,
                status=status,
                user_id=user.id if user else None,
                username_snapshot=user.username if user else None,
                resource_type=resource_type,
                resource_id=resource_id,
                ip=ip,
                user_agent=ua,
                details=_sanitize_details(details),
            )
            await session.commit()
    except Exception as exc:
        logger.error("Audit write failed: %s", exc)
