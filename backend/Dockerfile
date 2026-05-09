FROM python:3.10-slim-bullseye

# Install system dependencies
# postgresql-client: for pg_dump/psql
# mariadb-client: for mysqldump/mysql
# cron: for scheduling
# curl, gnupg2, ca-certificates: for adding MS repos
RUN apt-get update && apt-get install -y --fix-missing --no-install-recommends \
    mariadb-client \
    cron \
    nano \
    curl \
    gnupg2 \
    ca-certificates \
    lsb-release \
    libicu-dev \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Add PostgreSQL APT repository and install PostgreSQL 18 client tools
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bullseye-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

# Fix for .NET Core (mssql-scripter) globalization issue
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1


# Install Microsoft SQL Server Tools (sqlcmd)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg \
    && curl https://packages.microsoft.com/config/debian/11/prod.list | tee /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc-dev \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc \
    && rm -rf /var/lib/apt/lists/*

# Install MongoDB Database Tools
# Note: MongoDB provides packages for Debian 11 (Bullseye) but failures observed on arm64
# RUN curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/mongodb-org-6.0.gpg \
#     && echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/debian bullseye/mongodb-org/6.0 main" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list \
#     && apt-get update \
#     && apt-get install -y mongodb-database-tools \
#     && rm -rf /var/lib/apt/lists/*

ENV PATH="$PATH:/opt/mssql-tools18/bin"

WORKDIR /app

# Install from the locked, deterministic version list. requirements.in is
# the human-edited input; requirements.lock is what the image actually
# installs. See the header of requirements.lock for regeneration steps.
COPY requirements.lock .
RUN pip install --no-cache-dir --no-deps --timeout=300 -r requirements.lock

# Copy source code
COPY . .

# Create directory for data persistence
RUN mkdir -p /app/data

# Environment variable for app config
ENV DBMANAGER_DATA_DIR=/app/data

# Entrypoint: uvicorn becomes the foreground process via `exec`, so SIGTERM
# from `docker stop` reaches the lifespan handler (graceful shutdown drains
# audit queue, disposes DB engine, cancels in-flight backups). Compose runs
# this with `init: true`, so an init shim (PID 1) forwards SIGTERM to this
# bash script, which forwards it to uvicorn via `exec`.
#
# The legacy "API in background + tail -f" only kicks in when CLI mode is
# explicitly enabled, where we need a TTY-friendly main loop.
RUN printf '#!/bin/bash\nset -e\n\
cron\n\
python main.py proxy bootstrap || echo "[entrypoint] proxy bootstrap skipped"\n\
if [ "$DBMANAGER_ENABLE_CLI" = "true" ]; then\n\
    python main.py start-api\n\
    exec python main.py interactive\n\
else\n\
    exec python api_server.py\n\
fi\n' > /entrypoint.sh && chmod +x /entrypoint.sh

# NOTE: Backend currently runs as root because the system `cron` daemon
# (used by core/cron.py via python-crontab) requires it. If cron is moved to
# an in-process scheduler (e.g. APScheduler), switch to a non-root USER here.

ENTRYPOINT ["/entrypoint.sh"]
