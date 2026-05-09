"""Reverse proxy management endpoints (admin only)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import require_role
from proxy.config import ProxyConfig, ProxyConfigManager
from proxy.manager import ProxyManager

router = APIRouter()

_admin = [Depends(require_role("admin"))]


def _get_manager() -> ProxyManager:
    return ProxyManager(ProxyConfigManager())


def _mask(cfg: ProxyConfig) -> Dict[str, Any]:
    """Mask credential references — credentials_env names are safe to show
    but we never have raw secrets in the config anyway. Included for symmetry
    with future expansions."""
    return cfg.model_dump(mode="json")


@router.get("/proxy/config", dependencies=_admin)
async def get_proxy_config() -> Dict[str, Any]:
    cfg = _get_manager().cfg_manager.load()
    return _mask(cfg)


@router.put("/proxy/config", dependencies=_admin)
async def put_proxy_config(payload: ProxyConfig) -> Dict[str, Any]:
    mgr = _get_manager()
    if (
        payload.enabled
        and payload.mode.value != "disabled"
        and not payload.is_configured()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proxy config incomplete (check domain, ACME method, email, provider, manual cert paths).",
        )
    result = mgr.apply(payload)
    return {"config": _mask(payload), **result}


@router.get("/proxy/status", dependencies=_admin)
async def get_proxy_status() -> Dict[str, Any]:
    mgr = _get_manager()
    cfg = mgr.cfg_manager.load()
    return mgr.status(cfg)


@router.post("/proxy/reload", dependencies=_admin)
async def post_proxy_reload() -> Dict[str, Any]:
    mgr = _get_manager()
    cfg = mgr.cfg_manager.load()
    ok = mgr.hot_reload(cfg)
    if not ok:
        raise HTTPException(status_code=502, detail="Caddy admin API rejected reload")
    return {"reloaded": True}


@router.post("/proxy/restart", dependencies=_admin)
async def post_proxy_restart() -> Dict[str, Any]:
    mgr = _get_manager()
    cfg = mgr.cfg_manager.load()
    ok = mgr.restart_container(cfg)
    if not ok:
        raise HTTPException(status_code=502, detail="docker restart failed")
    return {"restarted": True}
