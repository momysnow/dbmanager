# S3 Test Environment

This directory contains test infrastructure for S3-compatible storage testing with DBManager.

## Available S3 Providers

### 1. Minio

Minio is an S3-compatible object storage server, perfect for local testing.

**Start Minio**:
```bash
cd test/s3
docker-compose -f docker-compose-minio.yml up -d
```

**Access**:
- **S3 API**: `http://localhost:9000`
- **Web Console**: `http://localhost:9001`
- **Credentials**: 
  - User: `minioadmin`
  - Password: `minioadmin`

**Stop Minio**:
```bash
docker-compose -f docker-compose-minio.yml down
```

**Configure in DBManager**:
1. Run `python main.py interactive`
2. Go to "Manage S3 Buckets" → "Add S3 Bucket"
3. Fill in:
   - Name: `Minio Local`
   - Provider: `Minio`
   - Endpoint URL: `http://localhost:9000`
   - Access Key: `minioadmin`
   - Secret Key: `minioadmin`
   - Bucket: `dbmanager-backups` (create in Minio console first)

---

### 2. Garage

Garage is a lightweight, geo-distributed S3-compatible storage.

**Start Garage**:
```bash
cd test/s3
docker-compose -f docker-compose-garage.yml up -d
```

**Access**:
- **S3 API**: `http://localhost:3900`
- **Admin API**: `http://localhost:3902`

**Initial Setup** (first time only):
```bash
# Create layout
docker exec dbmanager-garage-test garage layout assign -z dc1 -c 1 \$(docker exec dbmanager-garage-test garage node id | grep "Node ID:")

# Create bucket
docker exec dbmanager-garage-test garage bucket create dbmanager-backups

# Create key
docker exec dbmanager-garage-test garage key new dbmanager-key

# Allow key to access bucket
docker exec dbmanager-garage-test garage bucket allow --read --write dbmanager-backups --key dbmanager-key
```

**Stop Garage**:
```bash
docker-compose -f docker-compose-garage.yml down
```

**Configure in DBManager**:
1. Run `python main.py interactive`
2. Go to "Manage S3 Buckets" → "Add S3 Bucket"
3. Fill in:
   - Name: `Garage Local`
   - Provider: `Garage`
   - Endpoint URL: `http://localhost:3900`
   - Access Key: (from key creation output)
   - Secret Key: (from key creation output)
   - Bucket: `dbmanager-backups`
   - Region: `garage`

---

## Testing Workflow

### 1. Setup Test S3 Storage
```bash
# Start Minio
cd test/s3
docker-compose -f docker-compose-minio.yml up -d

# Create bucket via web console (http://localhost:9001)
# Or via CLI:
docker exec dbmanager-minio-test mc mb local/dbmanager-backups
```

### 2. Configure DBManager
```bash
# Start DBManager
docker-compose up -d
docker attach dbmanager

# In interactive mode:
# 1. Add S3 bucket (Minio)
# 2. Configure database with S3 enabled
# 3. Set retention policies
```

### 3. Test Backup Flow
```bash
# Backup database
# - Verify local backup created
# - Verify S3 upload successful
# - Check retention cleanup

# Edit database to change bucket
# - Verify migration prompt
# - Test bucket migration
```

### 4. Test Config Sync
```bash
# Settings → Configure Config Sync
# - Select bucket
# - Upload config
# - Verify in S3
# - Download on new instance
```

---

## teardown

```bash
# Minio
docker-compose -f docker-compose-minio.yml down -v

# Garage
docker-compose -f docker-compose-garage.yml down -v
```

---

## Notes

- Minio is easier for quick testing
- Garage is better for testing distributed scenarios
- Both are fully S3-compatible
- Test credentials are for local testing only
