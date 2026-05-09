"""ProxyManager: writes Caddyfile, hot-reloads Caddy, restarts container as needed."""

from __future__ import annotations

import http.client
import json as _json
import logging
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from proxy.caddyfile_gen import render_caddyfile
from proxy.config import ProxyConfig, ProxyConfigManager, ProxyMode

logger = logging.getLogger(__name__)


class _UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over a unix-domain socket. Used for Caddy admin API.

    Why: Caddy admin TCP is reachable from any sibling container on the same
    Docker bridge (the `origins` directive only filters Host headers). A
    UDS-only admin binding paired with a volume mounted into the backend alone
    makes admin reachable strictly to this process.
    """

    def __init__(self, socket_path: str, timeout: float = 10.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:  # type: ignore[override]
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


def _admin_request(
    admin_url: str,
    method: str,
    path: str,
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Tuple[int, bytes]:
    """Issue an HTTP request to the Caddy admin API over its unix socket.

    Returns (status_code, body_bytes). Raises OSError / http.client errors
    on transport failures — callers translate these to user-facing errors.
    """
    if not admin_url.startswith("unix://"):
        raise ValueError(
            f"admin_url must use scheme unix://, got {admin_url!r}"
        )
    sock_path = admin_url[len("unix://"):]
    conn = _UnixHTTPConnection(sock_path, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()

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

    def hot_reload(self, cfg: ProxyConfig, timeout: float = 10.0) -> bool:
        """POST the rendered Caddyfile to /load on Caddy admin API.
        Returns True if Caddy accepted the new config."""
        try:
            content = render_caddyfile(cfg)
            status_code, body = _admin_request(
                cfg.admin_url,
                "POST",
                "/load",
                body=content.encode("utf-8"),
                headers={"Content-Type": "text/caddyfile"},
                timeout=timeout,
            )
            if status_code >= 300:
                logger.error(
                    "Caddy reload failed: %s %s",
                    status_code,
                    body[:500].decode("utf-8", "replace"),
                )
                return False
            return True
        except (OSError, http.client.HTTPException) as e:
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
            status_code, body = _admin_request(
                cfg.admin_url, "GET", "/config/", timeout=timeout
            )
            if 200 <= status_code < 300:
                result["admin_reachable"] = True
                try:
                    result["running_config"] = _json.loads(body)
                except ValueError:
                    result["running_config"] = None
        except (OSError, http.client.HTTPException) as e:
            result["error"] = str(e)
        return result
