#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYSTEM_PYTHON="${TWC_DEPLOY_SYSTEM_PYTHON:-/opt/alt/python314/bin/python3.14}"
exec "$SYSTEM_PYTHON" "$SCRIPT_DIR/scripts/deploy_release.py" "$@"
