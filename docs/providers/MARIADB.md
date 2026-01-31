# MariaDB Provider

## Overview

MariaDB is a fork of MySQL and uses the **same protocol and tools**. 

The MariaDB provider inherits from MySQLProvider, so all MySQL features work identically.

## Requirements

```bash
# macOS
brew install mariadb

# Ubuntu/Debian
sudo apt-get install mariadb-client
```

## Configuration

Same as MySQL:
```json
{
  "provider": "mariadb",
  "host": "localhost",
  "port": 3306,
  "database": "mydb",
  "username": "user",
  "password": "pass"
}
```

## Features

All MySQL features:
- **mysqldump**: Creates SQL dump
- **mysql**: Restores from dump
- **--single-transaction**: Consistent backup (InnoDB)
- **--routines**: Includes stored procedures
- **--triggers**: Includes triggers
- **Progress tracking**: Real-time updates

## Why Separate Provider?

1. **Clear identification**: Users know MariaDB is explicitly supported
2. **Future features**: MariaDB-specific optimizations can be added
3. **Better UX**: Configuration explicitly shows "mariadb" provider

## Notes

- Default port: 3306 (same as MySQL)
- Uses mysqldump/mysql tools
- 100% compatible with MySQL provider
- Supports all MySQL backup options
