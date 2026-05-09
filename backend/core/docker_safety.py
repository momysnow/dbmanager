"""Guards around the Docker API calls the backend issues.

The backend talks to a restricted docker-socket-proxy, but the proxy can only
filter by HTTP method and endpoint group — it cannot scope a request to a
specific container. Without an in-process allow/deny list, an attacker who
configures a database row with `host: "dbmanager-caddy"` (admin role only,
but lateral-movement worthy) could trigger backup code paths that exec
arbitrary commands inside system containers.

This module enforces that no Docker API operation initiated for an
admin-configurable target ever lands on a container reserved for the
DBManager stack itself.
"""

from __future__ import annotations

# Container names DBManager reserves for itself. The backend may still operate
# on these via dedicated code paths (e.g. proxy/manager.py restarts caddy)
# but those callers go through `assert_target_is_user_db` only when the
# target is sourced from user input.
RESERVED_CONTAINER_NAMES = frozenset(
    {
        "dbmanager-backend",
        "dbmanager-caddy",
        "dbmanager-frontend",
        "dbmanager-docker-proxy",
        # Common alias forms — Compose service names without the
        # ``container_name`` prefix.
        "backend",
        "caddy",
        "frontend",
        "docker-proxy",
    }
)


class UnsafeContainerTargetError(Exception):
    """Raised when user-configurable code paths target a reserved container."""


def assert_target_is_user_db(name: str) -> None:
    """Refuse to operate on DBManager's own containers via user-provided names.

    Call this before `client.containers.get(name)` whenever ``name`` is
    derived from a database config row, request body, or any other
    admin-mutable input.
    """
    candidate = (name or "").strip().lower()
    if not candidate:
        raise UnsafeContainerTargetError("Container name is required")
    if candidate in RESERVED_CONTAINER_NAMES:
        raise UnsafeContainerTargetError(
            f"Refusing to operate on reserved container {name!r}: this name "
            "belongs to the DBManager stack and cannot be used as a database "
            "target."
        )
