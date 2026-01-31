"""S3 bucket-related Pydantic models"""

from pydantic import BaseModel, Field
from typing import Optional


class S3BucketCreate(BaseModel):
    """Model for creating S3 bucket configuration"""
    name: str = Field(..., description="Bucket name/identifier")
    provider: str = Field(..., description="S3 provider (aws, cloudflare, minio)")
    endpoint_url: Optional[str] = Field(default=None, description="S3 endpoint URL")
    bucket: str = Field(..., description="Bucket name")
    access_key: str = Field(..., description="Access key")
    secret_key: str = Field(..., description="Secret key")
    region: Optional[str] = Field(default=None, description="AWS region")


class S3BucketUpdate(BaseModel):
    """Model for updating S3 bucket configuration"""
    name: Optional[str] = None
    provider: Optional[str] = None
    endpoint_url: Optional[str] = None
    bucket: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None


class S3BucketResponse(BaseModel):
    """Model for S3 bucket configuration response"""
    id: int
    name: str
    provider: str
    endpoint_url: Optional[str] = None
    bucket: str
    # Keys excluded for security
    region: Optional[str] = None


class S3TestResult(BaseModel):
    """Model for S3 connection test result"""
    success: bool
    message: str
    error: Optional[str] = None
