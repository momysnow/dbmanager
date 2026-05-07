"""Config export endpoints — JSON, Docker Compose, .env"""

import copy
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from api.dependencies import get_config_manager
from config import ConfigManager, SENSITIVE_FIELDS

router = APIRouter()

_MASKED = "***MASKED***"


def _mask_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: _MASKED if k in SENSITIVE_FIELDS and isinstance(v, str) and v else _mask_sensitive(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive(i) for i in data]
    return data


@router.get("/export/config")
async def export_config(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> JSONResponse:
    """Export full config with sensitive fields masked."""
    safe = _mask_sensitive(copy.deepcopy(config_manager.config))
    return JSONResponse(content=safe, headers={"Content-Disposition": "attachment; filename=dbmanager-config.json"})


_PROVIDER_DOCKER: Dict[str, str] = {
    "postgres": """\
  {name}_db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: "{user}"
      POSTGRES_PASSWORD: "${{DB_{NAME}_PASSWORD}}"
      POSTGRES_DB: "{database}"
    ports:
      - "{port}:{port}"
""",
    "mysql": """\
  {name}_db:
    image: mysql:8.0
    environment:
      MYSQL_USER: "{user}"
      MYSQL_PASSWORD: "${{DB_{NAME}_PASSWORD}}"
      MYSQL_DATABASE: "{database}"
      MYSQL_ROOT_PASSWORD: "${{DB_{NAME}_ROOT_PASSWORD}}"
    ports:
      - "{port}:{port}"
""",
    "mariadb": """\
  {name}_db:
    image: mariadb:10
    environment:
      MARIADB_USER: "{user}"
      MARIADB_PASSWORD: "${{DB_{NAME}_PASSWORD}}"
      MARIADB_DATABASE: "{database}"
      MARIADB_ROOT_PASSWORD: "${{DB_{NAME}_ROOT_PASSWORD}}"
    ports:
      - "{port}:{port}"
""",
}


@router.get("/export/docker-compose")
async def export_docker_compose(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> PlainTextResponse:
    """Generate a docker-compose.yml for current DB configuration."""
    lines = ["version: '3.8'", "services:"]
    env_vars = ["# DBManager — generated docker-compose env vars", ""]

    for db in config_manager.get_databases():
        provider = db.get("provider", "")
        params = db.get("params", {})
        name_raw = str(db.get("name", f"db{db['id']}")).lower().replace(" ", "_")
        NAME = name_raw.upper()
        template = _PROVIDER_DOCKER.get(provider)
        if template:
            block = template.format(
                name=name_raw,
                NAME=NAME,
                user=params.get("user", ""),
                database=params.get("database", ""),
                port=params.get("port", "5432"),
            )
            lines.append(block)
            env_vars.append(f"DB_{NAME}_PASSWORD=change_me")
            if provider in ("mysql", "mariadb"):
                env_vars.append(f"DB_{NAME}_ROOT_PASSWORD=change_me")

    lines += [
        "  dbmanager:",
        "    image: dbmanager:latest",
        "    ports:",
        "      - '8000:8000'",
        "    environment:",
        "      - DBMANAGER_ADMIN_USER=${DBMANAGER_ADMIN_USER:-admin}",
        "      - DBMANAGER_ADMIN_PASSWORD=${DBMANAGER_ADMIN_PASSWORD:-changeme}",
    ]

    compose_content = "\n".join(lines)
    env_content = "\n".join(env_vars)

    full = f"{compose_content}\n\n# --- .env template ---\n# {env_content.replace(chr(10), chr(10)+'# ')}"
    return PlainTextResponse(
        content=full,
        headers={"Content-Disposition": "attachment; filename=docker-compose.yml"},
    )


@router.get("/export/env")
async def export_env(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> PlainTextResponse:
    """Export .env file with current environment variable configuration."""
    lines = ["# DBManager — environment configuration export", ""]

    # App settings
    lines += [
        "DBMANAGER_ADMIN_USER=admin",
        "DBMANAGER_ADMIN_PASSWORD=changeme",
        f"DBMANAGER_DATA_DIR={os.getenv('DBMANAGER_DATA_DIR', '~/.dbmanager')}",
        "",
    ]

    # Per-DB env vars (passwords masked)
    for db in config_manager.get_databases():
        name = str(db.get("name", f"db{db['id']}")).upper().replace(" ", "_")
        params = db.get("params", {})
        lines += [
            f"# {db.get('name')} ({db.get('provider')})",
            f"DB_{name}_HOST={params.get('host', '')}",
            f"DB_{name}_PORT={params.get('port', '')}",
            f"DB_{name}_USER={params.get('user', '')}",
            f"DB_{name}_PASSWORD=***CHANGE_ME***",
            f"DB_{name}_DATABASE={params.get('database', '')}",
            "",
        ]

    # Notification settings
    notif = config_manager.get_notification_settings()
    if notif.get("slack", {}).get("enabled"):
        lines.append("SLACK_WEBHOOK_URL=***CHANGE_ME***")
    if notif.get("discord", {}).get("enabled"):
        lines.append("DISCORD_WEBHOOK_URL=***CHANGE_ME***")
    if notif.get("teams", {}).get("enabled"):
        lines.append("TEAMS_WEBHOOK_URL=***CHANGE_ME***")

    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": "attachment; filename=.env"},
    )
