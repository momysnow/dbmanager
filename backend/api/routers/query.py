"""Database query execution endpoints"""

import asyncio
import logging
from functools import partial
from typing import Any, Callable, Dict, List, Tuple, TypeVar

import sqlparse
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_config_manager, get_db_manager
from api.deps import get_current_user, require_role
from config import ConfigManager
from core.manager import DBManager
from db.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

_all_roles = [Depends(require_role("admin", "operator", "viewer"))]

# Tokens that represent writes / DDL / side-effect-producing ops.
_WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "REPLACE", "MERGE", "CALL", "EXEC", "EXECUTE", "GRANT", "REVOKE",
    "COPY", "DO", "LOAD", "VACUUM", "ANALYZE", "REINDEX", "CLUSTER",
    "LOCK", "RENAME", "COMMENT", "SET", "RESET", "BEGIN", "COMMIT",
    "ROLLBACK", "SAVEPOINT", "ATTACH", "DETACH", "PRAGMA", "HANDLER",
    "INSTALL", "UNINSTALL",
}

# Explain variants that can still execute the underlying plan.
_UNSAFE_EXPLAIN = {"EXPLAIN"}


def _classify(sql: str) -> Tuple[bool, int]:
    """Return (contains_write, statement_count).

    A statement is a "write" if:
      - its first non-comment keyword is a write/DDL keyword, OR
      - it is EXPLAIN ANALYZE <write stmt>, OR
      - it is a CTE (WITH ...) whose inner definitions contain DML writes.
    """
    try:
        parsed = sqlparse.parse(sql)
    except Exception:
        # If sqlparse fails, treat defensively as write.
        return True, 1

    stmts = [s for s in parsed if s.tokens and str(s).strip()]
    count = len(stmts)
    for stmt in stmts:
        tokens = [t for t in stmt.flatten() if not t.is_whitespace and t.ttype not in (
            sqlparse.tokens.Comment,
            sqlparse.tokens.Comment.Single,
            sqlparse.tokens.Comment.Multiline,
        )]
        if not tokens:
            continue
        upper_words = [t.value.upper() for t in tokens if t.ttype in (
            sqlparse.tokens.Keyword,
            sqlparse.tokens.Keyword.DDL,
            sqlparse.tokens.Keyword.DML,
            sqlparse.tokens.Keyword.CTE,
        ) or t.ttype is None and t.value.upper() in _WRITE_KEYWORDS]

        first = upper_words[0] if upper_words else ""

        if first in _WRITE_KEYWORDS:
            return True, count

        # EXPLAIN ANALYZE <write> actually executes the plan.
        # Strip EXPLAIN-only modifiers before checking for writes.
        if first in _UNSAFE_EXPLAIN:
            _EXPLAIN_MODS = {"ANALYZE", "VERBOSE", "COSTS", "SETTINGS", "BUFFERS",
                             "WAL", "TIMING", "SUMMARY", "FORMAT"}
            rest = set(upper_words[1:]) - _EXPLAIN_MODS
            if rest & _WRITE_KEYWORDS:
                return True, count

        # WITH ... (CTE): scan inner keywords for writes.
        if first == "WITH":
            if any(w in _WRITE_KEYWORDS for w in upper_words[1:]):
                return True, count

    return False, count


_T = TypeVar("_T")


async def _run_blocking(fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Run a blocking DB call in the default executor so the event loop stays free."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


def _assert_read_only(sql: str) -> None:
    contains_write, count = _classify(sql)
    if count > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot execute multi-statement queries",
        )
    if contains_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot execute write queries",
        )


@router.post("/databases/{database_id}/query", response_model=Dict[str, Any])
async def execute_query(
    database_id: int,
    query_request: Dict[str, Any],
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )

    query = query_request.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is required")

    if current_user.role == "viewer":
        _assert_read_only(query)

    limit = min(query_request.get("limit", 1000), 10000)

    try:
        result = await _run_blocking(
            db_manager.execute_query, database_id, query, limit=limit
        )
        return result
    except Exception as e:
        logger.exception("Query execution failed for db=%s user=%s", database_id, current_user.username)
        # Admins get the raw error to debug; others get a generic message.
        detail = f"Query execution failed: {str(e)}" if current_user.role == "admin" else "Query execution failed"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.get("/databases/{database_id}/tables", response_model=List[Dict[str, Any]], dependencies=_all_roles)
async def list_tables(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> List[Dict[str, Any]]:
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )
    try:
        return await _run_blocking(db_manager.list_tables, database_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {str(e)}",
        )


@router.get("/databases/{database_id}/schema", response_model=Dict[str, Any], dependencies=_all_roles)
async def get_database_schema(
    database_id: int,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )
    try:
        return await _run_blocking(db_manager.get_database_schema, database_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database schema: {str(e)}",
        )


@router.get(
    "/databases/{database_id}/tables/{table_name}/schema",
    response_model=Dict[str, Any],
    dependencies=_all_roles,
)
async def get_table_schema(
    database_id: int,
    table_name: str,
    db_manager: DBManager = Depends(get_db_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Dict[str, Any]:
    db_config = config_manager.get_database(database_id)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database with ID {database_id} not found",
        )
    try:
        return await _run_blocking(
            db_manager.get_table_schema, database_id, table_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table schema: {str(e)}",
        )
