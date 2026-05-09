#!/bin/sh
# Caddy entrypoint — resolves twelve-factor `${NAME}_FILE` env vars before
# handing off to Caddy.
#
# Why: Caddy's `{env.NAME}` interpolation reads only environment variables.
# Plain env vars are visible in `docker inspect`, `/proc/1/environ`, and any
# debug endpoint that lists env. Mounting the secret as a file (docker /
# swarm secrets, Kubernetes secrets, podman --secret …) keeps it off the
# environment of the running process, but Caddy can't read it directly.
#
# This script bridges the gap: for every supported token name, if
# `<NAME>_FILE` points to a readable file, export `<NAME>` with its
# contents. The plain env-var path still works for users who can't or
# won't switch to mounted secrets.

set -eu

# Names of env vars that may be sourced from `<NAME>_FILE`.
secret_vars="
CF_API_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
DO_AUTH_TOKEN
GANDI_API_TOKEN
DUCKDNS_API_TOKEN
"

# Make sure the admin unix-socket directory exists before Caddy boots. The
# directory comes from a Docker volume that is also mounted into the backend
# container; only those two containers can reach the socket.
mkdir -p /run/caddy-admin
chmod 0750 /run/caddy-admin

for name in $secret_vars; do
    file_var="${name}_FILE"
    # Indirect lookup that is portable across busybox/dash/ash.
    eval "file_path=\${$file_var:-}"
    if [ -n "$file_path" ]; then
        if [ ! -r "$file_path" ]; then
            echo "[caddy entrypoint] $file_var=$file_path is not readable" >&2
            exit 1
        fi
        # Strip a single trailing newline (printf, k8s secrets often add one)
        # without invoking external tools that might not be in the image.
        value=$(cat "$file_path")
        export "$name=$value"
        # Best-effort: clear the file path so it doesn't leak to children.
        unset "$file_var"
    fi
done

exec caddy "$@"
