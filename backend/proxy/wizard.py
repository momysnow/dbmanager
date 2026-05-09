"""Interactive bootstrap for the reverse proxy.

Runs at container startup. Resolution order:
  1. proxy.json already valid → noop
  2. env vars complete → write proxy.json from env
  3. DBMANAGER_PROXY_NONINTERACTIVE=true → write disabled config, log warning
  4. TTY available → interactive Rich/InquirerPy prompts
  5. else → write disabled config
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from rich.console import Console

from proxy.config import (
    AcmeConfig,
    AcmeMethod,
    DnsProvider,
    DNS_PROVIDER_ENV,
    ManualCertConfig,
    ProxyConfig,
    ProxyConfigManager,
    ProxyMode,
    _DOMAIN_RE,
    _EMAIL_RE,
    _SAFE_PATH_RE,
    proxy_config_from_env,
)

logger = logging.getLogger(__name__)
console = Console()


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _noninteractive() -> bool:
    raw = os.getenv("DBMANAGER_PROXY_NONINTERACTIVE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _disabled_config() -> ProxyConfig:
    return ProxyConfig(enabled=False, mode=ProxyMode.DISABLED)


def _prompt_interactive() -> ProxyConfig:
    from InquirerPy import inquirer  # local import — only needed in TTY path

    console.print("\n[bold cyan]── DBManager reverse-proxy setup ──[/bold cyan]\n")

    enable = inquirer.confirm(message="Enable reverse proxy?", default=True).execute()
    if not enable:
        return _disabled_config()

    mode_choice = inquirer.select(
        message="Mode:",
        choices=[
            {"name": "HTTPS (with TLS cert)", "value": ProxyMode.HTTPS.value},
            {"name": "HTTP (plain, no TLS)", "value": ProxyMode.HTTP.value},
        ],
        default=ProxyMode.HTTPS.value,
    ).execute()
    mode = ProxyMode(mode_choice)

    domain = (
        inquirer.text(
            message="Domain (e.g. db.example.com or localhost):",
            validate=lambda v: bool(_DOMAIN_RE.match(v.strip().lower())),
            invalid_message="Must be a valid FQDN or 'localhost' — no whitespace or special chars.",
        )
        .execute()
        .strip()
        .lower()
    )

    acme = AcmeConfig()
    manual = ManualCertConfig()

    if mode == ProxyMode.HTTPS:
        method_choice = inquirer.select(
            message="Certificate method:",
            choices=[
                {
                    "name": "DNS-01 (Let's Encrypt via DNS provider API)",
                    "value": AcmeMethod.DNS.value,
                },
                {
                    "name": "HTTP-01 (Let's Encrypt, requires public port 80)",
                    "value": AcmeMethod.HTTP01.value,
                },
                {"name": "Manual cert / key files", "value": AcmeMethod.MANUAL.value},
                {
                    "name": "Self-signed (Caddy internal — dev only)",
                    "value": AcmeMethod.SELFSIGNED.value,
                },
            ],
            default=AcmeMethod.DNS.value,
        ).execute()
        acme.method = AcmeMethod(method_choice)

        if acme.method in (AcmeMethod.DNS, AcmeMethod.HTTP01):
            acme.email = (
                inquirer.text(
                    message="ACME contact email:",
                    validate=lambda v: bool(_EMAIL_RE.match(v.strip())),
                    invalid_message="Enter a valid email (used by Let's Encrypt for renewal alerts).",
                )
                .execute()
                .strip()
            )

        if acme.method == AcmeMethod.DNS:
            prov_choice = inquirer.select(
                message="DNS provider:",
                choices=[{"name": p.value, "value": p.value} for p in DnsProvider],
            ).execute()
            acme.dns_provider = DnsProvider(prov_choice)
            env_var = DNS_PROVIDER_ENV[acme.dns_provider]
            acme.credentials_env = env_var
            # The caddy container's entrypoint also resolves `${NAME}_FILE`
            # → secret-file path, so accept either form as proof the token
            # will be available at runtime.
            file_var = f"{env_var}_FILE"
            if not os.getenv(env_var) and not os.getenv(file_var):
                console.print(
                    f"[yellow]⚠ neither {env_var} nor {file_var} is set — proxy will "
                    f"fail to issue certificates until one is set and caddy is "
                    f"restarted.[/yellow]"
                )

        if acme.method == AcmeMethod.MANUAL:
            _path_invalid = (
                "Must be an absolute POSIX path with no whitespace or shell "
                "metacharacters."
            )
            manual.cert_path = (
                inquirer.text(
                    message="Path to certificate file (PEM):",
                    validate=lambda v: bool(_SAFE_PATH_RE.match(v.strip())),
                    invalid_message=_path_invalid,
                )
                .execute()
                .strip()
            )
            manual.key_path = (
                inquirer.text(
                    message="Path to private key file (PEM):",
                    validate=lambda v: bool(_SAFE_PATH_RE.match(v.strip())),
                    invalid_message=_path_invalid,
                )
                .execute()
                .strip()
            )

    return ProxyConfig(
        enabled=True,
        mode=mode,
        domain=domain,
        acme=acme,
        manual_cert=manual,
        admin_url=os.getenv(
            "DBMANAGER_PROXY_ADMIN_URL", "unix:///run/caddy-admin/admin.sock"
        ),
        caddy_container=os.getenv("DBMANAGER_PROXY_CADDY_CONTAINER", "dbmanager-caddy"),
    )


def bootstrap(force: bool = False) -> Optional[ProxyConfig]:
    """Idempotent bootstrap. Returns the active ProxyConfig (or None on fatal)."""
    mgr = ProxyConfigManager()

    if mgr.exists() and not force:
        cfg = mgr.load()
        if cfg.is_configured() or not cfg.enabled:
            logger.info("proxy.json already present — skipping bootstrap")
            return cfg

    # Try env first.
    env_cfg = proxy_config_from_env()
    if env_cfg is not None:
        mgr.save(env_cfg)
        console.print(
            "[green]✓ proxy config written from environment variables[/green]"
        )
        return env_cfg

    # No env → either non-interactive (disable) or interactive prompts.
    if _noninteractive() or not _is_tty():
        console.print(
            "[yellow]⚠ proxy not configured (no env vars, non-interactive). "
            "Starting with proxy disabled. Run "
            "`python main.py proxy bootstrap --force` from a TTY to configure."
            "[/yellow]"
        )
        cfg = _disabled_config()
        mgr.save(cfg)
        return cfg

    cfg = _prompt_interactive()
    mgr.save(cfg)
    console.print("[green]✓ proxy config saved to ~/.dbmanager/proxy.json[/green]")
    return cfg
