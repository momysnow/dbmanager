"""API Service management utilities"""

import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import os

PID_FILE = Path.home() / ".dbmanager" / "api.pid"
LOG_FILE = Path.home() / ".dbmanager" / "api.log"


def is_api_running() -> bool:
    """Check if API server is running"""
    if not PID_FILE.exists():
        return False

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        # Check if process exists
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        # Process doesn't exist or PID file is invalid
        if PID_FILE.exists():
            PID_FILE.unlink()
        return False


def get_api_pid() -> Optional[int]:
    """Get API server PID"""
    if not PID_FILE.exists():
        return None

    try:
        with open(PID_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def start_api_server(background: bool = True) -> bool:
    """Start API server"""
    if is_api_running():
        return False

    # Ensure log directory exists
    LOG_FILE.parent.mkdir(exist_ok=True)

    if background:
        # Start in background
        with open(LOG_FILE, "w") as log:
            subprocess.Popen(
                [sys.executable, "api_server.py"],
                stdout=log,
                stderr=log,
                start_new_session=True,  # Detach from parent
            )

        # Wait a bit to ensure it started
        time.sleep(1)
        return is_api_running()
    else:
        # Start in foreground
        subprocess.run([sys.executable, "api_server.py"])
        return True


def stop_api_server() -> bool:
    """Stop API server"""
    if not is_api_running():
        return False

    pid = get_api_pid()
    if pid is None:
        return False

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for process to stop (max 5 seconds)
        for _ in range(50):
            if not is_api_running():
                return True
            time.sleep(0.1)

        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink()
        return True
    except ProcessLookupError:
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True
    except Exception:
        return False


def restart_api_server() -> bool:
    """Restart API server"""
    if is_api_running():
        stop_api_server()
        time.sleep(0.5)

    return start_api_server()


def get_api_status() -> Dict[str, Any]:
    """Get API server status"""
    running = is_api_running()
    pid = get_api_pid() if running else None

    return {
        "running": running,
        "pid": pid,
        "url": "http://localhost:8000" if running else None,
        "docs": "http://localhost:8000/docs" if running else None,
        "log_file": str(LOG_FILE) if LOG_FILE.exists() else None,
    }
