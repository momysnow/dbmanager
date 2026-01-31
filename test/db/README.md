# Database Test Scripts

This directory contains test scripts to seed and modify test data in the development databases (PostgreSQL, MySQL, and SQL Server).

## Prerequisites

- Docker and Docker Compose must be installed
- **You must be in the project root directory** (where `docker-compose.yml` is located)
- Database containers must be running with the following services defined in `docker-compose.yml`:
  - `dbmanager-postgres` (PostgreSQL)
  - `dbmanager-mysql` (MySQL)  
  - `dbmanager-sqlserver` (SQL Server)
- Each database must have a `testdb` database created

> [!WARNING]
> If you haven't set up the database services yet, these scripts won't work. The database containers need to be properly configured in your `docker-compose.yml` first.


## Available Scripts

### Individual Database Scripts

**Seeding (initial data):**
- `seed_postgres.sh` - Seeds PostgreSQL with test data
- `seed_mysql.sh` - Seeds MySQL with test data
- `seed_sqlserver.sh` - Seeds SQL Server with test data

**Modifying (updates):**
- `modify_postgres.sh` - Modifies existing PostgreSQL test data
- `modify_mysql.sh` - Modifies existing MySQL test data
- `modify_sqlserver.sh` - Modifies existing SQL Server test data

### Master Scripts

- `seed_all.sh` - Seeds all three databases in sequence
- `modify_all.sh` - Modifies all three databases in sequence

## How to Use

### macOS / Linux

Scripts are ready to use directly:

```bash
# Seed all databases
./test/seed_all.sh

# Seed only PostgreSQL
./test/seed_postgres.sh

# Modify all databases
./test/modify_all.sh
```

### Windows

You have several options:

**Option 1: Git Bash (Recommended)**
```bash
# Same commands as macOS/Linux
./test/seed_all.sh
```

**Option 2: WSL (Windows Subsystem for Linux)**
```bash
# Same commands as macOS/Linux
./test/seed_all.sh
```

**Option 3: PowerShell**

You'll need to run the docker commands directly:

```powershell
# Seed PostgreSQL
Get-Content test/sql/postgres_seed.sql | docker exec -i dbmanager-postgres psql -U postgres -d testdb

# Seed MySQL
Get-Content test/sql/mysql_seed.sql | docker exec -i dbmanager-mysql mysql -uroot -proot_password testdb

# Seed SQL Server
Get-Content test/sql/sqlserver_seed.sql | docker exec -i dbmanager-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "YourStrong@Password" -d testdb -C
```

**Option 4: CMD (Command Prompt)**

```cmd
REM Seed PostgreSQL
type test\sql\postgres_seed.sql | docker exec -i dbmanager-postgres psql -U postgres -d testdb

REM Seed MySQL
type test\sql\mysql_seed.sql | docker exec -i dbmanager-mysql mysql -uroot -proot_password testdb

REM Seed SQL Server
type test\sql\sqlserver_seed.sql | docker exec -i dbmanager-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "YourStrong@Password" -d testdb -C
```


## How It Works

Each script:

1. Connects to the respective database container using `docker exec`
2. Pipes the SQL file content into the database client
3. Executes the SQL commands to create tables and insert/update data

### Script Breakdown

For example, `seed_postgres.sh`:

```bash
#!/bin/bash
# Locates the SQL file relative to the script
docker exec -i dbmanager-postgres \     # Run command in PostgreSQL container
  psql -U postgres -d testdb \          # PostgreSQL client with user and database
  < sql/postgres_seed.sql               # Feed SQL file as input
```

## SQL Files

The actual SQL commands are in the `sql/` subdirectory:

- `postgres_seed.sql` / `postgres_modify.sql` - PostgreSQL SQL
- `mysql_seed.sql` / `mysql_modify.sql` - MySQL SQL
- `sqlserver_seed.sql` / `sqlserver_modify.sql` - SQL Server SQL (T-SQL)

## Troubleshooting

**"Path not found" / "Impossibile trovare il percorso"** - You're in the wrong directory:
```bash
# Navigate to project root first
cd /path/to/dbmanager
# On Windows:
cd C:\path\to\dbmanager
```

**"Permission denied"** - Make scripts executable:
```bash
chmod +x test/*.sh
```

**"Container not found"** - Ensure containers are running:
```bash
docker compose up -d
```

**"Database does not exist"** - The database services aren't configured. You need to add PostgreSQL, MySQL, and SQL Server services to your `docker-compose.yml` with `testdb` databases created.

## Docker Container Names

The scripts use these container names (as defined in `docker-compose.yml`):
- `dbmanager-postgres` - PostgreSQL container
- `dbmanager-mysql` - MySQL container
- `dbmanager-sqlserver` - SQL Server container

If your container names differ, update the scripts accordingly.
