from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_users(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await session.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    from sqlalchemy import func
    result = await session.execute(select(func.count(User.id)))
    return result.scalar_one()


async def create_user(
    session: AsyncSession,
    username: str,
    password_hash: str,
    role: str = "viewer",
) -> User:
    user = User(username=username, password_hash=password_hash, role=role)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def update_last_login(session: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
