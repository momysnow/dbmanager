"""Render a Caddyfile from a ProxyConfig."""

from __future__ import annotations

from proxy.config import AcmeMethod, DnsProvider, ProxyConfig, ProxyMode

# Mapping caddy `dns` plugin keyword + the env-var token reference used in
# the generated Caddyfile. Keep in sync with the plugins baked into
# caddy/Dockerfile.
_DNS_DIRECTIVE = {
    DnsProvider.CLOUDFLARE: "cloudflare {env.CF_API_TOKEN}",
    DnsProvider.ROUTE53: "route53",
    DnsProvider.DIGITALOCEAN: "digitalocean {env.DO_AUTH_TOKEN}",
    DnsProvider.GANDI: "gandi {env.GANDI_API_TOKEN}",
    DnsProvider.DUCKDNS: "duckdns {env.DUCKDNS_API_TOKEN}",
}


def _global_block(cfg: ProxyConfig) -> str:
    lines = ["{", "    admin 0.0.0.0:2019"]
    if cfg.mode == ProxyMode.HTTPS and cfg.acme.email and cfg.acme.method in (
        AcmeMethod.DNS,
        AcmeMethod.HTTP01,
    ):
        lines.append(f"    email {cfg.acme.email}")
    if cfg.mode == ProxyMode.HTTP:
        lines.append("    auto_https off")
    lines.append("}")
    return "\n".join(lines)


def _tls_block(cfg: ProxyConfig) -> str:
    if cfg.mode != ProxyMode.HTTPS:
        return ""
    m = cfg.acme.method
    if m == AcmeMethod.SELFSIGNED:
        return "    tls internal\n"
    if m == AcmeMethod.MANUAL:
        return f"    tls {cfg.manual_cert.cert_path} {cfg.manual_cert.key_path}\n"
    if m == AcmeMethod.DNS and cfg.acme.dns_provider:
        directive = _DNS_DIRECTIVE[cfg.acme.dns_provider]
        return "    tls {\n" f"        dns {directive}\n" "    }\n"
    # HTTP-01 → no explicit tls block (Caddy default).
    return ""


def _site_block(cfg: ProxyConfig) -> str:
    if cfg.mode == ProxyMode.HTTP:
        site_addr = f"http://{cfg.domain}"
    else:
        site_addr = cfg.domain

    backend_prefix = cfg.routes.backend_path_prefix.rstrip("/") or "/api"

    parts = [
        f"{site_addr} {{",
        f"    handle {backend_prefix}/* {{",
        f"        reverse_proxy {cfg.routes.backend_upstream}",
        "    }",
        "    handle {",
        f"        reverse_proxy {cfg.routes.frontend_upstream}",
        "    }",
    ]
    tls = _tls_block(cfg)
    if tls:
        parts.append(tls.rstrip())
    parts.append("}")
    return "\n".join(parts)


def render_caddyfile(cfg: ProxyConfig) -> str:
    """Produce the textual Caddyfile content."""
    if not cfg.enabled or cfg.mode == ProxyMode.DISABLED:
        # Keep Caddy alive with a placeholder responder so admin API stays up.
        return (
            "{\n    admin 0.0.0.0:2019\n    auto_https off\n}\n\n"
            ":80 {\n    respond \"DBManager proxy disabled\" 503\n}\n"
        )

    return _global_block(cfg) + "\n\n" + _site_block(cfg) + "\n"
