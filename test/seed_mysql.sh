#!/bin/bash
# Seed MySQL database with test data

echo "Seeding MySQL database..."
docker exec -i dbmanager-mysql mysql -uroot -proot_password testdb < "$(dirname "$0")/sql/mysql_seed.sql"
echo "MySQL seeding completed!"
