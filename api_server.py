#!/usr/bin/env python3
"""DBManager API Server Daemon"""

import uvicorn
import signal
import sys
from pathlib import Path

# PID file for daemon management
PID_FILE = Path.home() / ".dbmanager" / "api.pid"


def write_pid():
    """Write process ID to file"""
    PID_FILE.parent.mkdir(exist_ok=True)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


def remove_pid():
    """Remove PID file"""
    if PID_FILE.exists():
        PID_FILE.unlink()


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutting down API server...")
    remove_pid()
    sys.exit(0)


if __name__ == "__main__":
    import os
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Write PID
    write_pid()
    
    print("🚀 Starting DBManager API Server...")
    print(f"📍 PID: {os.getpid()}")
    print(f"🌐 Server: http://0.0.0.0:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    print(f"💾 PID file: {PID_FILE}")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disabled for daemon mode
            log_level="info",
            access_log=True
        )
    finally:
        remove_pid()
