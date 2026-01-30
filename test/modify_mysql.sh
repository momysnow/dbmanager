#!/bin/bash
# Modify MySQL database test data

echo "Modifying MySQL database..."
docker exec -i dbmanager-mysql mysql -uroot -proot_password testdb < "$(dirname "$0")/sql/mysql_modify.sql"
echo "MySQL modification completed!"
