import requests
import sys

base_url = "http://localhost:8000/api/v1"
login_data = {"username": "admin", "password": "admin"}
resp = requests.post(f"{base_url}/auth/token", data=login_data)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

dbs = requests.get(f"{base_url}/databases", headers=headers).json()
if not dbs:
    print("No DBs")
    sys.exit(1)

db_id = dbs[0]['id']

q_req = {"query": "SELECT 1;", "limit": 100}
resp = requests.post(f"{base_url}/databases/{db_id}/query", json=q_req, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
