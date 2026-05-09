"""FastAPI application for DBManager REST API"""

import json as _json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (
    databases,
    backups,
    s3_buckets,
    schedules,
    settings,
    auth,
    notifications,
    dashboard,
    query,
    export,
)
from api.routers import users as users_router
from api.routers import audit_logs as audit_logs_router
from api.routers import proxy as proxy_router
from api.deps import get_current_user, require_role
from api.dependencies import config_manager, db_manager
from api.task_manager import task_manager

from fastapi import Depends

_all_roles = [Depends(require_role("admin", "operator", "viewer"))]
_admin_op = [Depends(require_role("admin", "operator"))]
_admin_only = [Depends(require_role("admin"))]

logger = logging.getLogger(__name__)

_start_time = time.time()


def _register_sample_dbs_if_needed() -> None:
    if os.getenv("SEED_SAMPLE_DBS") != "true":
        return
    existing_names = {d["name"] for d in config_manager.get_databases()}
    sample_dbs = [
        {
            "name": "Sample Postgres",
            "provider": "postgres",
            "params": {
                "host": os.getenv("POSTGRES_HOST", "postgres"),
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "database": os.getenv("POSTGRES_DB", "testdb"),
                "user": os.getenv("POSTGRES_USER", "testuser"),
                "password": os.getenv("POSTGRES_PASSWORD", "testpassword"),
            },
        },
        {
            "name": "Sample MySQL",
            "provider": "mysql",
            "params": {
                "host": os.getenv("MYSQL_HOST", "mysql"),
                "port": int(os.getenv("MYSQL_PORT", "3306")),
                "database": os.getenv("MYSQL_DATABASE", "testdb"),
                "user": os.getenv("MYSQL_USER", "testuser"),
                "password": os.getenv("MYSQL_PASSWORD", "testpassword"),
            },
        },
    ]
    for db in sample_dbs:
        if db["name"] not in existing_names:
            config_manager.add_database(db)
            logger.info(f"[startup] registered sample DB: {db['name']}")


