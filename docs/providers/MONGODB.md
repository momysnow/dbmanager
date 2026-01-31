# MongoDB Provider

## Requirements

**In Docker (included in image):**
MongoDB Database Tools are automatically installed in the Docker container.

**For local development (outside Docker):**
```bash
# macOS
brew install mongodb-database-tools

# Ubuntu/Debian
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update
sudo apt-get install -y mongodb-database-tools
```

## Configuration

### Using URI (recommended)
```json
{
  "provider": "mongodb",
  "uri": "mongodb://username:password@localhost:27017/mydb"
}
```

### Using individual parameters
```json
{
  "provider": "mongodb",
  "host": "localhost",
  "port": 27017,
  "database": "mydb",
  "username": "user",
  "password": "pass"
}
```

## Features

- **mongodump**: Creates BSON backup
- **mongorestore**: Restores from backup
- **--gzip**: Automatic compression
- **--drop**: Drops collections before restore
- **tar.gz archive**: Final backup is compressed archive
- **Progress tracking**: Real-time progress updates

## Backup Format

Backups are saved as `.tar.gz` archives containing:
- BSON files (collection data)
- Metadata files
- All compressed with gzip

## Notes

- Backup includes all collections in the database
- Restore drops existing collections (--drop flag)
- 1 hour timeout for large databases
- Compatible with mongosh and legacy mongo shell
