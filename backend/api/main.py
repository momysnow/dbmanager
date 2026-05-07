"""FastAPI application for DBManager REST API"""

import logging
import os
import time
from contextlib import asynccontextmanager
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
            print(f"[startup] registered sample DB: {db['name']}")


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
            if env_pw:
                admin_password = env_pw
                must_change = False
            else:
                admin_password = _secrets.token_urlsafe(24)
                must_change = True
            hashed = auth_manager.get_password_hash(admin_password)
            user_obj = await create_user(session, username=admin_user, password_hash=hashed, role="admin")
            user_obj.must_change_password = must_change
            await session.commit()
            if must_change:
                import sys
                print(
                    f"\n*** DBMANAGER: generated admin password (change immediately) ***\n"
                    f"    username: {admin_user}\n"
                    f"    password: {admin_password}\n",
                    file=sys.stderr,
                )
            logger.info("Created default admin user: %s", admin_user)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for startup/shutdown"""
    print("🚀 DBManager API starting...")
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
    monitor.stop()
    print("👋 DBManager API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="DBManager API",
    version="1.0.0",
    description="Database backup and restore management API",
    lifespan=lifespan,
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
    print(
        "FATAL: ALLOWED_ORIGINS='*' is incompatible with allow_credentials=True. "
        "Set a specific origin list.",
        file=sys.stderr,
    )
    sys.exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit middleware (after CORS so CORS headers are set first)
from middleware.audit_middleware import AuditMiddleware  # noqa: E402
app.add_middleware(AuditMiddleware)

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
app.include_router(settings.router, prefix="/api/v1", tags=["Settings"], dependencies=_admin_only)
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"], dependencies=_admin_only)
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"], dependencies=_all_roles)
app.include_router(export.router, prefix="/api/v1", tags=["Export"], dependencies=_admin_op)
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
                ts = bkps[0]["date"].isoformat() if hasattr(bkps[0]["date"], "isoformat") else str(bkps[0]["date"])
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
    return {
        "status": "healthy",
        "tasks": {
            "running": len([t for t in task_manager.tasks.values() if t["status"] == "running"]),
            "total": len(task_manager.tasks),
        },
    }
