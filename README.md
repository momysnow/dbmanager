# DB Manager CLI

A simple, guided command-line tool for managing database connections, checking status, and performing backups/restores for PostgreSQL, MySQL and Microsoft SQL Server.

## Features

- **Guided Interface**: Interactive shell to manage databases effortlessly.
- **Multiple Providers**: Supports PostgreSQL, MySQL and Microsoft SQL Server.
- **Backups**: Create manual backups or schedule them via Cron.
- **Restores**: Easy restoration from existing backup files.
- **Docker Support**: Fully containerized with persistent storage.

## Quick Start (Docker)

0. **Prerequisites**: Docker & Docker Compose.
1. **Navigate to Directory**:
   Ensure you are in the project folder where `docker-compose.yml` is located:
   ```bash
   cd dbmanager
   ```
2. **Start the Service**:
   ```bash
   docker-compose up -d
   ```
2. **Open the CLI**:
   ```bash
   docker-compose exec -it app python main.py interactive
   ```

## Quick Start (Local)

0. **Prerequisites**: Python 3.10+, `pg_dump`/`psql` (for Postgres), `mysqldump`/`mysql` (for MySQL) installed.
1. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Run the CLI**:
   ```bash
   python main.py interactive
   ```

## Commands

Once in the interactive shell (`interactive` command), you can:

- **List Databases**: See all configured connections.
- **Add Database**: distinct alias, host, user, password, etc.
- **Check Status**: Verify connectivity.
- **Backup**: Run an immediate backup.
- **Restore**: Overwrite a database with a previous backup.
- **Schedule**: Set a cron schedule (e.g., `0 0 * * *` for daily midnight backups).

## Configuration

- **Docker**: Data is stored in the `./data` folder in your project root.
- **Local**: Data is stored in `~/.dbmanager/` by default, or defined by `DBMANAGER_DATA_DIR` env var.

## Troubleshooting

- **Connection Failed**: Ensure you are using the correct host. Inside Docker, use `host.docker.internal` to connect to a DB running on your host machine.
- **Cron Not Running**: Ensure the container is running (`docker-compose ps`).
