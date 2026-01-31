#!/bin/bash
# Modify all databases with test data

SCRIPT_DIR="$(dirname "$0")"

echo "========================================="
echo "Modifying all databases..."
echo "========================================="

"$SCRIPT_DIR/modify_postgres.sh"
"$SCRIPT_DIR/modify_mysql.sh"
"$SCRIPT_DIR/modify_sqlserver.sh"

echo "========================================="
echo "All databases modified successfully!"
echo "========================================="
