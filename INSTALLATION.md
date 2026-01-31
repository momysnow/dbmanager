# DBManager - Installation Guide

## Docker Installation (Recommended)

The easiest way to use DBManager is via Docker. All database tools are pre-installed.

### Quick Start

```bash
# Clone repository
git clone <your-repo>
cd dbmanager

# Build and run
docker compose up -d --build

# Access container
docker exec -it dbmanager bash

# Run DBManager
python main.py interactive
```

### Included Tools

The Docker image includes all necessary database tools:
- ✅ PostgreSQL client (pg_dump, pg_restore)
- ✅ MySQL/MariaDB client (mysqldump, mysql)
- ✅ SQL Server client (sqlcmd, bcp)
- ✅ MongoDB tools (mongodump, mongorestore)

## Local Installation (Development)

For local development outside Docker:

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Database Tools

#### PostgreSQL
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client
```

#### MySQL/MariaDB
```bash
# macOS
brew install mysql-client

# Ubuntu/Debian
sudo apt-get install mysql-client
```

#### SQL Server
```bash
# macOS
brew tap microsoft/mssql-release
brew install mssql-tools18

# Ubuntu/Debian
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18
```

#### MongoDB
```bash
# macOS
brew install mongodb-database-tools

# Ubuntu/Debian
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update
sudo apt-get install -y mongodb-database-tools
```

### 3. Run DBManager

```bash
python main.py interactive
```

## Dependencies

All Python dependencies are in `requirements.txt`:

- **Core**: typer, InquirerPy, rich, pydantic
- **Database drivers**: psycopg2-binary, pymysql, pymssql, pymongo
- **Cloud**: boto3
- **API**: fastapi, uvicorn, websockets
- **Utilities**: requests, zstandard

## Production Deployment

See [deployment/README.md](../deployment/README.md) for production setup with systemd/supervisor.
