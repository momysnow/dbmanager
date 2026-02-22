import requests
import time
import sys

base_url = "http://localhost:8000/api/v1"

print("0. Login...")
login_data = {"username": "admin", "password": "admin"}
# It expects form data (OAuth2PasswordRequestForm)
resp = requests.post(f"{base_url}/auth/login", data=login_data)
if not resp.ok:
    print(f"Login failed: {resp.text}")
    sys.exit(1)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("1. Getting databases...")
dbs = requests.get(f"{base_url}/databases", headers=headers).json()
if not dbs:
    print("No databases found!")
    sys.exit(1)

db_id = dbs[0]['id']
print(f"Using DB ID: {db_id}, Name: {dbs[0].get('name')}")

print("2. Starting backup...")
resp = requests.post(f"{base_url}/databases/{db_id}/backup", headers=headers)
task_id = resp.json()['task_id']

while True:
    task = requests.get(f"{base_url}/tasks/{task_id}", headers=headers).json()
    print(f"Backup Status: {task['status']}")
    if task['status'] in ['completed', 'failed']:
        break
    time.sleep(1)

if task['status'] == 'failed':
    print(f"Backup failed: {task.get('error')}")
    sys.exit(1)

backup_file = task['result']['backup_path']
print(f"Backup file: {backup_file}")

print("3. Starting restore...")
restore_req = {
    "backup_file": backup_file,
    "location": "local"
}
resp = requests.post(f"{base_url}/databases/{db_id}/restore", json=restore_req, headers=headers)
restore_task_id = resp.json()['task_id']

while True:
    task = requests.get(f"{base_url}/tasks/{restore_task_id}", headers=headers).json()
    print(f"Restore Status: {task['status']}")
    print(f"Restore Message: {task.get('message', '')}")
    if task['status'] in ['completed', 'failed']:
        print(f"Final Task state: {task}")
        break
    time.sleep(1)

if task['status'] == 'failed':
    print("Restore failed!")
    sys.exit(1)
print("Restore success!")
