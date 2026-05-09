"""Proxy configuration: schema, persistence, env-var overlay."""

from __future__ import annotations

import json
import os
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from config import CONFIG_DIR

PROXY_CONFIG_FILE = CONFIG_DIR / "proxy.json"


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


class AcmeConfig(BaseModel):
    method: AcmeMethod = AcmeMethod.NONE
    email: str = ""
    dns_provider: Optional[DnsProvider] = None
    # Reference only, never the secret itself.
    credentials_env: Optional[str] = None


class ManualCertConfig(BaseModel):
    cert_path: str = ""
    key_path: str = ""


class ProxyRoutes(BaseModel):
    frontend_upstream: str = "frontend:5173"
    backend_upstream: str = "backend:8000"
    backend_path_prefix: str = "/api"


class ProxyConfig(BaseModel):
    enabled: bool = True
    mode: ProxyMode = ProxyMode.DISABLED
    domain: str = ""
    acme: AcmeConfig = Field(default_factory=AcmeConfig)
    manual_cert: ManualCertConfig = Field(default_factory=ManualCertConfig)
    routes: ProxyRoutes = Field(default_factory=ProxyRoutes)
    admin_url: str = "http://caddy:2019"
    caddy_container: str = "dbmanager-caddy"

    @field_validator("domain")
    @classmethod
    def _strip_domain(cls, v: str) -> str:
        return v.strip().lower()

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
        admin_url=os.getenv("DBMANAGER_PROXY_ADMIN_URL", "http://caddy:2019"),
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
