"""Settings-related Pydantic models"""

from pydantic import BaseModel, Field
from typing import Optional


class CompressionSettings(BaseModel):
    """Model for compression settings"""
    enabled: bool = Field(default=False, description="Compression enabled")
    algorithm: str = Field(default="gzip", description="Compression algorithm")
    level: int = Field(default=6, description="Compression level")


class EncryptionSettings(BaseModel):
    """Model for encryption settings"""
    enabled: bool = Field(default=False, description="Encryption enabled")
    # Password not exposed via API for security


class EncryptionUpdate(BaseModel):
    """Model for updating encryption settings"""
    enabled: bool = Field(default=False, description="Encryption enabled")
    password: Optional[str] = Field(default=None, description="Encryption password")


class ConfigSyncSettings(BaseModel):
    """Model for config sync settings"""
    bucket_id: Optional[int] = Field(default=None, description="S3 bucket ID for config sync")


class ConfigSyncStatus(BaseModel):
    """Model for config sync status"""
    enabled: bool
    bucket_id: Optional[int] = None
    bucket_name: Optional[str] = None


class ConfigSyncInfo(BaseModel):
    """Model for config sync info"""
    enabled: bool
    bucket_id: Optional[int] = None
    bucket_name: Optional[str] = None
    local_mtime: Optional[str] = None
    s3_mtime: Optional[str] = None
    is_local_newer: Optional[bool] = None
    is_s3_newer: Optional[bool] = None


class GlobalSettings(BaseModel):
    """Model for global settings"""
    compression: CompressionSettings
    encryption: EncryptionSettings
