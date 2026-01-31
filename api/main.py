"""FastAPI application for DBManager REST API"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import routers
from api.routers import databases, backups, s3_buckets, schedules, settings

# Task manager for background operations
from api.task_manager import task_manager


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

# Include routers
app.include_router(databases.router, prefix="/api/v1", tags=["Databases"])
app.include_router(backups.router, prefix="/api/v1", tags=["Backups"])
app.include_router(s3_buckets.router, prefix="/api/v1", tags=["S3 Buckets"])
app.include_router(schedules.router, prefix="/api/v1", tags=["Schedules"])
app.include_router(settings.router, prefix="/api/v1", tags=["Settings"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DBManager API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tasks": {
            "running": len([t for t in task_manager.tasks.values() if t["status"] == "running"]),
            "total": len(task_manager.tasks)
        }
    }
