"""User management endpoints (admin only)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import auth_manager, get_current_user, require_role
from core.audit import record_audit
from db.engine import get_db
from db.models.user import User
from db.repositories.users_repo import (
    count_users,
    create_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
)

router = APIRouter()

_admin_only = [Depends(require_role("admin"))]

_VALID_ROLES = {"admin", "operator", "viewer"}


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    role: str = "viewer"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]


async def _count_active_admins(db: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(
        and_(User.role == "admin", User.is_active.is_(True))
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


def _check_password_strength(username: str, password: str) -> None:
    if username and username.lower() in password.lower():
        raise HTTPException(status_code=400, detail="Password must not contain username")


@router.get("/users", response_model=UserListResponse, dependencies=_admin_only)
async def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    users = await list_users(db, skip=skip, limit=limit)
    total = await count_users(db)
    return UserListResponse(total=total, users=[UserResponse.model_validate(u) for u in users])


@router.post("/users", response_model=UserResponse, status_code=201, dependencies=_admin_only)
async def create_new_user(
    body: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    _check_password_strength(body.username, body.password)
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    hashed = auth_manager.get_password_hash(body.password)
    user = await create_user(db, username=body.username, password_hash=hashed, role=body.role)
    await db.commit()
    await record_audit(
        action="user.created",
        status="success",
        user=current_user,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
        details={"username": user.username, "role": user.role},
    )
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=_admin_only)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Self-lockout guard: admin can't demote or deactivate themselves.
    if user.id == current_user.id:
        if body.role is not None and body.role != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Last-admin invariant: demoting or deactivating an admin requires another admin to exist.
    would_demote = user.role == "admin" and body.role is not None and body.role != "admin"
    would_deactivate = user.role == "admin" and user.is_active and body.is_active is False
    if would_demote or would_deactivate:
        remaining = await _count_active_admins(db)
        if remaining <= 1:
            raise HTTPException(status_code=400, detail="At least one active admin must remain")

    if body.role is not None:
        if body.role not in _VALID_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = body.role
    if body.is_active is not None:
        # If deactivating, invalidate outstanding tokens.
        if user.is_active and not body.is_active:
            user.token_version = (user.token_version or 0) + 1
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    await record_audit(
        action="user.updated",
        status="success",
        user=current_user,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
        details={"role": user.role, "is_active": user.is_active},
    )
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", dependencies=_admin_only)
async def reset_user_password(
    user_id: int,
    body: PasswordReset,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _check_password_strength(user.username, body.new_password)
    user.password_hash = auth_manager.get_password_hash(body.new_password)
    # Invalidate any existing JWTs for this user.
    user.token_version = (user.token_version or 0) + 1
    # Force the target user to change password on next login unless they're resetting their own.
    if user.id != current_user.id:
        user.must_change_password = True
    await db.commit()
    await record_audit(
        action="user.password_reset",
        status="success",
        user=current_user,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    return {"detail": "Password updated"}


@router.delete("/users/{user_id}", dependencies=_admin_only)
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Last-admin invariant.
    if user.role == "admin" and user.is_active:
        remaining = await _count_active_admins(db)
        if remaining <= 1:
            raise HTTPException(status_code=400, detail="At least one active admin must remain")
    username = user.username
    await db.delete(user)
    await db.commit()
    await record_audit(
        action="user.deleted",
        status="success",
        user=current_user,
        resource_type="user",
        resource_id=str(user_id),
        request=request,
        details={"username": username},
    )
    return {"detail": "User deleted"}
