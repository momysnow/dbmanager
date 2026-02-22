"""Database query execution endpoints"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager

router = APIRouter()


@router.post("/databases/{database_id}/query", response_model=Dict[str, Any])
async def execute_query(
    database_id: int,
    query_request: Dict[str, Any],
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
    """
    Execute a SQL query on a database and return results.

    Args:
        database_id: Database ID
        query_request: {"query": "SELECT ...", "limit": 100}

    Returns:
        {
            "columns": ["col1", "col2", ...],
            "rows": [[val1, val2, ...], ...],
            "row_count": 10,
            "execution_time_ms": 50
        }
    """
    # Validate database exists
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )

    query = query_request.get("query", "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query is required",
        )
    limit = query_request.get("limit", 1000)
    if limit > 10000:
        limit = 10000  # Cap at 10000 rows

    try:
        result = db_manager.execute_query(database_id, query, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}",
        )


@router.get("/databases/{database_id}/tables", response_model=List[Dict[str, Any]])
async def list_tables(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> List[Dict[str, Any]]:
    """List all tables in a database"""
    # Validate database exists
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )

    try:
        tables = db_manager.list_tables(database_id)
        return tables
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {str(e)}",
        )


@router.get("/databases/{database_id}/schema", response_model=Dict[str, Any])
async def get_database_schema(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
    """Get full database schema mapping (tables and foreign keys) for visualization"""
    # Validate database exists
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )

    try:
        schema = db_manager.get_database_schema(database_id)
        return schema
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database schema: {str(e)}",
        )


@router.get(
    "/databases/{database_id}/tables/{table_name}/schema", response_model=Dict[str, Any]
)
async def get_table_schema(
    database_id: int,
    table_name: str,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
    """Get schema information for a specific table"""
    # Validate database exists
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )

    try:
        schema = db_manager.get_table_schema(database_id, table_name)
        return schema
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table schema: {str(e)}",
        )
