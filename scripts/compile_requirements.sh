#!/bin/sh
set -eu

EXPECTED_UV_VERSION="uv 0.12.2"
UV_BIN="${UV_BIN:-uv}"
PYTHON_BIN="${PYTHON_BIN:-python3.14}"
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INPUT_PATH="twocomms/requirements.in"
LOCK_PATH="$ROOT_DIR/twocomms/requirements.lock"
HTTP_ECE_BUILDER="$ROOT_DIR/scripts/build_http_ece_wheel.py"
HTTP_ECE_SDIST="${HTTP_ECE_SDIST:-}"
TEMP_DIR=""
TEMP_LOCK=""

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT HUP INT TERM

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
    echo "error: uv 0.12.2 is required but uv was not found" >&2
    exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "error: Python 3.14 is required but ${PYTHON_BIN} was not found" >&2
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

if [ ! -s "$ROOT_DIR/$INPUT_PATH" ]; then
    echo "error: requirements input is missing or empty" >&2
    exit 1
fi
if [ ! -s "$HTTP_ECE_BUILDER" ]; then
    echo "error: reproducible http-ece wheel builder is missing" >&2
    exit 1
fi

TEMP_DIR=$(mktemp -d "$LOCK_PATH.build.XXXXXX")
TEMP_LOCK="$TEMP_DIR/requirements.lock"
TEMP_WHEEL_DIR="$TEMP_DIR/wheelhouse"
mkdir -p -- "$TEMP_WHEEL_DIR"

# http-ece is pure Python and is published only as an sdist; pywebpush
# requires it. Keep every compiled dependency wheel-only and make this
# single, explicit exception visible in the generated lock metadata.
(cd "$ROOT_DIR" && "$UV_BIN" pip compile "$INPUT_PATH" \
    --output-file "$TEMP_LOCK" \
    --python-version 3.14.6 \
    --python-platform x86_64-manylinux_2_28 \
    --only-binary :all: \
    --no-binary http-ece \
    --generate-hashes \
    --resolution highest \
    --exclude-newer 2026-08-07T00:00:00Z \
    --no-emit-index-url \
    --custom-compile-command "./scripts/compile_requirements.sh")

if [ -n "$HTTP_ECE_SDIST" ]; then
    "$PYTHON_BIN" "$HTTP_ECE_BUILDER" \
        --sdist "$HTTP_ECE_SDIST" \
        --wheel-dir "$TEMP_WHEEL_DIR" \
        --lock "$TEMP_LOCK" \
        --source-date-epoch 315532800
else
    "$PYTHON_BIN" "$HTTP_ECE_BUILDER" \
        --wheel-dir "$TEMP_WHEEL_DIR" \
        --lock "$TEMP_LOCK" \
        --source-date-epoch 315532800
fi

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
