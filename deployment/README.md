# DBManager Service Deployment

## Development Mode

### Start API Server (background)
```bash
python main.py start-api
```

### Check Status
```bash
python main.py status-api
```

### Stop API Server
```bash
python main.py stop-api
```

### Restart API Server
```bash
python main.py restart-api
```

### Start API Server (foreground for debugging)
```bash
python main.py start-api --no-background
# or directly:
python api_server.py
```

## Production Deployment (Linux)

### Using systemd

1. **Edit service file:**
   ```bash
   sudo nano deployment/dbmanager-api.service
   ```
   
   Update:
   - `User=YOUR_USERNAME`
   - `WorkingDirectory=/path/to/dbmanager`
   - `ExecStart=/usr/bin/python3 /path/to/dbmanager/api_server.py`

2. **Install service:**
   ```bash
   sudo cp deployment/dbmanager-api.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

3. **Start service:**
   ```bash
   sudo systemctl start dbmanager-api
   sudo systemctl enable dbmanager-api  # Auto-start on boot
   ```

4. **Check status:**
   ```bash
   sudo systemctl status dbmanager-api
   ```

5. **View logs:**
   ```bash
   sudo journalctl -u dbmanager-api -f
   ```

### Using Supervisor

1. **Install Supervisor:**
   ```bash
   sudo apt-get install supervisor
   ```

2. **Create config:**
   ```bash
   sudo nano /etc/supervisor/conf.d/dbmanager-api.conf
   ```
   
   Content:
   ```ini
   [program:dbmanager-api]
   command=/usr/bin/python3 /path/to/dbmanager/api_server.py
   directory=/path/to/dbmanager
   user=YOUR_USERNAME
   autostart=true
   autorestart=true
   stderr_logfile=/var/log/dbmanager-api.err.log
   stdout_logfile=/var/log/dbmanager-api.out.log
   ```

3. **Start:**
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start dbmanager-api
   ```

## Production Deployment (Docker)

### Build Image
```bash
docker build -t dbmanager-api -f deployment/Dockerfile .
```

### Run Container
```bash
docker run -d \
  --name dbmanager-api \
  -p 8000:8000 \
  -v ~/.dbmanager:/root/.dbmanager \
  dbmanager-api
```

## Nginx Reverse Proxy (Production)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              API Server (Daemon)            │
│         Always running on port 8000         │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │         FastAPI Application           │ │
│  │  - REST Endpoints                     │ │
│  │  - WebSocket Progress                 │ │
│  │  - Background Tasks                   │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                    ↑
                    │ Uses
                    ↓
┌─────────────────────────────────────────────┐
│              Core Library                   │
│                                             │
│  - DBManager                                │
│  - Providers (PostgreSQL, MySQL, etc)       │
│  - NotificationManager                      │
│  - BucketManager                            │
│  - Backup/Restore Logic                     │
└─────────────────────────────────────────────┘
                    ↑
                    │ Uses
                    ↓
┌─────────────────────────────────────────────┐
│          CLI Tool (Interactive)             │
│                                             │
│  - Can use Core directly                    │
│  - Or call API endpoints                    │
│  - Manages API service (start/stop/status)  │
└─────────────────────────────────────────────┘
```

## Usage Patterns

### Pattern 1: API + CLI Independent
- API running as system service
- CLI used for quick operations
- Both access same config/data

### Pattern 2: API Only
- API running as service
- Web UI or scripts consume API
- CLI not needed

### Pattern 3: CLI Only
- No API running
- Direct CLI usage
- Good for cron jobs

## Environment Variables

- `DBMANAGER_DATA_DIR`: Override default data directory
- `DBMANAGER_API_PORT`: API port (default: 8000)
- `DBMANAGER_API_HOST`: API host (default: 0.0.0.0)
