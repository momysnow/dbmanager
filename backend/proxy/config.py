"""Proxy configuration: schema, persistence, env-var overlay."""

from __future__ import annotations

import json
import os
import re
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from config import CONFIG_DIR

PROXY_CONFIG_FILE = CONFIG_DIR / "proxy.json"

# All values below feed into a Caddyfile via plain string interpolation
# (proxy/caddyfile_gen.py). Anything that survives validation must be
# unable to break out of a directive — no whitespace, no `{`/`}`, no
# semicolons or quotes, no newlines. The regexes below are intentionally
# strict; relax only after auditing the generator together.
_DOMAIN_RE = re.compile(
    r"^(localhost|"
    r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?"
    r"(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*)$"
)
_UPSTREAM_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,253}[a-z0-9])?:[0-9]{1,5}$")
# Caddy admin is reached over a unix-domain socket (preferred) shared via a
# volume mount with the backend container only. TCP is no longer accepted;
# any sibling container on the same Docker bridge would otherwise reach :2019.
_ADMIN_SOCKET_PATH_RE = re.compile(r"^/(?:[a-zA-Z0-9._-]+/)+[a-zA-Z0-9._-]+$")


class ProxyMode(str, Enum):
    DISABLED = "disabled"
    HTTP = "http"
    HTTPS = "https"


class AcmeMethod(str, Enum):
    NONE = "none"  # used with mode=http
    DNS = "dns"  # DNS-01 via plugin
    HTTP01 = "http-01"  # HTTP-01 challenge
    MANUAL = "manual"  # user-provided cert/key
    SELFSIGNED = "selfsigned"  # caddy `tls internal`


class DnsProvider(str, Enum):
    CLOUDFLARE = "cloudflare"
    ROUTE53 = "route53"
    DIGITALOCEAN = "digitalocean"
    GANDI = "gandi"
    DUCKDNS = "duckdns"


# Map provider -> caddy `dns` directive name + env var the user must set.
# The wizard validates the env var is present at config-time.
DNS_PROVIDER_ENV: Dict[DnsProvider, str] = {
    DnsProvider.CLOUDFLARE: "CF_API_TOKEN",
    DnsProvider.ROUTE53: "AWS_ACCESS_KEY_ID",
    DnsProvider.DIGITALOCEAN: "DO_AUTH_TOKEN",
    DnsProvider.GANDI: "GANDI_API_TOKEN",
    DnsProvider.DUCKDNS: "DUCKDNS_API_TOKEN",
}


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9/_.-]+$")


