import subprocess
import json

with open("backend/data/config.json") as f:
    config = json.load(f)

for db in config["databases"]:
    print(f"DB {db['id']}: {db['name']} (Host: {db['params']['host']})")
    
    # Try a simple ping or host resolution from python
    try:
        import socket
        ip = socket.gethostbyname(db['params']['host'])
        print(f"  Resolution: OK -> {ip}")
    except Exception as e:
        print(f"  Resolution: FAILED -> {e}")
