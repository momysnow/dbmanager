"""Database-related Pydantic models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any


class ConnectionParams(BaseModel):
    """Model for database connection parameters"""

    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    # Optional because some providers like S3 might not strictly use it.
    database: Optional[str] = Field(None, description="Database name")
    user: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password")
    # Add other provider-specific fields as optional
    trust_certificate: Optional[bool] = Field(
        False, description="Trust server certificate (SQL Server)"
    )
    driver: Optional[str] = Field(None, description="ODBC Driver (SQL Server)")

    # Allow extra fields for flexibility
    class Config:
        extra = "allow"


class DatabaseCreate(BaseModel):
    """Model for creating a new database configuration"""

    name: str = Field(..., description="Database name/identifier")
    provider: str = Field(
        ..., description="Database provider (postgres, mysql, sqlserver)"
    )
    params: ConnectionParams = Field(..., description="Connection parameters")
    s3_enabled: bool = Field(default=False, description="Enable S3 backup")
    s3_bucket_id: Optional[int] = Field(default=None, description="S3 bucket ID")
    retention: int = Field(default=0, description="Local retention days (0 = infinite)")
    s3_retention: int = Field(default=0, description="S3 retention days (0 = infinite)")


class DatabaseUpdate(BaseModel):
    """Model for updating database configuration"""

    name: Optional[str] = None
    provider: Optional[str] = None
    params: Optional[ConnectionParams] = None
    s3_enabled: Optional[bool] = None
    s3_bucket_id: Optional[int] = None
    retention: Optional[int] = None
    s3_retention: Optional[int] = None


class DatabaseResponse(BaseModel):
    """Model for database configuration response"""

    id: int
    name: str
    provider: str
    params: Dict[
        str, Any
    ]  # Use generic dict to include all fields but processed (no password)
    s3_enabled: bool = False
    s3_bucket_id: Optional[int] = None
    retention: int = 0
    s3_retention: int = 0

    @validator("params")
    def remove_password(cls, v: Any) -> Any:
        """Ensure password is not returned in response"""
        if isinstance(v, dict):
            # Create a copy to avoid modifying original info
            v_copy = v.copy()
            v_copy.pop("password", None)
            return v_copy
        return v


class DatabaseTestResult(BaseModel):
    """Model for database connection test result"""

    success: bool
    message: str
    error: Optional[str] = None
