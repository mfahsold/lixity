#!/usr/bin/env bash
# Compatibility wrapper; the installed CLI owns all lifecycle behavior.
# Usage: lixity-start.sh [start|stop|restart|status] [service options] [PROJECT]
set -euo pipefail

if ! command -v lixity >/dev/null 2>&1; then
    echo "[ERR] lixity is not on PATH. Follow https://mfahsold.github.io/lixity/guides/installation.html" >&2
    exit 1
fi
if [ "$#" -eq 0 ]; then
    set -- start
fi
exec lixity service "$@"
