#!/bin/sh
set -eu

EXPECTED_UV_VERSION="uv 0.12.2"
UV_BIN="${UV_BIN:-uv}"
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INPUT_PATH="$ROOT_DIR/twocomms/requirements.in"
LOCK_PATH="$ROOT_DIR/twocomms/requirements.lock"
TEMP_LOCK=""

cleanup() {
    if [ -n "$TEMP_LOCK" ] && [ -e "$TEMP_LOCK" ]; then
        rm -f -- "$TEMP_LOCK"
    fi
}
trap cleanup EXIT HUP INT TERM

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
    echo "error: uv 0.12.2 is required but uv was not found" >&2
    exit 1
fi

UV_VERSION=$($UV_BIN --version 2>/dev/null || true)
case "$UV_VERSION" in
    "$EXPECTED_UV_VERSION"|"$EXPECTED_UV_VERSION "*) ;;
    *)
        echo "error: expected uv 0.12.2, got ${UV_VERSION:-unknown}" >&2
        exit 1
        ;;
esac

if [ ! -s "$INPUT_PATH" ]; then
    echo "error: requirements input is missing or empty" >&2
    exit 1
fi

TEMP_LOCK=$(mktemp "$LOCK_PATH.tmp.XXXXXX")

# http-ece is pure Python and is published only as an sdist; pywebpush
# requires it. Keep every compiled dependency wheel-only and make this
# single, explicit exception visible in the generated lock metadata.
"$UV_BIN" pip compile "$INPUT_PATH" \
    --output-file "$TEMP_LOCK" \
    --python-version 3.14.6 \
    --python-platform x86_64-manylinux_2_28 \
    --only-binary :all: \
    --no-binary http-ece \
    --generate-hashes \
    --resolution highest \
    --exclude-newer 2026-08-07T00:00:00Z \
    --no-emit-index-url \
    --custom-compile-command "./scripts/compile_requirements.sh"

if [ ! -s "$TEMP_LOCK" ]; then
    echo "error: resolver produced an empty lock" >&2
    exit 1
fi
if ! grep -Eq '^[-A-Za-z0-9_.]+==[^[:space:]\\]+[[:space:]]*\\?$' "$TEMP_LOCK"; then
    echo "error: resolver output contains no exact requirements" >&2
    exit 1
fi
if ! grep -Eq -- '--hash=sha256:[0-9a-f]{64}' "$TEMP_LOCK"; then
    echo "error: resolver output contains no SHA-256 hashes" >&2
    exit 1
fi

mv -f -- "$TEMP_LOCK" "$LOCK_PATH"
TEMP_LOCK=""
