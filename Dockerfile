FROM python:3.10-slim-bullseye

# Install system dependencies
# postgresql-client: for pg_dump/psql
# mariadb-client: for mysqldump/mysql
# cron: for scheduling
# curl, gnupg2, ca-certificates: for adding MS repos
RUN apt-get update && apt-get install -y \
    postgresql-client \
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

# Fix for .NET Core (mssql-scripter) globalization issue
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1


# Install Microsoft SQL Server Tools (sqlcmd)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg \
    && curl https://packages.microsoft.com/config/debian/11/prod.list | tee /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc-dev \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="$PATH:/opt/mssql-tools18/bin"

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create directory for data persistence
RUN mkdir -p /app/data

# Environment variable for app config
ENV DBMANAGER_DATA_DIR=/app/data

# Setup entrypoint script
RUN echo '#!/bin/bash\n\
    # Start cron in background\n\
    cron\n\
    # Keep container running or execute command\n\
    if [ "$#" -eq 0 ]; then\n\
    exec python main.py interactive\n\
    else\n\
    exec "$@"\n\
    fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