class AcmeConfig(BaseModel):
    method: AcmeMethod = AcmeMethod.NONE
    email: str = ""
    dns_provider: Optional[DnsProvider] = None
    # Reference only, never the secret itself.
    credentials_env: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip()
        if v and not _EMAIL_RE.match(v):
            raise ValueError(f"Invalid ACME email {v!r}.")
        return v

    @field_validator("credentials_env")
    @classmethod
    def _validate_credentials_env(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not re.match(r"^[A-Z][A-Z0-9_]{0,63}$", v):
            raise ValueError(f"Invalid env var name {v!r}.")
        return v


class ManualCertConfig(BaseModel):
    cert_path: str = ""
    key_path: str = ""

    @field_validator("cert_path", "key_path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        v = v.strip()
        # Empty allowed for unconfigured / non-manual modes. Otherwise the
        # path is interpolated into a `tls <cert> <key>` directive — must be
        # an absolute POSIX path without whitespace or shell metacharacters.
        if v and not _SAFE_PATH_RE.match(v):
            raise ValueError(
                f"Invalid certificate path {v!r}: must be absolute and free "
                f"of whitespace, '{{', '}}', and shell metacharacters."
            )
        return v


class ProxyRoutes(BaseModel):
    frontend_upstream: str = "frontend:5173"
    backend_upstream: str = "backend:8000"
    backend_path_prefix: str = "/api"

    @field_validator("frontend_upstream", "backend_upstream")
    @classmethod
    def _validate_upstream(cls, v: str) -> str:
        v = v.strip()
        if not _UPSTREAM_RE.match(v):
            raise ValueError(
                f"Invalid upstream {v!r}: expected `host:port` with a DNS-safe "
                f"host and a numeric port."
            )
        port = int(v.rsplit(":", 1)[1])
        if not 1 <= port <= 65535:
            raise ValueError(f"Upstream port {port} out of range (1-65535).")
        return v

    @field_validator("backend_path_prefix")
    @classmethod
    def _validate_path_prefix(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("/"):
            raise ValueError("backend_path_prefix must start with '/'.")
        if not re.match(r"^/[A-Za-z0-9/_-]*$", v):
            raise ValueError("backend_path_prefix contains illegal characters.")
        return v


class ProxyConfig(BaseModel):
    enabled: bool = True
    mode: ProxyMode = ProxyMode.DISABLED
    domain: str = ""
    acme: AcmeConfig = Field(default_factory=AcmeConfig)
    manual_cert: ManualCertConfig = Field(default_factory=ManualCertConfig)
    routes: ProxyRoutes = Field(default_factory=ProxyRoutes)
    admin_url: str = "unix:///run/caddy-admin/admin.sock"
    caddy_container: str = "dbmanager-caddy"

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, v: str) -> str:
        v = v.strip().lower()
        # Empty is permitted because a disabled / partially-configured proxy
        # carries an empty domain. is_configured() rejects that combination
        # downstream. A non-empty value must be a strict FQDN — anything else
        # could break out of the Caddyfile site block on render.
        if v and not _DOMAIN_RE.match(v):
            raise ValueError(
                f"Invalid domain {v!r}: expected an FQDN like 'db.example.com' "
                f"or 'localhost'. Whitespace, '{{', '}}', ';', and newlines "
                f"are rejected."
            )
        return v

    @field_validator("admin_url")
    @classmethod
    def _validate_admin_url(cls, v: str) -> str:
        # The backend POSTs the rendered Caddyfile to admin_url at runtime
        # (proxy/manager.py). Only `unix://` is accepted: a TCP admin endpoint
        # is reachable by any sibling container on the Docker bridge (the
        # `origins` directive only filters HTTP Host headers, not source IPs).
        v = v.strip()
        if not v.startswith("unix://"):
            raise ValueError(
                "admin_url must use scheme 'unix://' "
                "(e.g. unix:///run/caddy-admin/admin.sock)."
            )
        path = v[len("unix://"):]
        if not _ADMIN_SOCKET_PATH_RE.match(path):
            raise ValueError(
                f"Invalid unix socket path {path!r}: must be an absolute path "
                f"using only [A-Za-z0-9._-] segments."
            )
        return v

    @field_validator("caddy_container")
    @classmethod
    def _validate_container_name(cls, v: str) -> str:
        v = v.strip()
        # Docker container name rules: [a-zA-Z0-9][a-zA-Z0-9_.-]+
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,127}$", v):
            raise ValueError(f"Invalid container name {v!r}.")
        return v

    def is_configured(self) -> bool:
        if not self.enabled or self.mode == ProxyMode.DISABLED:
            return False
        if not self.domain:
            return False
        if self.mode == ProxyMode.HTTPS:
            if self.acme.method == AcmeMethod.MANUAL:
                return bool(self.manual_cert.cert_path and self.manual_cert.key_path)
            if self.acme.method == AcmeMethod.SELFSIGNED:
                return True
            if self.acme.method in (AcmeMethod.DNS, AcmeMethod.HTTP01):
                if not self.acme.email:
                    return False
                if self.acme.method == AcmeMethod.DNS:
                    return self.acme.dns_provider is not None
                return True
            return False
        return True


def _bool_env(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    return raw.lower() in ("1", "true", "yes", "on")


def proxy_config_from_env() -> Optional[ProxyConfig]:
    """Build a ProxyConfig from env vars. Returns None if not enough info."""
    enabled = _bool_env("DBMANAGER_PROXY_ENABLED")
    if enabled is False:
        cfg = ProxyConfig(enabled=False, mode=ProxyMode.DISABLED)
        return cfg

    mode_raw = os.getenv("DBMANAGER_PROXY_MODE", "").strip().lower()
    domain = os.getenv("DBMANAGER_PROXY_DOMAIN", "").strip()
    if not mode_raw or not domain:
        return None
    if mode_raw not in (m.value for m in ProxyMode):
        return None

    mode = ProxyMode(mode_raw)

    acme = AcmeConfig()
    if mode == ProxyMode.HTTPS:
        method_raw = os.getenv("DBMANAGER_PROXY_ACME_METHOD", "").strip().lower()
        if method_raw not in (m.value for m in AcmeMethod):
            return None
        acme.method = AcmeMethod(method_raw)
        acme.email = os.getenv("DBMANAGER_PROXY_ACME_EMAIL", "").strip()
        if acme.method == AcmeMethod.DNS:
            prov = os.getenv("DBMANAGER_PROXY_DNS_PROVIDER", "").strip().lower()
            if prov not in (p.value for p in DnsProvider):
                return None
            acme.dns_provider = DnsProvider(prov)
            acme.credentials_env = DNS_PROVIDER_ENV[acme.dns_provider]

    manual = ManualCertConfig(
        cert_path=os.getenv("DBMANAGER_PROXY_CERT_PATH", "").strip(),
        key_path=os.getenv("DBMANAGER_PROXY_KEY_PATH", "").strip(),
    )

    cfg = ProxyConfig(
        enabled=True if enabled is None else enabled,
        mode=mode,
        domain=domain,
        acme=acme,
        manual_cert=manual,
        admin_url=os.getenv(
            "DBMANAGER_PROXY_ADMIN_URL", "unix:///run/caddy-admin/admin.sock"
        ),
        caddy_container=os.getenv("DBMANAGER_PROXY_CADDY_CONTAINER", "dbmanager-caddy"),
    )
    return cfg if cfg.is_configured() else None


class ProxyConfigManager:
    """Load/save proxy.json. File state is the source of truth at runtime;
    env vars are consulted only for first-run bootstrap."""

    def __init__(self, path: Path = PROXY_CONFIG_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> ProxyConfig:
        if not self.path.exists():
            return ProxyConfig()
        with self._lock:
            with open(self.path, "r") as f:
                data = json.load(f)
        return ProxyConfig.model_validate(data)

    def save(self, cfg: ProxyConfig) -> None:
        payload: Dict[str, Any] = cfg.model_dump(mode="json")
        with self._lock:
            tmp = self.path.with_suffix(".json.tmp")
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            tmp.replace(self.path)

    def bootstrap_from_env_if_missing(self) -> Optional[ProxyConfig]:
        """If proxy.json missing and env vars provide a complete config,
        write it. Returns the written config, or None if nothing was done."""
        if self.exists():
            return None
        cfg = proxy_config_from_env()
        if cfg is None:
            return None
        self.save(cfg)
        return cfg
