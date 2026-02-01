"""Global settings endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import FileResponse
import os
import tempfile

from api.models.settings import (
    CompressionSettings,
    EncryptionSettings,
    GlobalSettings,
    EncryptionUpdate,
    ConfigSyncSettings,
    ConfigSyncStatus
)
from api.dependencies import get_config_manager
from config import ConfigManager
from core.config_sync import ConfigSync
from core.bucket_manager import BucketManager
from utils.config_export import ConfigExporter

router = APIRouter()


@router.get("/settings", response_model=GlobalSettings)
async def get_settings(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get all global settings"""
    global_settings = config_manager.get_global_settings()
    
    # Convert to response models
    compression = CompressionSettings(**global_settings.get("compression", {}))
    
    # For encryption, don't expose password
    encryption_data = global_settings.get("encryption", {})
    encryption = EncryptionSettings(
        enabled=encryption_data.get("enabled", False)
    )
    
    return GlobalSettings(
        compression=compression,
        encryption=encryption
    )


@router.get("/settings/compression", response_model=CompressionSettings)
async def get_compression_settings(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get compression settings"""
    settings = config_manager.get_compression_settings()
    return CompressionSettings(**settings)


@router.put("/settings/compression", response_model=CompressionSettings)
async def update_compression_settings(
    settings: CompressionSettings,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Update compression settings"""
    
    # Validate algorithm if enabled
    if settings.enabled:
        from core.compression import get_available_algorithms
        
        available = get_available_algorithms()
        if settings.algorithm not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Algorithm '{settings.algorithm}' not available. Available: {', '.join(available)}"
            )
    
    # Update settings
    config_manager.update_compression_settings(
        enabled=settings.enabled,
        algorithm=settings.algorithm,
        level=settings.level
    )
    
    return settings


@router.get("/settings/encryption", response_model=EncryptionSettings)
async def get_encryption_settings(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get encryption settings (password not included)"""
    settings = config_manager.get_encryption_settings()
    
    return EncryptionSettings(
        enabled=settings.get("enabled", False)
    )


@router.put("/settings/encryption", response_model=EncryptionSettings)
async def update_encryption_settings(
    settings: EncryptionUpdate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Update encryption settings"""
    
    # Validate encryption is available if enabling
    if settings.enabled:
        from core.encryption import is_encryption_available
        
        if not is_encryption_available():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encryption not available. Install: pip install cryptography"
            )
        
        # Check if password is provided when enabling
        current_settings = config_manager.get_encryption_settings()
        if not current_settings.get("password") and not settings.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required when enabling encryption"
            )
    
    # Update settings
    config_manager.update_encryption_settings(
        enabled=settings.enabled,
        password=settings.password if settings.password else None
    )
    
    return EncryptionSettings(enabled=settings.enabled)


@router.get("/settings/config-sync", response_model=ConfigSyncStatus)
async def get_config_sync_status(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get config sync status"""
    bucket_id = config_manager.config.get("config_sync_bucket_id")
    bucket_name = None
    if bucket_id:
        bucket_name = BucketManager(config_manager).get_bucket_name(bucket_id)

    return ConfigSyncStatus(
        enabled=bool(bucket_id),
        bucket_id=bucket_id,
        bucket_name=bucket_name
    )


@router.put("/settings/config-sync", response_model=ConfigSyncStatus)
async def update_config_sync(
    settings: ConfigSyncSettings,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Enable or disable config sync"""
    if settings.bucket_id is not None:
        bucket = BucketManager(config_manager).get_bucket(settings.bucket_id)
        if not bucket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="S3 bucket not found"
            )

    config_sync = ConfigSync(BucketManager(config_manager), config_manager)
    config_sync.set_config_bucket(settings.bucket_id)

    bucket_name = None
    if settings.bucket_id:
        bucket_name = BucketManager(config_manager).get_bucket_name(settings.bucket_id)

    return ConfigSyncStatus(
        enabled=bool(settings.bucket_id),
        bucket_id=settings.bucket_id,
        bucket_name=bucket_name
    )


@router.post("/settings/config-sync/sync", response_model=dict)
async def sync_config_to_s3(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Sync config to S3 now"""
    config_sync = ConfigSync(BucketManager(config_manager), config_manager)
    success = config_sync.sync_to_s3()
    return {"success": success}


@router.post("/settings/config-sync/download", response_model=dict)
async def download_config_from_s3(
    force: bool = False,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Download config from S3"""
    config_sync = ConfigSync(BucketManager(config_manager), config_manager)
    success = config_sync.sync_from_s3(force=force)
    return {"success": success}


@router.post("/settings/export")
async def export_configuration(
    include_backups: bool = False,
    format: str = "zip",
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Export configuration to a file"""
    exporter = ConfigExporter(config_manager)

    if format == "json":
        path = exporter.export_to_json()
        return FileResponse(path, media_type="application/json", filename=os.path.basename(path))

    path = exporter.export_config(include_backups=include_backups)
    return FileResponse(path, media_type="application/zip", filename=os.path.basename(path))


@router.post("/settings/import", response_model=dict)
async def import_configuration(
    file: UploadFile = File(...),
    merge: bool = True,
    restore_backups: bool = False,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Import configuration from a file"""
    exporter = ConfigExporter(config_manager)

    suffix = os.path.splitext(file.filename or "")[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await file.read())
        temp_path = temp_file.name

    try:
        if suffix == ".json":
            summary = exporter.import_from_json(temp_path, merge=merge)
        else:
            summary = exporter.import_config(temp_path, merge=merge, restore_backups=restore_backups)
        return summary
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass
