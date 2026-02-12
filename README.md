# DBManager - Database Backup & Restore Tool

Enterprise-grade backup and restore tool for multiple database providers with S3 support, encryption, compression, scheduling, and REST API.

## 🚀 Quick Start (Docker)

```bash
docker compose up -d --build
docker exec -it dbmanager bash
python main.py interactive
```

## 📦 Supported Databases

- ✅ **PostgreSQL** (pg_dump/pg_restore)
- ✅ **MySQL** (mysqldump/mysql)
- ✅ **MariaDB** (MySQL protocol)
- ✅ **SQL Server** (sqlcmd/bcp)
- ✅ **MongoDB** (mongodump/mongorestore)

## ✨ Features

### Core

- 🔄 **Backup & Restore** - All major databases
- ☁️ **S3 Storage** - AWS, Cloudflare R2, MinIO
- 🗜️ **Compression** - gzip, zstandard (configurable levels)
- 🔐 **Encryption** - AES-256 or ChaCha20
- ✅ **Checksum** - SHA-256 verification
- 🔁 **Config Sync** - S3-based configuration backup

### Automation

- ⏰ **Scheduling** - Cron-based automatic backups
- 🔔 **Notifications** - Email, Slack, Teams, Discord
- 📊 **Dashboard** - CLI statistics and health monitoring
- 📝 **Structured Logging** - Rotating logs with JSON support

### API

- 🌐 **REST API** - FastAPI with OpenAPI docs
- 🎯 **Background Tasks** - Async backup/restore
- 📡 **Service Mode** - Daemon API server

### Management

- 📤 **Export/Import** - Configuration backup/restore
- 💾 **Retention** - Local and S3 cleanup policies
- 🏥 **Health Checks** - System status monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         CLI (Interactive Menu)          │
│  - Dashboard                            │
│  - Manage Databases                     │
│  - Schedules, Settings, S3              │
└─────────────┬───────────────────────────┘
              │
              ↓
┌─────────────────────────────────────────┐
│         Core Business Logic             │
│  - DBManager                            │
│  - Providers (5 database types)         │
│  - BucketManager (S3)                   │
│  - NotificationManager                  │
│  - Encryption, Compression, Checksums   │
└─────────────┬───────────────────────────┘
              │
              ↓
┌─────────────────────────────────────────┐
│      REST API (FastAPI, optional)       │
│  - Endpoints for all operations         │
│  - Background task manager              │
└─────────────────────────────────────────┘
```

## 📖 Documentation

- [Installation Guide](INSTALLATION.md) - Docker & local setup
- [API Documentation](http://localhost:8000/docs) - Swagger UI (when API running)

## 🛠️ Tech Stack

- **Python 3.10+**
- **CLI**: Typer, InquirerPy, Rich
- **API**: FastAPI, Uvicorn
- **Database Drivers**: psycopg2, pymysql, pymssql
- **Cloud**: boto3 (S3)
- **Compression**: zstandard
- **Encryption**: cryptography

## ✅ Code Quality

Install dev tools:

```bash
pip install -r requirements-dev.txt
```

Run checks:

```bash
black .
flake8 .
mypy .
```

Docstring warnings (non-blocking, Google style):

```bash
flake8 --select D --exit-zero
```

Pre-commit:

```bash
pre-commit run --all-files
```

### Tools Explained

- **Black**: The uncompromising Python code formatter. It enforces a consistent clicking style.
- **Flake8**: A wrapper around `PyFlakes`, `pycodestyle`, and `Ned Batchelder's McCabe script`. It checks for style guide enforcement (PEP8) and programming errors.
- **Mypy**: A static type checker for Python. It acts as a linter that checks for type errors using Python 3 type hints.

## 🐳 Docker

All database tools pre-installed:

- PostgreSQL 18 client
- MySQL/MariaDB client
- SQL Server tools (mssql-tools18)
- MongoDB Database Tools

### Environment variables

You can configure the API auth and encryption via environment variables (recommended for Docker).

| Variable                 | Description                               | Default     |
| ------------------------ | ----------------------------------------- | ----------- |
| DBMANAGER_CREATE_ADMIN   | Create admin user on first run            | true        |
| DBMANAGER_ADMIN_USER     | Initial admin username                    | admin       |
| DBMANAGER_ADMIN_PASSWORD | Initial admin password                    | admin       |
| DBMANAGER_JWT_SECRET     | JWT secret for API tokens                 | (generated) |
| DBMANAGER_MASTER_KEY     | Master key for config encryption (Fernet) | (generated) |

Copy .env.example and edit values:

```bash
cp .env.example .env
```

## 📝 Configuration

Config stored in: `~/.dbmanager/config.json`

```json
{
  "databases": [...],
  "s3_buckets": [...],
  "schedules": [...],
  "global_settings": {
    "compression": {...},
    "encryption": {...}
  },
  "notifications": {...}
}
```

## 🎯 Usage Examples

### CLI

```bash
# Interactive menu
python main.py interactive

# Start API server
python main.py start-api

# Check API status
python main.py status-api
```

### API

```bash
# Start API
docker compose up -d

# Access Swagger docs
open http://localhost:8000/docs

# Backup via API
curl -X POST http://localhost:8000/api/v1/backups/1
```

## 📄 License

[Your License]

## 🤝 Contributing

[Contributing guidelines]
