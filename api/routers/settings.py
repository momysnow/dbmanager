"""Global settings endpoints"""

from datetime import datetime
import os
import tempfile
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from api.models.settings import (
    CompressionSettings,
    EncryptionSettings,
    GlobalSettings,
    EncryptionUpdate,
    ConfigSyncSettings,
    ConfigSyncStatus,
    ConfigSyncInfo,
)
from api.dependencies import get_config_manager
from config import ConfigManager
from core.config_sync import ConfigSync
from core.storage_manager import StorageManager
from utils.config_export import ConfigExporter

from config import CONFIG_FILE

router = APIRouter()


@router.get("/settings", response_model=GlobalSettings)
async def get_settings(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> GlobalSettings:
    """Get all global settings"""
    global_settings = config_manager.get_global_settings()

    # Convert to response models
    compression = CompressionSettings(**global_settings.get("compression", {}))

    # For encryption, don't expose password
    encryption_data = global_settings.get("encryption", {})
    encryption = EncryptionSettings(enabled=encryption_data.get("enabled", False))

    return GlobalSettings(compression=compression, encryption=encryption)


@router.get("/settings/compression", response_model=CompressionSettings)
async def get_compression_settings(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> CompressionSettings:
    """Get compression settings"""
    settings = config_manager.get_compression_settings()
    return CompressionSettings(**settings)


@router.put("/settings/compression", response_model=CompressionSettings)
async def update_compression_settings(
    settings: CompressionSettings,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> CompressionSettings:
    """Update compression settings"""

    # Validate algorithm if enabled
    if settings.enabled:
        from core.compression import get_available_algorithms

        available = get_available_algorithms()
        if settings.algorithm not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Algorithm '{settings.algorithm}' not available. "
                    f"Available: {', '.join(available)}"
                ),
            )

    # Update settings
    config_manager.update_compression_settings(
        enabled=settings.enabled, algorithm=settings.algorithm, level=settings.level
    )

    return settings


@router.get("/settings/encryption", response_model=EncryptionSettings)
async def get_encryption_settings(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> EncryptionSettings:
    """Get encryption settings (password not included)"""
    settings = config_manager.get_encryption_settings()

    return EncryptionSettings(enabled=settings.get("enabled", False))


@router.put("/settings/encryption", response_model=EncryptionSettings)
async def update_encryption_settings(
    settings: EncryptionUpdate,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> EncryptionSettings:
    """Update encryption settings"""

    # Validate encryption is available if enabling
    if settings.enabled:
        from core.encryption import is_encryption_available

        if not is_encryption_available():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encryption not available. Install: pip install cryptography",
            )

        # Check if password is provided when enabling
        current_settings = config_manager.get_encryption_settings()
        if not current_settings.get("password") and not settings.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required when enabling encryption",
            )

    # Update settings
    config_manager.update_encryption_settings(
        enabled=settings.enabled,
        password=settings.password if settings.password else None,
    )

    return EncryptionSettings(enabled=settings.enabled)


@router.get("/settings/config-sync", response_model=ConfigSyncStatus)
async def get_config_sync_status(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> ConfigSyncStatus:
    """Get config sync status"""
    target_id = config_manager.config.get("config_sync_bucket_id")
    target_name = None
    if target_id:
        target_name = StorageManager(config_manager).get_storage_name(target_id)

    # We map target_id to bucket_id for API compatibility
    return ConfigSyncStatus(
        enabled=bool(target_id), bucket_id=target_id, bucket_name=target_name
    )


@router.put("/settings/config-sync", response_model=ConfigSyncStatus)
async def update_config_sync(
    settings: ConfigSyncSettings,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> ConfigSyncStatus:
    """Enable or disable config sync"""
    if settings.bucket_id is not None:
        target = StorageManager(config_manager).get_storage_config(settings.bucket_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Storage target not found"
            )

    config_sync = ConfigSync(StorageManager(config_manager), config_manager)
    config_sync.set_config_target(settings.bucket_id)

    target_name = None
    if settings.bucket_id:
        target_name = StorageManager(config_manager).get_storage_name(
            settings.bucket_id
        )

    return ConfigSyncStatus(
        enabled=bool(settings.bucket_id),
        bucket_id=settings.bucket_id,
        bucket_name=target_name,
    )


@router.post("/settings/config-sync/sync", response_model=dict)
async def sync_config_to_storage(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, bool]:
    """Sync config to storage now"""
    config_sync = ConfigSync(StorageManager(config_manager), config_manager)
    success = config_sync.sync_to_storage()
    return {"success": success}


@router.post("/settings/config-sync/download", response_model=dict)
async def download_config_from_storage(
    force: bool = False, config_manager: ConfigManager = Depends(get_config_manager)
) -> Dict[str, bool]:
    """Download config from storage"""
    config_sync = ConfigSync(StorageManager(config_manager), config_manager)
    success = config_sync.sync_from_storage(force=force, interactive=False)
    return {"success": success}


@router.get("/settings/config-sync/info", response_model=ConfigSyncInfo)
async def get_config_sync_info(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> ConfigSyncInfo:
    """Get config sync info and comparison"""
    target_id = config_manager.config.get("config_sync_bucket_id")
    target_name = None
    if target_id:
        target_name = StorageManager(config_manager).get_storage_name(target_id)

    config_sync = ConfigSync(StorageManager(config_manager), config_manager)
    remote_info = config_sync.get_storage_config_info() if target_id else None
    remote_mtime = remote_info.get("last_modified") if remote_info else None

    local_mtime = None
    if CONFIG_FILE.exists():
        local_mtime = datetime.fromtimestamp(CONFIG_FILE.stat().st_mtime)

    is_local_newer = None
    is_remote_newer = None
    if local_mtime and remote_mtime:
        remote_compare = (
            remote_mtime.replace(tzinfo=None) if remote_mtime.tzinfo else remote_mtime
        )
        is_local_newer = local_mtime > remote_compare
        is_remote_newer = remote_compare > local_mtime

    return ConfigSyncInfo(
        enabled=bool(target_id),
        bucket_id=target_id,
        bucket_name=target_name,
        local_mtime=local_mtime.isoformat() if local_mtime else None,
        s3_mtime=remote_mtime.isoformat() if remote_mtime else None,
        is_local_newer=is_local_newer,
        is_s3_newer=is_remote_newer,
    )


@router.post("/settings/export")
async def export_configuration(
    include_backups: bool = False,
    format: str = "zip",
    config_manager: ConfigManager = Depends(get_config_manager),
) -> FileResponse:
    """Export configuration to a file"""
    exporter = ConfigExporter(config_manager)

    if format == "json":
        path = exporter.export_to_json()
        return FileResponse(
            path, media_type="application/json", filename=os.path.basename(path)
        )

    path = exporter.export_config(include_backups=include_backups)
    return FileResponse(
        path, media_type="application/zip", filename=os.path.basename(path)
    )


@router.post("/settings/import", response_model=dict)
async def import_configuration(
    file: UploadFile = File(...),
    merge: bool = True,
    restore_backups: bool = False,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
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
            summary = exporter.import_config(
                temp_path, merge=merge, restore_backups=restore_backups
            )
        return summary
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass
