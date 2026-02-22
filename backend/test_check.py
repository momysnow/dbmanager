import socket
import json
import sys

with open("data/config.json") as f:
    config = json.load(f)

for db in config["databases"]:
    print(f"DB {db['id']}: {db['name']} (Host: {db['params']['host']})")
    try:
        ip = socket.gethostbyname(db['params']['host'])
        print(f"  Resolution: OK -> {ip}")
    except Exception as e:
        print(f"  Resolution: FAILED -> {e}")
