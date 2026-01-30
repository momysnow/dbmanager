#!/bin/bash
# Seed all databases with test data

SCRIPT_DIR="$(dirname "$0")"

echo "========================================="
echo "Seeding all databases..."
echo "========================================="

"$SCRIPT_DIR/seed_postgres.sh"
"$SCRIPT_DIR/seed_mysql.sh"
"$SCRIPT_DIR/seed_sqlserver.sh"

echo "========================================="
echo "All databases seeded successfully!"
echo "========================================="
