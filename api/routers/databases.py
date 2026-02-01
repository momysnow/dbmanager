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
    
    # Validation/filtering happens in Pydantic model validator (remove_password)
    return databases


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
    
    return db


@router.post("/databases", response_model=DatabaseResponse, status_code=status.HTTP_201_CREATED)
async def create_database(
    database: DatabaseCreate,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Create a new database configuration"""
    
    # Validate provider
    valid_providers = ['postgres', 'mysql', 'sqlserver', 'mariadb', 'mongodb']
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
    # model_dump() handles the nested params structure correctly now
    db_dict = database.model_dump()
    db_id = config_manager.add_database(db_dict)
    
    # Get the created database
    created_db = config_manager.get_database(db_id)
    
    return created_db


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
        valid_providers = ['postgres', 'mysql', 'sqlserver', 'mariadb', 'mongodb']
        if database.provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
    
    # Merge updates with existing config
    updated_db = existing_db.copy()
    
    # For nested params, we need to be careful not to overwrite the whole dict if we want partial updates,
    # but DatabaseUpdate.params is the connection params. Usually user sends all connection params.
    # If partial update of params is needed, we should merge.
    update_data = database.model_dump(exclude_unset=True)
    
    if "params" in update_data and "params" in updated_db:
        # Check for nested merge needs? 
        # For simplicity, if params are provided, we update/overwrite with what's provided, 
        # but preserving existing keys if not in update logic? 
        # Actually, best practice often strictly separate.
        # But password handling: if password is NOT in update_data["params"], we should keep old one?
        # DatabaseUpdate params.password is Optional.
        # If it's None, it might be excluded by exclude_unset=True if it was not set in request.
        
        # Let's check if password is being cleared or just not sent.
        # If the user sends password field in UI left empty, we treat as "no change".
        
        # Merge params manually to ensure we don't lose existing fields like 'trust_certificate' if not in model?
        # Our model allows extra fields.
        
        new_params = update_data["params"]
        old_params = updated_db["params"]
        
        # Merge
        merged_params = old_params.copy()
        merged_params.update(new_params)
        
        update_data["params"] = merged_params
        
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
    
    return updated


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
