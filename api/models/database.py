"""Database-related Pydantic models"""

from pydantic import BaseModel, Field
from typing import Optional


class DatabaseCreate(BaseModel):
    """Model for creating a new database configuration"""
    name: str = Field(..., description="Database name/identifier")
    provider: str = Field(..., description="Database provider (postgres, mysql, sqlserver)")
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    s3_enabled: bool = Field(default=False, description="Enable S3 backup")
    s3_bucket_id: Optional[int] = Field(default=None, description="S3 bucket ID")
    retention: int = Field(default=0, description="Local retention days (0 = infinite)")
    s3_retention: int = Field(default=0, description="S3 retention days (0 = infinite)")


class DatabaseUpdate(BaseModel):
    """Model for updating database configuration"""
    name: Optional[str] = None
    provider: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    s3_enabled: Optional[bool] = None
    s3_bucket_id: Optional[int] = None
    retention: Optional[int] = None
    s3_retention: Optional[int] = None


class DatabaseResponse(BaseModel):
    """Model for database configuration response"""
    id: int
    name: str
    provider: str
    host: str
    port: int
    database: str
    username: str
    # Password is excluded for security
    s3_enabled: bool
    s3_bucket_id: Optional[int] = None
    retention: int
    s3_retention: int


class DatabaseTestResult(BaseModel):
    """Model for database connection test result"""
    success: bool
    message: str
    error: Optional[str] = None
