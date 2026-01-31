"""Global settings endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status

from api.models.settings import (
    CompressionSettings,
    EncryptionSettings,
    GlobalSettings
)
from api.dependencies import get_config_manager
from config import ConfigManager

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
    settings: EncryptionSettings,
    password: str = None,
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
        if not current_settings.get("password") and not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required when enabling encryption"
            )
    
    # Update settings
    config_manager.update_encryption_settings(
        enabled=settings.enabled,
        password=password if password else None
    )
    
    return EncryptionSettings(enabled=settings.enabled)
