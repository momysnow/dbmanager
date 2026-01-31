"""Task manager for tracking background operations"""

import uuid
from datetime import datetime
from typing import Dict, Optional, Callable
from threading import Lock
from core.progress import BackupProgress, ProgressStatus


class TaskManager:
    """Manages background tasks and their status"""
    
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self._lock = Lock()
    
    def create_task(self, task_type: str, description: str) -> str:
        """Create a new task and return its ID"""
        task_id = str(uuid.uuid4())
        
        with self._lock:
            self.tasks[task_id] = {
                "id": task_id,
                "type": task_type,
                "description": description,
                "status": "pending",
                "progress": 0,
                "message": "Task created",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "completed_at": None,
                "error": None,
                "result": None
            }
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task status"""
        with self._lock:
            return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs):
        """Update task fields"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kwargs)
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
    
    def update_from_progress(self, task_id: str, progress: BackupProgress):
        """Update task from BackupProgress object"""
        status_map = {
            ProgressStatus.IDLE: "pending",
            ProgressStatus.PREPARING: "running",
            ProgressStatus.RUNNING: "running",
            ProgressStatus.COMPLETED: "completed",
            ProgressStatus.FAILED: "failed"
        }
        
        update_data = {
            "status": status_map.get(progress.status, "pending"),
            "progress": progress.percentage,
            "message": progress.message,
            "error": progress.error
        }
        
        if progress.status == ProgressStatus.COMPLETED:
            update_data["completed_at"] = datetime.now().isoformat()
        elif progress.status == ProgressStatus.FAILED:
            update_data["completed_at"] = datetime.now().isoformat()
        
        self.update_task(task_id, **update_data)
    
    def complete_task(self, task_id: str, result: any = None):
        """Mark task as completed"""
        self.update_task(
            task_id,
            status="completed",
            progress=100,
            message="Task completed successfully",
            completed_at=datetime.now().isoformat(),
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed"""
        self.update_task(
            task_id,
            status="failed",
            message=f"Task failed: {error}",
            error=error,
            completed_at=datetime.now().isoformat()
        )
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove tasks older than max_age_hours"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            to_remove = []
            for task_id, task in self.tasks.items():
                created = datetime.fromisoformat(task["created_at"])
                if created < cutoff and task["status"] in ["completed", "failed"]:
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.tasks[task_id]
        
        return len(to_remove)


# Global task manager instance
task_manager = TaskManager()
