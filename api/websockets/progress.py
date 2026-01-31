"""WebSocket handlers for real-time progress updates"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json

from api.task_manager import task_manager


class ConnectionManager:
    """Manages WebSocket connections for progress updates"""
    
    def __init__(self):
        # Map of task_id -> set of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        
        self.active_connections[task_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection"""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_task_update(self, task_id: str, task_data: dict):
        """Send update to all clients watching this task"""
        if task_id not in self.active_connections:
            return
        
        # Create message
        message = json.dumps({
            "type": "progress",
            **task_data
        })
        
        # Send to all connected clients
        disconnected = set()
        for websocket in self.active_connections[task_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                # Mark for disconnection
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, task_id)


# Global connection manager
manager = ConnectionManager()


async def progress_websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for task progress updates"""
    
    # Check if task exists
    task = task_manager.get_task(task_id)
    if not task:
        await websocket.close(code=1008, reason="Task not found")
        return
    
    # Connect
    await manager.connect(websocket, task_id)
    
    try:
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "progress",
            **task
        }))
        
        # Poll for updates and send to client
        last_update = task.get("updated_at")
        
        while True:
            # Check task status
            current_task = task_manager.get_task(task_id)
            
            if not current_task:
                # Task was deleted
                await websocket.close(code=1000, reason="Task completed and cleaned up")
                break
            
            # Send update if changed
            if current_task.get("updated_at") != last_update:
                await websocket.send_text(json.dumps({
                    "type": "progress",
                    **current_task
                }))
                last_update = current_task.get("updated_at")
            
            # Check if task is finished
            if current_task.get("status") in ["completed", "failed"]:
                # Send final update and close
                await asyncio.sleep(0.5)  # Give client time to receive final message
                await websocket.close(code=1000, reason="Task finished")
                break
            
            # Wait before next poll
            await asyncio.sleep(0.5)  # Poll every 500ms
    
    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Error occurred
        print(f"WebSocket error for task {task_id}: {e}")
    finally:
        # Cleanup
        manager.disconnect(websocket, task_id)
