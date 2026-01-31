"""Database management endpoints"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from api.models.database import (
    DatabaseCreate,
    DatabaseUpdate,
    DatabaseResponse,
    DatabaseTestResult
)
from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager

router = APIRouter()


@router.get("/databases", response_model=List[DatabaseResponse])
async def list_databases(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """List all configured databases"""
    databases = config_manager.get_databases()
    
    # Convert to response model (exclude password)
    response = []
    for db in databases:
        db_copy = db.copy()
        db_copy.pop('password', None)  # Remove password from response
        response.append(DatabaseResponse(**db_copy))
    
    return response


@router.get("/databases/{database_id}", response_model=DatabaseResponse)
async def get_database(
    database_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Get a specific database by ID"""
    db = config_manager.get_database(database_id)
    
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Remove password from response
    db_copy = db.copy()
    db_copy.pop('password', None)
    
    return DatabaseResponse(**db_copy)


@router.post("/databases", response_model=DatabaseResponse, status_code=status.HTTP_201_CREATED)
async def create_database(
    database: DatabaseCreate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Create a new database configuration"""
    
    # Validate provider
    valid_providers = ['postgres', 'mysql', 'sqlserver']
    if database.provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        )
    
    # Validate S3 configuration
    if database.s3_enabled and not database.s3_bucket_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="s3_bucket_id is required when s3_enabled is true"
        )
    
    # Convert to dict and add to config
    db_dict = database.model_dump()
    db_id = config_manager.add_database(db_dict)
    
    # Get the created database
    created_db = config_manager.get_database(db_id)
    created_db_copy = created_db.copy()
    created_db_copy.pop('password', None)
    
    return DatabaseResponse(**created_db_copy)


@router.put("/databases/{database_id}", response_model=DatabaseResponse)
async def update_database(
    database_id: int,
    database: DatabaseUpdate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Update an existing database configuration"""
    
    # Check if database exists
    existing_db = config_manager.get_database(database_id)
    if not existing_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Validate provider if being updated
    if database.provider is not None:
        valid_providers = ['postgres', 'mysql', 'sqlserver']
        if database.provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
    
    # Merge updates with existing config
    updated_db = existing_db.copy()
    update_data = database.model_dump(exclude_unset=True)
    updated_db.update(update_data)
    
    # Validate S3 configuration after merge
    if updated_db.get('s3_enabled') and not updated_db.get('s3_bucket_id'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="s3_bucket_id is required when s3_enabled is true"
        )
    
    # Update in config
    success = config_manager.update_database(database_id, updated_db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database"
        )
    
    # Get updated database
    updated = config_manager.get_database(database_id)
    updated_copy = updated.copy()
    updated_copy.pop('password', None)
    
    return DatabaseResponse(**updated_copy)


@router.delete("/databases/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database(
    database_id: int,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Delete a database configuration"""
    
    # Check if database exists
    db = config_manager.get_database(database_id)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found"
        )
    
    # Remove database
    config_manager.remove_database(database_id)
    
    return None


@router.post("/databases/{database_id}/test", response_model=DatabaseTestResult)
async def test_database_connection(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager)
):
    """Test database connection"""
    
    try:
        # Get provider instance
        provider = db_manager.get_provider_instance(database_id)
        
        # Test connection
        result = provider.test_connection()
        
        if result:
            return DatabaseTestResult(
                success=True,
                message="Connection successful"
            )
        else:
            return DatabaseTestResult(
                success=False,
                message="Connection failed",
                error="Connection test returned False"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        return DatabaseTestResult(
            success=False,
            message="Connection failed",
            error=str(e)
        )
