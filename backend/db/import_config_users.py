"""Migrate users from config.json to DB on first startup."""

import json
import logging
import shutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.users_repo import count_users, create_user

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__import__("os").getenv("DBMANAGER_DATA_DIR", str(Path.home() / ".dbmanager")))
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_BACKUP = CONFIG_DIR / "config.json.pre-rbac.bak"


async def migrate_users_from_config(session: AsyncSession) -> int:
    """Import users from config.json if DB is empty. Returns count imported."""
    if not CONFIG_FILE.exists():
        return 0

    existing = await count_users(session)
    if existing > 0:
        return 0

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    users = config.get("users", [])
    if not users:
        return 0

    # Back up config before stripping users
    if not CONFIG_BACKUP.exists():
        shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)

    imported = 0
    for u in users:
        username = u.get("username")
        password_hash = u.get("password_hash")
        role = u.get("role", "admin")
        if role not in ("admin", "operator", "viewer"):
            logger.warning("Unknown role %r for user %r — defaulting to viewer", role, username)
            role = "viewer"
        if username and password_hash:
            try:
                await create_user(session, username=username, password_hash=password_hash, role=role)
                imported += 1
            except Exception:
                logger.warning("Failed to import user %s", username)

    # Remove users key from config.json
    if "users" in config:
        del config["users"]
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    logger.info("Migrated %d user(s) from config.json to DB", imported)
    return imported
