"""ProxyManager: writes Caddyfile, hot-reloads Caddy, restarts container as needed."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from proxy.caddyfile_gen import render_caddyfile
from proxy.config import ProxyConfig, ProxyConfigManager, ProxyMode

logger = logging.getLogger(__name__)

# Bind-mounted from host (see docker-compose.yml). Inside the backend container
# this path points at the same file caddy reads at /etc/caddy/Caddyfile.
CADDYFILE_PATH = Path(
    os.getenv("DBMANAGER_CADDYFILE", "/etc/dbmanager/caddy/Caddyfile")
)


class ProxyManager:
    def __init__(self, cfg_manager: Optional[ProxyConfigManager] = None) -> None:
        self.cfg_manager = cfg_manager or ProxyConfigManager()

    # ── Caddyfile writing ────────────────────────────────────────────────────

    def write_caddyfile(self, cfg: ProxyConfig) -> Path:
        content = render_caddyfile(cfg)
        CADDYFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CADDYFILE_PATH.with_suffix(".tmp")
        tmp.write_text(content)
        tmp.replace(CADDYFILE_PATH)
        logger.info("Wrote Caddyfile to %s (%d bytes)", CADDYFILE_PATH, len(content))
        return CADDYFILE_PATH

    # ── Caddy admin API ──────────────────────────────────────────────────────

    def _admin_url(self, cfg: ProxyConfig, path: str = "") -> str:
        return cfg.admin_url.rstrip("/") + path

    def hot_reload(self, cfg: ProxyConfig, timeout: float = 10.0) -> bool:
        """POST the rendered Caddyfile to /load on Caddy admin API.
        Returns True if Caddy accepted the new config."""
        try:
            content = render_caddyfile(cfg)
            r = requests.post(
                self._admin_url(cfg, "/load"),
                data=content,
                headers={"Content-Type": "text/caddyfile"},
                timeout=timeout,
            )
            if r.status_code >= 300:
                logger.error("Caddy reload failed: %s %s", r.status_code, r.text[:500])
                return False
            return True
        except requests.RequestException as e:
            logger.error("Caddy reload request error: %s", e)
            return False

    # ── Container restart (docker socket) ────────────────────────────────────

    def restart_container(self, cfg: ProxyConfig) -> bool:
        try:
            import docker  # type: ignore
        except ImportError:
            logger.error("docker SDK not installed")
            return False
        try:
            client = docker.from_env()
            container = client.containers.get(cfg.caddy_container)
            container.restart(timeout=10)
            return True
        except Exception as e:
            logger.error("docker restart failed: %s", e)
            return False

    # ── Apply: persist + write file + reload (or restart on failure) ─────────

    def apply(
        self, cfg: ProxyConfig, allow_restart_fallback: bool = True
    ) -> Dict[str, Any]:
        self.cfg_manager.save(cfg)
        path = self.write_caddyfile(cfg)
        reloaded = self.hot_reload(cfg)
        restarted = False
        if not reloaded and allow_restart_fallback:
            restarted = self.restart_container(cfg)
        return {
            "caddyfile": str(path),
            "reloaded": reloaded,
            "restarted": restarted,
            "ok": reloaded or restarted,
        }

    # ── Status / cert info ───────────────────────────────────────────────────

    def status(self, cfg: ProxyConfig, timeout: float = 5.0) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "configured": cfg.is_configured(),
            "mode": cfg.mode.value,
            "domain": cfg.domain,
            "admin_reachable": False,
            "running_config": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            r = requests.get(self._admin_url(cfg, "/config/"), timeout=timeout)
            if r.ok:
                result["admin_reachable"] = True
                try:
                    result["running_config"] = r.json()
                except ValueError:
                    result["running_config"] = None
        except requests.RequestException as e:
            result["error"] = str(e)
        return result
