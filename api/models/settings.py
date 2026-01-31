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


class GlobalSettings(BaseModel):
    """Model for global settings"""
    compression: CompressionSettings
    encryption: EncryptionSettings
