"""ASGI middleware that records an audit log entry for significant requests."""

import asyncio
import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths always audited regardless of method
_ALWAYS_AUDIT_PREFIXES = ("/api/v1/auth/",)
# Methods that are always audited (state-changing)
_AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _should_audit(method: str, path: str, status_code: int) -> bool:
    if any(path.startswith(p) for p in _ALWAYS_AUDIT_PREFIXES):
        return True
    if method in _AUDIT_METHODS:
        return True
    if status_code >= 400:
        return True
    return False


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        if not _should_audit(request.method, request.url.path, response.status_code):
            return response

        # Extract user from request state (set by get_current_user if called)
        user = getattr(request.state, "current_user", None)

        status_str = "success"
        if response.status_code == 403:
            status_str = "denied"
        elif response.status_code >= 400:
            status_str = "failure"

        action = f"http.{request.method.lower()}"
        resource_type = request.url.path

        asyncio.create_task(
            _write_audit(
                action=action,
                resource_type=resource_type,
                status=status_str,
                user=user,
                request=request,
                details={
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        )

        return response


async def _write_audit(
    *,
    action: str,
    resource_type: Optional[str],
    status: str,
    user: Optional[object],
    request: Request,
    details: Optional[dict],
) -> None:
    try:
        from core.audit import record_audit

        await record_audit(
            action=action,
            status=status,
            user=user,  # type: ignore[arg-type]
            resource_type=resource_type,
            request=request,
            details=details,
        )
    except Exception as exc:
        logger.error("Middleware audit write failed: %s", exc)
