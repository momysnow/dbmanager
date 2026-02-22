"""FastAPI application for DBManager REST API"""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
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
)
from api.deps import get_current_user

# Task manager for background operations
from api.task_manager import task_manager

from fastapi import Depends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for startup/shutdown"""
    # Startup
    print("🚀 DBManager API starting...")
    yield
    # Shutdown
    print("👋 DBManager API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="DBManager API",
    version="1.0.0",
    description="Database backup and restore management API",
    lifespan=lifespan,
)

# CORS middleware
# In production set ALLOWED_ORIGINS env var to a comma-separated list of origins
# e.g. ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Public routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# Protected routes
app.include_router(
    databases.router,
    prefix="/api/v1",
    tags=["Databases"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    backups.router,
    prefix="/api/v1",
    tags=["Backups"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    s3_buckets.router,
    prefix="/api/v1",
    tags=["Storage"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    schedules.router,
    prefix="/api/v1",
    tags=["Schedules"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    settings.router,
    prefix="/api/v1",
    tags=["Settings"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    notifications.router,
    prefix="/api/v1",
    tags=["Notifications"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    dashboard.router,
    prefix="/api/v1",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    query.router,
    prefix="/api/v1",
    tags=["Query"],
    dependencies=[Depends(get_current_user)],
)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tasks": {
            "running": len(
                [t for t in task_manager.tasks.values() if t["status"] == "running"]
            ),
            "total": len(task_manager.tasks),
        },
    }
