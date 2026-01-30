#!/bin/bash
# Seed SQL Server database with test data

echo "Seeding SQL Server database..."
docker exec -i dbmanager-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'YourStrong@Password' -d testdb -C < "$(dirname "$0")/sql/sqlserver_seed.sql"
echo "SQL Server seeding completed!"
