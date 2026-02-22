import requests
import time
import sys

base_url = "http://localhost:8000/api/v1"
login_data = {"username": "admin", "password": "admin"}
resp = requests.post(f"{base_url}/auth/token", data=login_data)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

dbs = requests.get(f"{base_url}/databases", headers=headers).json()
db_id = dbs[0]["id"]

resp = requests.post(f"{base_url}/databases/{db_id}/backup", headers=headers)
task_id = resp.json()["task_id"]

while True:
    task = requests.get(f"{base_url}/tasks/{task_id}", headers=headers).json()
    if task["status"] in ["completed", "failed"]:
        break
    time.sleep(1)

backup_file = task["result"]["backup_path"]

restore_req = {
    "backup_file": backup_file,
    "location": "local",
    "skip_safety_snapshot": True,
}
resp = requests.post(
    f"{base_url}/databases/{db_id}/restore", json=restore_req, headers=headers
)
print(f"Restore API Status: {resp.status_code}")
print(f"Restore API Response: {resp.text}")
