#!/bin/bash
# Modify PostgreSQL database test data

echo "Modifying PostgreSQL database..."
docker exec -i dbmanager-postgres psql -U postgres -d testdb < "$(dirname "$0")/sql/postgres_modify.sql"
echo "PostgreSQL modification completed!"
