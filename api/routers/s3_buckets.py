"""S3 bucket management endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from api.models.s3 import (
    S3BucketCreate,
    S3BucketUpdate,
    S3BucketResponse,
    S3TestResult
)
from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager

router = APIRouter()


@router.get("/s3-buckets", response_model=List[S3BucketResponse])
async def list_s3_buckets(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """List all S3 bucket configurations"""
    buckets = config_manager.config.get("s3_buckets", [])
    
    # Convert to response model (exclude secrets)
    response = []
    for bucket in buckets:
        bucket_copy = bucket.copy()
        bucket_copy.pop('access_key', None)
        bucket_copy.pop('secret_key', None)
        response.append(S3BucketResponse(**bucket_copy))
    
    return response


@router.get("/s3-buckets/{bucket_id}", response_model=S3BucketResponse)
async def get_s3_bucket(
    bucket_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get a specific S3 bucket by ID"""
    buckets = config_manager.config.get("s3_buckets", [])
    
    bucket = next((b for b in buckets if b.get("id") == bucket_id), None)
    
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"S3 bucket with ID {bucket_id} not found"
        )
    
    # Remove secrets from response
    bucket_copy = bucket.copy()
    bucket_copy.pop('access_key', None)
    bucket_copy.pop('secret_key', None)
    
    return S3BucketResponse(**bucket_copy)


@router.post("/s3-buckets", response_model=S3BucketResponse, status_code=status.HTTP_201_CREATED)
async def create_s3_bucket(
    bucket: S3BucketCreate,
    config_manager: ConfigManager = Depends(get_config_manager),
    db_manager: DBManager = Depends(get_db_manager)
):
    """Create a new S3 bucket configuration"""
    
    # Validate provider
    valid_providers = {'s3', 'minio', 'garage', 'other', 'aws', 'cloudflare'}
    if bucket.provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(sorted(valid_providers))}"
        )
    
    # Convert to dict
    bucket_dict = bucket.model_dump()
    
    # Generate ID
    buckets = config_manager.config.get("s3_buckets", [])
    existing_ids = [b.get("id", 0) for b in buckets]
    new_id = max(existing_ids) + 1 if existing_ids else 1
    bucket_dict["id"] = new_id
    
    # Add to config
    if "s3_buckets" not in config_manager.config:
        config_manager.config["s3_buckets"] = []
    
    config_manager.config["s3_buckets"].append(bucket_dict)
    config_manager.save_config()
    
    # Remove secrets from response
    bucket_copy = bucket_dict.copy()
    bucket_copy.pop('access_key', None)
    bucket_copy.pop('secret_key', None)
    
    return S3BucketResponse(**bucket_copy)


@router.put("/s3-buckets/{bucket_id}", response_model=S3BucketResponse)
async def update_s3_bucket(
    bucket_id: int,
    bucket: S3BucketUpdate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Update an existing S3 bucket configuration"""
    
    buckets = config_manager.config.get("s3_buckets", [])
    bucket_index = next((i for i, b in enumerate(buckets) if b.get("id") == bucket_id), None)
    
    if bucket_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"S3 bucket with ID {bucket_id} not found"
        )
    
    # Validate provider if being updated
    if bucket.provider is not None:
        valid_providers = {'s3', 'minio', 'garage', 'other', 'aws', 'cloudflare'}
        if bucket.provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider. Must be one of: {', '.join(sorted(valid_providers))}"
            )
    
    # Merge updates
    updated_bucket = buckets[bucket_index].copy()
    update_data = bucket.model_dump(exclude_unset=True)
    updated_bucket.update(update_data)
    
    # Save
    config_manager.config["s3_buckets"][bucket_index] = updated_bucket
    config_manager.save_config()
    
    # Remove secrets from response
    bucket_copy = updated_bucket.copy()
    bucket_copy.pop('access_key', None)
    bucket_copy.pop('secret_key', None)
    
    return S3BucketResponse(**bucket_copy)


@router.delete("/s3-buckets/{bucket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_s3_bucket(
    bucket_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Delete an S3 bucket configuration"""
    
    buckets = config_manager.config.get("s3_buckets", [])
    bucket = next((b for b in buckets if b.get("id") == bucket_id), None)
    
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"S3 bucket with ID {bucket_id} not found"
        )
    
    # Remove bucket
    config_manager.config["s3_buckets"] = [b for b in buckets if b.get("id") != bucket_id]
    config_manager.save_config()
    
    return None


@router.post("/s3-buckets/{bucket_id}/test", response_model=S3TestResult)
async def test_s3_connection(
    bucket_id: int,
    db_manager: DBManager = Depends(get_db_manager)
):
    """Test S3 bucket connection"""
    
    try:
        # Get bucket manager and test connection
        storage = db_manager.bucket_manager.get_storage(bucket_id)
        
        # Test by listing (this will verify credentials)
        storage.list_files()
        
        return S3TestResult(
            success=True,
            message="S3 connection successful"
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        return S3TestResult(
            success=False,
            message="S3 connection failed",
            error=str(e)
        )
