"""Pretty-print effective DBManager runtime configuration at startup."""

from __future__ import annotations

import os
from typing import Iterable, List, Tuple

from rich.console import Console
from rich.table import Table

from proxy.config import ProxyConfig, ProxyConfigManager, ProxyMode

console = Console()

# env-var name substrings that imply a secret value — masked in output
_SECRET_HINTS = ("PASSWORD", "SECRET", "TOKEN", "KEY", "JWT")

# DBManager-relevant env prefixes / explicit names to surface
_ENV_PREFIXES = (
    "DBMANAGER_",
    "ALLOWED_ORIGINS",
    "VITE_API_URL",
    "POSTGRES_",
    "MYSQL_",
    "MINIO_",
    "CF_API_TOKEN",
    "AWS_",
    "DO_AUTH_TOKEN",
    "GANDI_API_TOKEN",
    "DUCKDNS_API_TOKEN",
)


def _mask_value(name: str, value: str) -> str:
    if not value:
        return "(unset)"
    if any(h in name.upper() for h in _SECRET_HINTS):
        if len(value) <= 4:
            return "****"
        return value[:2] + "…" + value[-2:]
    return value


def _collect_env() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for k, v in sorted(os.environ.items()):
        if any(k == p or k.startswith(p) for p in _ENV_PREFIXES):
            out.append((k, _mask_value(k, v)))
    return out


def _proxy_summary(cfg: ProxyConfig) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = [
        ("enabled", str(cfg.enabled)),
        ("mode", cfg.mode.value),
        ("domain", cfg.domain or "(unset)"),
    ]
    if cfg.mode == ProxyMode.HTTPS:
        rows.append(("acme.method", cfg.acme.method.value))
        if cfg.acme.email:
            rows.append(("acme.email", cfg.acme.email))
        if cfg.acme.dns_provider:
            rows.append(("acme.dns_provider", cfg.acme.dns_provider.value))
            if cfg.acme.credentials_env:
                env_val = os.getenv(cfg.acme.credentials_env, "")
                rows.append(
                    (
                        f"acme.{cfg.acme.credentials_env}",
                        _mask_value(cfg.acme.credentials_env, env_val),
                    )
                )
        if cfg.manual_cert.cert_path:
            rows.append(("manual_cert.cert", cfg.manual_cert.cert_path))
            rows.append(("manual_cert.key", cfg.manual_cert.key_path))
    rows.append(("routes.frontend", cfg.routes.frontend_upstream))
    rows.append(("routes.backend", cfg.routes.backend_upstream + cfg.routes.backend_path_prefix))
    rows.append(("admin_url", cfg.admin_url))
    return rows


def _render_table(title: str, rows: Iterable[Tuple[str, str]]) -> Table:
    t = Table(title=title, show_header=True, header_style="bold cyan", title_justify="left")
    t.add_column("key", style="bold")
    t.add_column("value")
    for k, v in rows:
        t.add_row(k, v)
    return t


def print_runtime_config() -> None:
    """Print a Rich table block summarizing env + proxy config."""
    console.rule("[bold cyan]DBManager runtime configuration[/bold cyan]")

    env_rows = _collect_env()
    if env_rows:
        console.print(_render_table("Environment", env_rows))

    try:
        cfg = ProxyConfigManager().load()
        console.print(_render_table("Reverse proxy", _proxy_summary(cfg)))
    except Exception as e:
        console.print(f"[yellow]proxy config unavailable: {e}[/yellow]")

    console.rule()
