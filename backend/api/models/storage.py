"""Storage target Pydantic models (S3, SMB, etc.)"""

from pydantic import BaseModel, Field, model_validator
from typing import Any, Dict, Literal, Optional


# ---------------------------------------------------------------------------
# Provider categories
# ---------------------------------------------------------------------------
S3_PROVIDERS = {"aws", "minio", "cloudflare", "garage", "s3", "other"}
SMB_PROVIDERS = {"smb"}
ALL_PROVIDERS = S3_PROVIDERS | SMB_PROVIDERS


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class StorageCreate(BaseModel):
    """Unified model for creating any storage target."""

    name: str = Field(..., min_length=2, description="Display name")
    provider: str = Field(..., description="Provider type")

    # --- S3 fields (required when provider is S3-compatible) ---
    bucket: Optional[str] = Field(default=None, description="S3 bucket name")
    endpoint_url: Optional[str] = Field(default=None, description="S3 endpoint URL")
    access_key: Optional[str] = Field(default=None, description="S3 access key")
    secret_key: Optional[str] = Field(default=None, description="S3 secret key")
    region: Optional[str] = Field(default=None, description="AWS region")

    # --- SMB fields (required when provider is 'smb') ---
    server: Optional[str] = Field(default=None, description="SMB server hostname/IP")
    share_name: Optional[str] = Field(default=None, description="SMB share name")
    smb_username: Optional[str] = Field(default=None, description="SMB username")
    smb_password: Optional[str] = Field(default=None, description="SMB password")
    domain: Optional[str] = Field(default=None, description="SMB domain (optional)")
    remote_path: Optional[str] = Field(
        default=None, description="Base path within SMB share"
    )

    @model_validator(mode="after")
    def validate_provider_fields(self) -> "StorageCreate":
        if self.provider not in ALL_PROVIDERS:
            raise ValueError(
                f"Invalid provider '{self.provider}'. "
                f"Must be one of: {', '.join(sorted(ALL_PROVIDERS))}"
            )

        if self.provider in S3_PROVIDERS:
            if not self.bucket:
                raise ValueError("'bucket' is required for S3 providers")
            if not self.access_key:
                raise ValueError("'access_key' is required for S3 providers")
            if not self.secret_key:
                raise ValueError("'secret_key' is required for S3 providers")

        if self.provider in SMB_PROVIDERS:
            if not self.server:
                raise ValueError("'server' is required for SMB provider")
            if not self.share_name:
                raise ValueError("'share_name' is required for SMB provider")
            if not self.smb_username:
                raise ValueError("'smb_username' is required for SMB provider")
            if not self.smb_password:
                raise ValueError("'smb_password' is required for SMB provider")

        return self


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
class StorageUpdate(BaseModel):
    """Partial update model — all fields optional."""

    name: Optional[str] = None
    provider: Optional[str] = None

    # S3
    bucket: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None

    # SMB
    server: Optional[str] = None
    share_name: Optional[str] = None
    smb_username: Optional[str] = None
    smb_password: Optional[str] = None
    domain: Optional[str] = None
    remote_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class StorageResponse(BaseModel):
    """Response model — secrets excluded."""

    id: int
    name: str
    provider: str

    # S3
    endpoint_url: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None

    # SMB
    server: Optional[str] = None
    share_name: Optional[str] = None
    domain: Optional[str] = None
    remote_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Test result (same for all providers)
# ---------------------------------------------------------------------------
class StorageTestResult(BaseModel):
    """Connection test result."""

    success: bool
    message: str
    error: Optional[str] = None
