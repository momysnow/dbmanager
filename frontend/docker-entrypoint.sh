#!/bin/sh
# Sync dependencies in case package.json changed via bind mount
npm install --prefer-offline --no-audit --no-fund 2>/dev/null
exec npm run dev -- --host
