"""FastAPI application for DBManager REST API"""

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import os
from pathlib import Path

# Import routers
from api.routers import databases, backups, s3_buckets, schedules, settings, auth
from api.deps import get_current_user

# Task manager for background operations
from api.task_manager import task_manager

# WebSocket handler
from api.websockets import progress_websocket_endpoint
from fastapi import Depends


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    lifespan=lifespan
)

# CORS middleware for web UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure per environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WEB UI SETUP
# -----------------------------------------------------------------------------
# Determine web directory path (robust to running from root or api dir)
BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

# Create web directories if they strictly must exist for StaticFiles to mount without error
# In production, these should be pre-copied.
if not WEB_DIR.exists():
    pass

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

# Mount static files
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static"), check_dir=False), name="static")


# Include routers
# Public routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# Protected routes
app.include_router(databases.router, prefix="/api/v1", tags=["Databases"], dependencies=[Depends(get_current_user)])
app.include_router(backups.router, prefix="/api/v1", tags=["Backups"], dependencies=[Depends(get_current_user)])
app.include_router(s3_buckets.router, prefix="/api/v1", tags=["S3 Buckets"], dependencies=[Depends(get_current_user)])
app.include_router(schedules.router, prefix="/api/v1", tags=["Schedules"], dependencies=[Depends(get_current_user)])
app.include_router(settings.router, prefix="/api/v1", tags=["Settings"], dependencies=[Depends(get_current_user)])


# WebSocket endpoint for progress updates (Auth via query param or ticket needed in future)
# For now public or we can inspect query params manually
@app.websocket("/api/v1/ws/tasks/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task progress updates"""
    await progress_websocket_endpoint(websocket, task_id)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve Login Page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the Web UI entry point"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tasks": {
            "running": len([t for t in task_manager.tasks.values() if t["status"] == "running"]),
            "total": len(task_manager.tasks)
        }
    }
