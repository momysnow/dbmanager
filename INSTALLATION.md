# DBManager - Installation Guide

## Quick start (zero-config)

```bash
git clone <repo>
cd dbmanager
docker compose -f docker-compose.yml up -d --build
# open http://localhost  (admin / admin — change immediately)
```

Defaults that make this work without any `.env` file:

- admin user `admin/admin` auto-created on first run
- JWT secret auto-generated and persisted in `~/.dbmanager/config.json`
- master encryption key auto-generated and persisted in `~/.dbmanager/.secret.key`
- Caddy reverse proxy starts in HTTP mode on `:80` once configured from the UI
- All settings (proxy, databases, schedules, storage, notifications) are
  configurable from the **Settings** page in the web UI

> Use only `docker-compose.yml` for production. The bundled `docker-compose.override.yml`
> brings up demo postgres/mysql/minio for testing — drop or rename it on real deployments.

## Configuration management

**Primary path: web UI.** Everything is editable under Settings:

- **Proxy** — mode, domain, ACME method (DNS-01 / HTTP-01 / manual cert / self-signed), DNS provider
- **Backup config** — download a single zip containing your full configuration
  (config.json + proxy.json) and re-upload it to a fresh instance to restore
  an identical deployment. Optional: include backup files in the zip.
- **Encryption / Compression / Notifications** — global behaviour for backups
- **General** — config sync to S3 (auto-uploads on every change)

**Optional: environment variables.** Same settings can be pinned in `.env` —
useful for IaC / immutable deployments. Env vars take precedence on first
boot only; once `proxy.json` exists the UI / API / config sync are the
authoritative source.

## Reverse Proxy & TLS (Caddy)

DBManager ships a Caddy reverse proxy that fronts both backend (`/api`) and
frontend (`/`) on a single hostname. Configure via `.env`:

```bash
# Plain HTTP (dev)
DBMANAGER_PROXY_MODE=http
DBMANAGER_PROXY_DOMAIN=localhost

# HTTPS with Let's Encrypt (DNS-01 via Cloudflare)
DBMANAGER_PROXY_MODE=https
DBMANAGER_PROXY_DOMAIN=db.example.com
DBMANAGER_PROXY_ACME_METHOD=dns
DBMANAGER_PROXY_ACME_EMAIL=you@example.com
DBMANAGER_PROXY_DNS_PROVIDER=cloudflare
CF_API_TOKEN=...
```

Other ACME methods: `http-01` (needs public :80), `manual` (set
`DBMANAGER_PROXY_CERT_PATH` + `_KEY_PATH`), `selfsigned` (dev).

Interactive setup (TTY): `docker compose run --rm backend python main.py proxy bootstrap --force`.

At startup the backend prints the full effective configuration (env vars +
proxy state) — check `docker logs dbmanager-backend` to verify. Runtime
changes via `PUT /api/v1/proxy/config` hot-reload Caddy without dropping
connections; only ACME plugin changes require `POST /api/v1/proxy/restart`.

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
- **Database drivers**: psycopg2-binary, pymysql, pymssql
- **Cloud**: boto3
- **API**: fastapi, uvicorn
- **Utilities**: requests, zstandard

## Production Deployment

See [deployment/README.md](../deployment/README.md) for production setup with systemd/supervisor.
