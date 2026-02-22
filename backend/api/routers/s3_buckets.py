"""Storage target management endpoints (S3, SMB, etc.)"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from api.models.storage import (
    StorageCreate,
    StorageUpdate,
    StorageResponse,
    StorageTestResult,
)
from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager

router = APIRouter()

# All storage targets live under this config key
CONFIG_KEY = "storage_targets"

# Fields to strip from responses (secrets)
SECRET_FIELDS = {"access_key", "secret_key", "smb_password"}


def _get_targets(config_manager: ConfigManager) -> list:
    return config_manager.config.get(CONFIG_KEY, [])


def _to_response(target: dict) -> StorageResponse:
    """Convert a raw config dict to a response model (strip secrets)."""
    clean = {k: v for k, v in target.items() if k not in SECRET_FIELDS}
    return StorageResponse(**clean)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/storage", response_model=List[StorageResponse])
async def list_storage(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> List[StorageResponse]:
    """List all configured storage targets."""
    return [_to_response(t) for t in _get_targets(config_manager)]


@router.get("/storage/{storage_id}", response_model=StorageResponse)
async def get_storage(
    storage_id: int,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> StorageResponse:
    """Get a single storage target by ID."""
    target = next(
        (t for t in _get_targets(config_manager) if t.get("id") == storage_id),
        None,
    )
    if not target:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Storage {storage_id} not found"
        )
    return _to_response(target)


@router.post(
    "/storage", response_model=StorageResponse, status_code=status.HTTP_201_CREATED
)
async def create_storage(
    payload: StorageCreate,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> StorageResponse:
    """Create a new storage target (S3 or SMB)."""
    data = payload.model_dump(exclude_none=True)

    # Generate ID
    targets = _get_targets(config_manager)
    existing_ids = [t.get("id", 0) for t in targets]
    data["id"] = max(existing_ids) + 1 if existing_ids else 1

    # Persist
    if CONFIG_KEY not in config_manager.config:
        config_manager.config[CONFIG_KEY] = []
    config_manager.config[CONFIG_KEY].append(data)
    config_manager.save_config()

    return _to_response(data)


@router.put("/storage/{storage_id}", response_model=StorageResponse)
async def update_storage(
    storage_id: int,
    payload: StorageUpdate,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> StorageResponse:
    """Update an existing storage target."""
    targets = _get_targets(config_manager)
    idx = next(
        (i for i, t in enumerate(targets) if t.get("id") == storage_id),
        None,
    )
    if idx is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Storage {storage_id} not found"
        )

    updated = targets[idx].copy()
    updated.update(payload.model_dump(exclude_unset=True))
    config_manager.config[CONFIG_KEY][idx] = updated
    config_manager.save_config()

    return _to_response(updated)


@router.delete("/storage/{storage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storage(
    storage_id: int,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> None:
    """Delete a storage target."""
    targets = _get_targets(config_manager)
    if not any(t.get("id") == storage_id for t in targets):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Storage {storage_id} not found"
        )

    config_manager.config[CONFIG_KEY] = [
        t for t in targets if t.get("id") != storage_id
    ]
    config_manager.save_config()


@router.post("/storage/{storage_id}/test", response_model=StorageTestResult)
async def test_storage_connection(
    storage_id: int,
    db_manager: DBManager = Depends(get_db_manager),
) -> StorageTestResult:
    """Test connection to a storage target."""
    try:
        storage = db_manager.storage_manager.get_storage(storage_id)
        if not storage:
            raise ValueError(f"Storage {storage_id} not found")

        success = storage.test_connection()
        if success:
            return StorageTestResult(success=True, message="Connection successful")
        return StorageTestResult(success=False, message="Connection test failed")

    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except Exception as e:
        return StorageTestResult(
            success=False, message="Connection failed", error=str(e)
        )


# ---------------------------------------------------------------------------
# Legacy aliases — keep /s3-buckets/* working for backward compat
# ---------------------------------------------------------------------------


@router.get(
    "/s3-buckets", response_model=List[StorageResponse], include_in_schema=False
)
async def list_s3_buckets_compat(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> List[StorageResponse]:
    return await list_storage(config_manager)


@router.post(
    "/s3-buckets",
    response_model=StorageResponse,
    status_code=201,
    include_in_schema=False,
)
async def create_s3_bucket_compat(
    payload: StorageCreate,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> StorageResponse:
    return await create_storage(payload, config_manager)


@router.delete("/s3-buckets/{storage_id}", status_code=204, include_in_schema=False)
async def delete_s3_bucket_compat(
    storage_id: int,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> None:
    return await delete_storage(storage_id, config_manager)
