#!/bin/bash
# Seed PostgreSQL database with test data

echo "Seeding PostgreSQL database..."
docker exec -i dbmanager-postgres psql -U postgres -d testdb < "$(dirname "$0")/sql/postgres_seed.sql"
echo "PostgreSQL seeding completed!"
