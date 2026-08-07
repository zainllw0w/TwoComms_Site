#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYSTEM_PYTHON="${TWC_DEPLOY_SYSTEM_PYTHON:-/opt/alt/python314/bin/python3.14}"
if [[ $# -ne 2 || $1 != "--target-sha" || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
    echo "usage: $0 --target-sha <40-character-lowercase-commit-sha>" >&2
    exit 64
fi
exec "$SYSTEM_PYTHON" "$SCRIPT_DIR/scripts/deploy_release.py" "$@"
