"""Per-request correlation ID middleware.

Generates a `request_id` if the inbound request didn't supply one, stores it
in `utils.logger.request_id_ctx` for the duration of the request so log
lines can be filtered/joined across services, and echoes it back to the
client via the `X-Request-ID` response header.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logger import request_id_ctx


_HEADER = "X-Request-ID"
# Caps the inbound id length so a malicious client cannot make us log
# unbounded strings.
_MAX_LEN = 128


def _normalise(raw: str) -> str:
    raw = raw.strip()
    if not raw or len(raw) > _MAX_LEN:
        return uuid.uuid4().hex
    # Allow only printable, no-whitespace, no-shell-metachar ASCII so the
    # value is safe to drop into log lines and Sentry tags.
    if not all(c.isalnum() or c in "-_." for c in raw):
        return uuid.uuid4().hex
    return raw


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        rid = _normalise(request.headers.get(_HEADER, ""))
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[_HEADER] = rid
        return response
