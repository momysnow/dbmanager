#!/bin/bash
# Modify SQL Server database test data

echo "Modifying SQL Server database..."
docker exec -i dbmanager-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'YourStrong@Password' -d testdb -C < "$(dirname "$0")/sql/sqlserver_modify.sql"
echo "SQL Server modification completed!"
