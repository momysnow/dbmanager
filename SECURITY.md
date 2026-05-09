# Security Notes

## Configuring database connections — least privilege

**TL;DR — never give DBManager a superuser account on the database it backs up.**

DBManager exposes an authenticated `/query` endpoint that lets users with
the `viewer` role run read-only SQL. The "read-only" gate is a parser-level
check (sqlparse) that blocks DML/DDL, but it cannot stop a `SELECT` that
calls a privileged function. Examples that look like a SELECT but execute
side effects on a superuser connection:

- PostgreSQL: `SELECT pg_read_file('/etc/passwd')`,
  `SELECT lo_export(...)`, `COPY (SELECT ...) TO PROGRAM 'curl ...'`
  (write-blocked, but worth flagging) — all available to roles with
  `pg_read_server_files` / `SUPERUSER` membership.
- MySQL/MariaDB: `LOAD_FILE('/etc/passwd')`, `INTO OUTFILE` —
  available to accounts with the `FILE` privilege.
- SQL Server: `xp_cmdshell`, `OPENROWSET` — `sysadmin`-only.

When you wire DBManager to a database, give it an account that only has
the privileges it needs:

| Operation                | Privilege                                            |
|--------------------------|-------------------------------------------------------|
| Backup (logical dump)    | `SELECT` on the schemas/tables you want to back up.   |
| Backup (physical / `pg_dumpall`) | A replication / backup-specific role (`pg_read_all_data` on Postgres ≥ 14). |
| Schema + table listing   | Standard read on `information_schema`.                |
| `/query` for `viewer`s   | Same `SELECT` grants — **never** the `FILE` /         |
|                          | `pg_read_server_files` / `sysadmin` membership.       |

If your DB role hands out filesystem read or remote-program execution as a
side effect of `SELECT`, the parser-level guard cannot help.

## Reverse-proxy admin API

The Caddy admin API used by the backend to hot-reload configuration is
bound to a **unix socket** (`/run/caddy-admin/admin.sock`) shared via a
Docker volume mount with the backend container only. The frontend and
docker-socket-proxy containers do not see the socket and cannot reach
admin.

If you change the deployment topology (e.g. replace Caddy with another
reverse proxy or move admin onto TCP), keep this principle: admin API
must be reachable only from the backend, and never via TCP on the same
Docker bridge as untrusted containers — the Caddy `origins` directive
filters HTTP `Origin` headers, not source IP.

## Docker socket access

The backend talks to a restricted `tecnativa/docker-socket-proxy` for the
DB-management workflows that need it (SQL Server backup-via-exec, etc.).
The proxy filters by HTTP method/endpoint, but cannot scope a request to
a specific container. The backend additionally enforces an in-process
allow/deny list (`backend/core/docker_safety.py`) that refuses to operate
on any container reserved for the DBManager stack itself. **Do not
configure a database with `host` set to the name of a stack container**
(e.g. `dbmanager-caddy`, `dbmanager-backend`) — that's never a real DB.

## Production deployment

- Deploy with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
  The prod overlay drops dev bind mounts and switches the frontend to a
  static nginx build (no Vite dev server, no `/docs` proxy).
- Set `DBMANAGER_ENV=production` (the default). Swagger `/docs`, `/redoc`,
  and `/openapi.json` are gated on this and return 404 in prod.
- Set `DBMANAGER_ADMIN_PASSWORD` and `DBMANAGER_JWT_SECRET` in `.env` —
  the backend refuses to boot without them or with placeholder values.
- DNS-provider tokens prefer the `${NAME}_FILE` form (mounted secret).
- Consider running behind another upstream that terminates TLS with a
  trusted certificate (the included Caddy can do ACME on its own as long
  as it has internet egress and DNS access).
