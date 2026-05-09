"""Storage target Pydantic models (S3, SMB, etc.)"""

import ipaddress
import os
import socket
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, Literal, Optional


# ---------------------------------------------------------------------------
# Provider categories
# ---------------------------------------------------------------------------
S3_PROVIDERS = {"aws", "minio", "cloudflare", "garage", "s3", "other"}
SMB_PROVIDERS = {"smb"}
ALL_PROVIDERS = S3_PROVIDERS | SMB_PROVIDERS


def _assert_safe_endpoint_url(url: Optional[str]) -> Optional[str]:
    """Refuse loopback / link-local / multicast / reserved targets to block
    SSRF (e.g. an admin pointing endpoint_url at 169.254.169.254 to harvest
    cloud-instance metadata via boto3). Private RFC1918 ranges are allowed
    on purpose: legitimate deployments often run MinIO/Garage on the same
    Docker bridge or VPC.

    Set DBMANAGER_ALLOW_INTERNAL_STORAGE=1 to bypass for trusted dev setups
    (e.g. a custom unit test against 127.0.0.1).
    """
    if not url:
        return url
    if os.getenv("DBMANAGER_ALLOW_INTERNAL_STORAGE", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return url

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid endpoint_url: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"endpoint_url must be http(s), got {parsed.scheme!r}"
        )
    host = parsed.hostname
    if not host:
        raise ValueError("endpoint_url missing host")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(
            f"endpoint_url host {host!r} did not resolve: {exc}"
        ) from exc

    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            raise ValueError(f"endpoint_url host {host!r} resolved to unparseable {ip!r}")
        if (
            addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            raise ValueError(
                f"endpoint_url host {host!r} resolves to a non-routable IP "
                f"({ip}); refused for SSRF protection."
            )
    return url


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class StorageCreate(BaseModel):
    """Unified model for creating any storage target."""

    model_config = {"extra": "forbid"}

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

    @field_validator("endpoint_url")
    @classmethod
    def _validate_endpoint_url(cls, v: Optional[str]) -> Optional[str]:
        return _assert_safe_endpoint_url(v)

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

    model_config = {"extra": "forbid"}

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

    @field_validator("endpoint_url")
    @classmethod
    def _validate_endpoint_url(cls, v: Optional[str]) -> Optional[str]:
        return _assert_safe_endpoint_url(v)


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