async def _init_db() -> None:
    """Run Alembic migrations and bootstrap admin user if DB is empty."""
    import asyncio
    from alembic.config import Config
    from alembic import command

    from db.engine import engine, CONFIG_DIR
    from db.engine import AsyncSessionLocal
    from db.repositories.users_repo import count_users, create_user
    from db.import_config_users import migrate_users_from_config
    from api.deps import auth_manager

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Run migrations synchronously in a thread to avoid event-loop issues
    def _run_migrations() -> None:
        import sys

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(cfg, "head")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations)

    async with AsyncSessionLocal() as session:
        # Migrate users from legacy config.json
        imported = await migrate_users_from_config(session)
        if imported:
            await session.commit()
            logger.info("Imported %d users from config.json", imported)

        # Bootstrap default admin if still empty
        total = await count_users(session)
        if total == 0:
            import secrets as _secrets

            admin_user = os.getenv("DBMANAGER_ADMIN_USER", "admin")
            env_pw = os.getenv("DBMANAGER_ADMIN_PASSWORD", "")
            # Reject obvious placeholders shipped in .env.example to avoid
            # admin/admin (or admin/change-me) reaching production.
            _REJECTED_PWS = {"admin", "change-me", "changeme", "password", ""}
            if env_pw and env_pw.strip().lower() in _REJECTED_PWS:
                raise RuntimeError(
                    "DBMANAGER_ADMIN_PASSWORD is set to a known placeholder "
                    f"value ({env_pw!r}). Set a strong password in .env or "
                    "leave it empty to auto-generate one."
                )
            if env_pw and len(env_pw) < 8:
                raise RuntimeError(
                    "DBMANAGER_ADMIN_PASSWORD is too short (<8 chars)."
                )
            if env_pw:
                admin_password = env_pw
                must_change = True  # Force change on first login regardless.
            else:
                admin_password = _secrets.token_urlsafe(24)
                must_change = True
            hashed = auth_manager.get_password_hash(admin_password)
            user_obj = await create_user(
                session, username=admin_user, password_hash=hashed, role="admin"
            )
            user_obj.must_change_password = must_change
            await session.commit()
            if must_change:
                logger.warning(
                    "*** DBMANAGER: generated admin password (change immediately) ***"
                    " username=%s password=%s",
                    admin_user,
                    admin_password,
                )
            logger.info("Created default admin user: %s", admin_user)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for startup/shutdown"""
    logger.info("🚀 DBManager API starting...")
    await _init_db()

    from core.uptime_monitor import UptimeMonitor

    monitor = UptimeMonitor(
        config_manager,
        db_manager.notification_manager,
        db_manager.get_provider_instance,
    )
    monitor.start()
    _register_sample_dbs_if_needed()

    # Apply proxy config to Caddy on startup (idempotent — hot reload only).
    try:
        from proxy.config import ProxyConfigManager
        from proxy.manager import ProxyManager
        from proxy.runtime_print import print_runtime_config

        print_runtime_config()
        pmgr = ProxyConfigManager()
        if pmgr.exists():
            cfg = pmgr.load()
            if cfg.is_configured():
                ProxyManager(pmgr).apply(cfg, allow_restart_fallback=False)
    except Exception as e:  # noqa: BLE001 — never block API startup on proxy errors
        logger.warning("proxy startup apply failed: %s", e)

    yield

    # Graceful shutdown. Each step is wrapped so a failure in one stage does
    # not abort the others — partial cleanup is better than none. Order:
    #   1. stop accepting new background work
    #   2. drain async audit writes (security events must not be lost)
    #   3. close the DB engine so SQLite can release its WAL
    logger.info("👋 DBManager API shutting down...")
    try:
        monitor.stop()
    except Exception as exc:  # noqa: BLE001
        logger.warning("uptime monitor stop failed: %s", exc)

    try:
        from middleware.audit_middleware import drain_pending_audits

        drained = await drain_pending_audits(timeout=5.0)
        if drained:
            logger.info("audit drain: flushed %d pending writes", drained)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit drain failed: %s", exc)

    try:
        from db.engine import engine as _db_engine

        await _db_engine.dispose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("db engine dispose failed: %s", exc)


# Create FastAPI app. /docs, /redoc, /openapi.json are gated on
# DBMANAGER_ENV. They expose the full route map (path, methods, params) of an
# authenticated API and are unnecessary in production deployments. Set
# DBMANAGER_ENV=development to re-enable them.
_env = os.getenv("DBMANAGER_ENV", "production").strip().lower()
_docs_enabled = _env in {"dev", "development", "local"}
app = FastAPI(
    title="DBManager API",
    version="1.0.0",
    description="Database backup and restore management API",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS middleware
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

# Guard: allow_credentials=True + wildcard origin is rejected by browsers but
# we still refuse startup to avoid accidental misconfiguration.
if "*" in _allowed_origins:
    import sys

    logger.critical(
        "FATAL: ALLOWED_ORIGINS='*' is incompatible with allow_credentials=True. "
        "Set a specific origin list."
    )
    sys.exit(1)

# Guard: the auth rate-limiter (api/routers/auth.py) keeps state in process
# memory. With more than one backend replica, an attacker can spread brute-
# force attempts across replicas and bypass per-IP / per-user limits. Refuse
# to boot in that combination unless an explicit shared backend is set.
_replicas_raw = os.getenv("DBMANAGER_REPLICAS", "1").strip()
try:
    _replicas = int(_replicas_raw or "1")
except ValueError:
    _replicas = 1
_rl_backend = os.getenv("DBMANAGER_RATE_LIMIT_BACKEND", "memory").strip().lower()
if _replicas > 1 and _rl_backend == "memory":
    import sys

    logger.critical(
        "FATAL: DBMANAGER_REPLICAS=%s with rate-limit backend 'memory' would "
        "silently bypass brute-force protection. Set "
        "DBMANAGER_RATE_LIMIT_BACKEND=redis (or another shared store) and "
        "point the limiter at it before scaling out.",
        _replicas,
    )
    sys.exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    # Pin methods + headers explicitly. Wildcards combined with credentials
    # let any allow-listed origin send arbitrary custom headers, which would
    # weaken the X-Requested-With CSRF check in api/deps.py.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


# Cap request body size up-front so a 10GB POST cannot OOM the worker before
# any business logic runs. Default 100 MiB; override via env when restoring
# from a large dump.
def _max_body_bytes() -> int:
    raw = os.getenv("DBMANAGER_MAX_REQUEST_BYTES", str(100 * 1024 * 1024)).strip()
    try:
        v = int(raw)
    except ValueError:
        v = 100 * 1024 * 1024
    return max(1024, v)


_MAX_REQUEST_BYTES = _max_body_bytes()


class _BodySizeLimitMiddleware:
    """Reject bodies larger than ``max_bytes``.

    Previous implementation looked only at the Content-Length header. Clients
    using ``Transfer-Encoding: chunked`` (or any request without CL) bypassed
    the cap entirely — a 200 MB chunked POST was buffered to completion before
    Starlette parsed it. This streaming wrapper counts bytes as the ASGI
    server delivers ``http.request`` messages and short-circuits with 413 the
    moment the cap is crossed, regardless of CL/TE framing.
    """

    def __init__(self, app, max_bytes: int) -> None:  # type: ignore[no-untyped-def]
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: trusted CL beyond limit → reject without reading body.
        cl_value = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                cl_value = value
                break
        if cl_value is not None:
            try:
                cl = int(cl_value)
            except ValueError:
                await self._reject(send, 400, "Malformed Content-Length.")
                return
            if cl > self.max_bytes:
                await self._reject(send, 413, self._too_large_msg())
                return

        # Slow path: count bytes as they arrive. Works for chunked TE too.
        # When the cap is crossed, we send the 413 response from the receive
        # wrapper itself and then signal http.disconnect so the downstream
        # app stops reading. ``rejected`` blocks any later response from the
        # app from being forwarded to the client (the 413 wins).
        bytes_seen = 0
        rejected = False

        async def watching_send(message):
            nonlocal rejected
            if rejected:
                # Drop everything the app produces after we've already sent
                # 413 — Starlette has no way to know the receive wrapper
                # short-circuited the request.
                return
            await send(message)

        async def counting_receive():
            nonlocal bytes_seen, rejected
            message = await receive()
            if message.get("type") == "http.request":
                bytes_seen += len(message.get("body", b""))
                if bytes_seen > self.max_bytes:
                    if not rejected:
                        await self._reject(send, 413, self._too_large_msg())
                    rejected = True
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, counting_receive, watching_send)

    def _too_large_msg(self) -> str:
        return f"Request body exceeds {self.max_bytes} byte limit."

    @staticmethod
    async def _reject(send, status_code: int, detail: str) -> None:  # type: ignore[no-untyped-def]
        body = ('{"detail":' + _json.dumps(detail) + "}").encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app.add_middleware(_BodySizeLimitMiddleware, max_bytes=_MAX_REQUEST_BYTES)


# Optional Sentry integration. Off by default — only initialised if a DSN is
# explicitly provided so the SDK isn't imported in environments that don't
# need it.
_sentry_dsn = os.getenv("DBMANAGER_SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("DBMANAGER_ENV", "production"),
            traces_sample_rate=float(os.getenv("DBMANAGER_SENTRY_TRACES", "0") or "0"),
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        logger.info("Sentry initialised")
    except ImportError:
        logger.warning(
            "DBMANAGER_SENTRY_DSN is set but sentry-sdk is not installed; "
            "skipping initialisation."
        )

# Audit middleware (after CORS so CORS headers are set first)
from middleware.audit_middleware import AuditMiddleware  # noqa: E402
from middleware.request_id import RequestIdMiddleware  # noqa: E402

# Order matters: starlette runs middleware top-down on the request, bottom-up
# on the response. Adding RequestId AFTER Audit means it's the outermost
# middleware on the request path, so the request_id is in the contextvar
# before Audit runs and gets recorded with every audit row.
app.add_middleware(AuditMiddleware)
app.add_middleware(RequestIdMiddleware)

# Public routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# Protected routes
# Databases/backups/s3/schedules/query have per-route role deps in their router files
app.include_router(databases.router, prefix="/api/v1", tags=["Databases"])
app.include_router(backups.router, prefix="/api/v1", tags=["Backups"])
app.include_router(s3_buckets.router, prefix="/api/v1", tags=["Storage"])
app.include_router(schedules.router, prefix="/api/v1", tags=["Schedules"])
app.include_router(query.router, prefix="/api/v1", tags=["Query"])

# Uniform-role routers
app.include_router(
    settings.router, prefix="/api/v1", tags=["Settings"], dependencies=_admin_only
)
app.include_router(
    notifications.router,
    prefix="/api/v1",
    tags=["Notifications"],
    dependencies=_admin_only,
)
app.include_router(
    dashboard.router, prefix="/api/v1", tags=["Dashboard"], dependencies=_all_roles
)
app.include_router(
    export.router, prefix="/api/v1", tags=["Export"], dependencies=_admin_op
)
app.include_router(users_router.router, prefix="/api/v1", tags=["Users"])
app.include_router(audit_logs_router.router, prefix="/api/v1", tags=["AuditLogs"])
app.include_router(proxy_router.router, prefix="/api/v1", tags=["Proxy"])


@app.get("/api/status", include_in_schema=True, tags=["Status"])
async def public_status() -> JSONResponse:
    """Public status endpoint — no auth required."""
    try:
        from utils.stats import DashboardStats

        stats = DashboardStats(config_manager, db_manager)
        health = stats.get_health_status()
    except Exception:
        health = {"status": "unknown", "issues": [], "warnings": []}

    dbs = config_manager.get_databases()
    db_statuses: List[Dict[str, Any]] = []
    last_backup_ts = None

    for db in dbs:
        db_id = db["id"]
        history = config_manager.get_uptime_history(db_id)
        if history:
            last = history[-1]
            # Name and id omitted: unauthenticated callers don't need DB identifiers.
            db_statuses.append({"status": last["status"], "last_seen": last["ts"]})
        else:
            db_statuses.append({"status": "unknown", "last_seen": None})

        try:
            bkps = db_manager.list_backups(db_id)
            if bkps:
                ts = (
                    bkps[0]["date"].isoformat()
                    if hasattr(bkps[0]["date"], "isoformat")
                    else str(bkps[0]["date"])
                )
                if last_backup_ts is None or ts > last_backup_ts:
                    last_backup_ts = ts
        except Exception:
            pass

    return JSONResponse(
        {
            "status": health.get("status", "unknown"),
            "version": "1.0.0",
            "uptime_seconds": round(time.time() - _start_time, 1),
            "databases": db_statuses,
            "last_backup": last_backup_ts,
            "issues": health.get("issues", []),
        }
    )


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    # Anonymous endpoint — keep the body free of stack-state hints (running
    # task counts, DB counts, etc.) that could fingerprint activity for an
    # unauthenticated attacker. Use /livez and /readyz for richer probes.
    return {"status": "healthy"}


@app.get("/livez", include_in_schema=False)
async def livez() -> Dict[str, str]:
    """Liveness probe: process is up. Cheap — no I/O."""
    return {"status": "alive"}


@app.get("/readyz", include_in_schema=False)
async def readyz() -> Response:
    """Readiness probe: deep check that the API can serve traffic.

    Returns 200 only if the auth DB is reachable AND alembic schema is at
    head. Load balancers should route traffic only when this returns 200;
    a freshly started instance with a pending migration is *not* ready.
    """
    from sqlalchemy import text

    from db.engine import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": f"db: {exc.__class__.__name__}"},
        )

    # Migration check — best-effort, don't fail readiness if alembic config
    # is missing (e.g. fresh checkout in dev).
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect

        from db.engine import engine

        async with engine.connect() as conn:

            def _check_head(sync_conn):  # type: ignore[no-untyped-def]
                inspector = inspect(sync_conn)
                if not inspector.has_table("alembic_version"):
                    return None  # bootstrap without migrations is OK
                row = sync_conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).first()
                return row[0] if row else None

            current = await conn.run_sync(_check_head)

        if current is not None:
            cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
            head = ScriptDirectory.from_config(cfg).get_current_head()
            if head and current != head:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not_ready",
                        "reason": f"alembic head={head} current={current}",
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("readyz alembic check skipped: %s", exc)

    return JSONResponse(status_code=200, content={"status": "ready"})
