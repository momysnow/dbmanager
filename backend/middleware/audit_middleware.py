"""ASGI middleware that records an audit log entry for significant requests."""

import asyncio
import logging
import time
from typing import Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths always audited regardless of method
_ALWAYS_AUDIT_PREFIXES = ("/api/v1/auth/",)
# Methods that are always audited (state-changing)
_AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 401/403 are security-relevant — write them synchronously so a SIGTERM
# during shutdown can never silently drop a denial event.
_SYNC_AUDIT_STATUS = {401, 403}

# Track in-flight async audit tasks so the lifespan shutdown can drain them.
_pending_audit_tasks: "Set[asyncio.Task]" = set()


async def drain_pending_audits(timeout: float = 5.0) -> int:
    """Wait up to `timeout` seconds for fire-and-forget audit writes to finish.

    Returns the number of tasks that were still pending when called. Safe to
    call repeatedly; a no-op if the queue is empty.
    """
    if not _pending_audit_tasks:
        return 0
    pending = list(_pending_audit_tasks)
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    if still_pending:
        logger.warning(
            "audit drain: %d task(s) still pending after %.1fs", len(still_pending), timeout
        )
    return len(pending)


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
        details = {
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

        if response.status_code in _SYNC_AUDIT_STATUS:
            # Block the response on the audit write. Costs ~one DB round-trip
            # per denial but guarantees the event lands in the log even if the
            # process is killed immediately afterwards.
            await _write_audit(
                action=action,
                resource_type=resource_type,
                status=status_str,
                user=user,
                request=request,
                details=details,
            )
        else:
            # Successful and non-security-critical paths use a fire-and-forget
            # task so latency stays below the audit DB round-trip. Tasks are
            # tracked in a module-level set so the lifespan shutdown can drain
            # them; without that, SIGTERM cancels them mid-write.
            task = asyncio.create_task(
                _write_audit(
                    action=action,
                    resource_type=resource_type,
                    status=status_str,
                    user=user,
                    request=request,
                    details=details,
                )
            )
            _pending_audit_tasks.add(task)
            task.add_done_callback(_pending_audit_tasks.discard)

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
