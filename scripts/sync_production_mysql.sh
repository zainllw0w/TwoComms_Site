#!/usr/bin/env bash
# Pull the production default MariaDB alias into a disposable local database.

set -euo pipefail
umask 077

SCRIPT_NAME="sync_production_mysql"
MODE="dry-run"
CONFIRMED=0
APPLY_MODE=0
DRY_RUN_REQUESTED=0

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_HOST="${TWOCOMMS_SSH_HOST:-}"
SSH_USER="${TWOCOMMS_SSH_USER:-}"
SSH_PORT="${TWOCOMMS_SSH_PORT:-22}"
REMOTE_PROJECT="${TWOCOMMS_REMOTE_PROJECT:-}"
REMOTE_VENV="${TWOCOMMS_REMOTE_VENV:-}"
REMOTE_DEFAULTS_FILE="${TWOCOMMS_REMOTE_MYSQL_DEFAULTS_FILE:-\$HOME/.my.cnf}"
REMOTE_DB_NAMES="${TWOCOMMS_REMOTE_DB_NAMES:-}"

LOCAL_HOST="${TWOCOMMS_LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${TWOCOMMS_LOCAL_PORT:-3306}"
LOCAL_DEFAULTS_FILE="${TWOCOMMS_LOCAL_MYSQL_DEFAULTS_FILE:-${HOME:-}/.my.cnf}"
LOCAL_DB_PREFIX="${TWOCOMMS_LOCAL_DB_PREFIX-twc_snapshot_}"
SYNC_ROOT="${TWOCOMMS_SYNC_ROOT:-${HOME:-}/.twocomms-db-sync}"
MIN_DUMP_BYTES="${TWOCOMMS_MIN_DUMP_BYTES:-10240}"
RETENTION_DAYS="${TWOCOMMS_SNAPSHOT_RETENTION_DAYS:-14}"
RUN_ID="${TWOCOMMS_SYNC_RUN_ID:-$(date +%Y%m%d%H%M%S)-$$}"

REMOTE_DB_NAME=""
TARGET_DB=""
STAGING_DB=""
SNAPSHOT_ARCHIVE=""
INCOMING_ARCHIVE=""
ROLLBACK_ARCHIVE=""
TARGET_EXISTED=0
REPLACEMENT_STARTED=0
SYNC_SUCCESS=0
LOCK_DIR=""
LOCK_ACQUIRED=0
LOCAL_CLIENT_BIN=""
LOCAL_DUMP_BIN=""
TEMP_FILES=()

usage() {
  cat <<'USAGE'
Usage: sync_production_mysql.sh [--dry-run]
       sync_production_mysql.sh --apply --confirm-production-snapshot

The command synchronizes only the production Django database alias `default`.
TWOCOMMS_REMOTE_DB_NAMES must contain exactly one expected non-DTF database
name; the remote command verifies that it equals settings.DATABASES['default'].
USAGE
}

error() {
  printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$*" >&2
}

die() {
  error "$*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}

require_private_file() {
  local path="$1"
  [ -r "$path" ] || die "private defaults file is not readable: $path"
  case "$(file_mode "$path")" in
    400|600) ;;
    *) die "private defaults file must have mode 0600 or 0400: $path" ;;
  esac
}

validate_integer() {
  local label="$1"
  local value="$2"
  case "$value" in
    ''|*[!0-9]*) die "$label must be a positive integer" ;;
  esac
  [ "$value" -gt 0 ] || die "$label must be a positive integer"
}

validate_db_name() {
  local value="$1"
  case "$value" in
    ''|--*|-*|*[!A-Za-z0-9_-]*) die "unsafe database name: $value" ;;
  esac
  [ "${#value}" -le 64 ] || die "database name is longer than 64 characters"
}

validate_remote_path() {
  local value="$1"
  case "$value" in
    \$HOME/[A-Za-z0-9_./-]*|/[A-Za-z0-9_./-]*) ;;
    *) die "remote path must be a safe absolute or \$HOME path" ;;
  esac
}

validate_ssh_endpoint() {
  case "$SSH_HOST" in
    ''|*[!A-Za-z0-9._:-]*) die "TWOCOMMS_SSH_HOST is required and must be a safe hostname or address" ;;
  esac
  case "$SSH_USER" in
    ''|*[!A-Za-z0-9._-]*) die "TWOCOMMS_SSH_USER is required and must be a safe account name" ;;
  esac
}

is_loopback_host() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    localhost|127.0.0.1|::1|\[::1\]) return 0 ;;
    *) return 1 ;;
  esac
}

sql_identifier() {
  printf '`%s`' "$1"
}

sql_literal() {
  printf "'%s'" "$1"
}

parse_arguments() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --help|-h)
        usage
        exit 0
        ;;
      --dry-run)
        [ "$APPLY_MODE" -eq 0 ] || die "--dry-run and --apply cannot be combined"
        [ "$DRY_RUN_REQUESTED" -eq 0 ] || die "--dry-run may be specified only once"
        MODE="dry-run"
        DRY_RUN_REQUESTED=1
        ;;
      --apply)
        [ "$APPLY_MODE" -eq 0 ] || die "--apply may be specified only once"
        [ "$DRY_RUN_REQUESTED" -eq 0 ] || die "--dry-run and --apply cannot be combined"
        MODE="apply"
        APPLY_MODE=1
        ;;
      --confirm-production-snapshot)
        CONFIRMED=1
        ;;
      *) die "unknown option or positional database name: $1" ;;
    esac
    shift
  done
}

resolve_database_mapping() {
  [ -n "$REMOTE_DB_NAMES" ] || die "an explicit TWOCOMMS_REMOTE_DB_NAMES value is required"
  case "$REMOTE_DB_NAMES" in
    *,*) die "exactly one production default database must be configured" ;;
  esac
  validate_db_name "$REMOTE_DB_NAMES"
  case "$(printf '%s' "$REMOTE_DB_NAMES" | tr '[:upper:]' '[:lower:]')" in
    *dtf*) die "DTF databases are outside the supported sync scope" ;;
  esac
  case "$LOCAL_DB_PREFIX" in
    twc_snapshot_*) ;;
    *) die "TWOCOMMS_LOCAL_DB_PREFIX must begin with twc_snapshot_" ;;
  esac
  validate_db_name "$LOCAL_DB_PREFIX"
  REMOTE_DB_NAME="$REMOTE_DB_NAMES"
  TARGET_DB="${LOCAL_DB_PREFIX}${REMOTE_DB_NAME}"
  validate_db_name "$TARGET_DB"
  [ "$TARGET_DB" != "$REMOTE_DB_NAME" ] || die "local target must not equal the production database name"
}

validate_configuration() {
  validate_integer "TWOCOMMS_SSH_PORT" "$SSH_PORT"
  validate_integer "TWOCOMMS_LOCAL_PORT" "$LOCAL_PORT"
  validate_integer "TWOCOMMS_MIN_DUMP_BYTES" "$MIN_DUMP_BYTES"
  validate_integer "TWOCOMMS_SNAPSHOT_RETENTION_DAYS" "$RETENTION_DAYS"
  case "$RUN_ID" in
    ''|*[!0-9-]*) die "TWOCOMMS_SYNC_RUN_ID may contain only digits and hyphens" ;;
  esac
  resolve_database_mapping
  [ -n "$SYNC_ROOT" ] || die "TWOCOMMS_SYNC_ROOT must not be empty"
  [ "$SYNC_ROOT" != "/" ] || die "TWOCOMMS_SYNC_ROOT may not be the filesystem root"
  local sync_parent
  sync_parent="$(cd "$(dirname "$SYNC_ROOT")" 2>/dev/null && pwd || true)"
  [ -n "$sync_parent" ] || die "TWOCOMMS_SYNC_ROOT parent must exist"
  case "$sync_parent/$(basename "$SYNC_ROOT")/" in
    "$REPO_ROOT"/*) die "TWOCOMMS_SYNC_ROOT must be outside the repository" ;;
  esac

  if [ "$APPLY_MODE" -eq 1 ]; then
    [ "$CONFIRMED" -eq 1 ] || die "--apply requires --confirm-production-snapshot"
    [ -n "${TWOCOMMS_DEPLOY_PASSWORD:-}" ] || die "TWOCOMMS_DEPLOY_PASSWORD must be exported for apply mode"
    validate_ssh_endpoint
    validate_remote_path "$REMOTE_DEFAULTS_FILE"
    validate_remote_path "$REMOTE_PROJECT"
    validate_remote_path "$REMOTE_VENV"
    is_loopback_host "$LOCAL_HOST" || die "local MariaDB host must be loopback"
    require_command sshpass
    require_command ssh
    require_command gzip
    require_private_file "$LOCAL_DEFAULTS_FILE"
    LOCAL_CLIENT_BIN="$(command -v mariadb || command -v mysql || true)"
    LOCAL_DUMP_BIN="$(command -v mariadb-dump || command -v mysqldump || true)"
    [ -n "$LOCAL_CLIENT_BIN" ] || die "local MariaDB client is unavailable"
    [ -n "$LOCAL_DUMP_BIN" ] || die "local MariaDB dump client is unavailable"
  elif [ "$CONFIRMED" -eq 1 ]; then
    die "--confirm-production-snapshot requires --apply"
  fi
}

local_sql() {
  "$LOCAL_CLIENT_BIN" \
    --defaults-extra-file="$LOCAL_DEFAULTS_FILE" \
    --protocol=TCP --host="$LOCAL_HOST" --port="$LOCAL_PORT" \
    --batch --skip-column-names --raw --execute="$1"
}

local_import() {
  "$LOCAL_CLIENT_BIN" \
    --defaults-extra-file="$LOCAL_DEFAULTS_FILE" \
    --protocol=TCP --host="$LOCAL_HOST" --port="$LOCAL_PORT" \
    --binary-mode "$1"
}

local_dump() {
  "$LOCAL_DUMP_BIN" \
    --defaults-extra-file="$LOCAL_DEFAULTS_FILE" \
    --protocol=TCP --host="$LOCAL_HOST" --port="$LOCAL_PORT" \
    --single-transaction --quick --skip-lock-tables \
    --routines --triggers --events --no-tablespaces "$1"
}

remote_dump_command() {
  local expected="$REMOTE_DB_NAME"
  printf '%s' \
    "set -eu; source '$REMOTE_VENV'; cd '$REMOTE_PROJECT'; "\
    "actual=\$(python -c 'from twocomms import production_settings as settings; print(settings.DATABASES[\"default\"][\"NAME\"])' | tail -n 1); "\
    "[ \"\$actual\" = '$expected' ] || { echo production-default-mismatch >&2; exit 65; }; "\
    "case \"\$(printf '%s' \"\$actual\" | tr '[:upper:]' '[:lower:]')\" in *dtf*) echo dtf-forbidden >&2; exit 66;; esac; "\
    "if command -v mariadb-dump >/dev/null 2>&1; then dump_bin=\$(command -v mariadb-dump); else dump_bin=\$(command -v mysqldump); fi; "\
    "exec \"\$dump_bin\" --defaults-extra-file=\"$REMOTE_DEFAULTS_FILE\" --single-transaction --quick --skip-lock-tables --routines --triggers --events --no-tablespaces \"\$actual\""
}

run_remote_dump() {
  local command_text
  command_text="$(remote_dump_command)"
  local quoted_command
  printf -v quoted_command '%q' "$command_text"
  SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
    -o StrictHostKeyChecking=no -p "$SSH_PORT" \
    "${SSH_USER}@${SSH_HOST}" "bash -lc $quoted_command"
}

acquire_lock() {
  mkdir -p "$SYNC_ROOT" "$SYNC_ROOT/incoming" "$SYNC_ROOT/snapshots" "$SYNC_ROOT/rollback"
  chmod 700 "$SYNC_ROOT" "$SYNC_ROOT/incoming" "$SYNC_ROOT/snapshots" "$SYNC_ROOT/rollback"
  LOCK_DIR="$SYNC_ROOT/.sync.lock"
  mkdir "$LOCK_DIR" 2>/dev/null || die "another production database sync is already running"
  LOCK_ACQUIRED=1
  printf '%s\n' "$$" > "$LOCK_DIR/pid"
  chmod 600 "$LOCK_DIR/pid"
}

restore_target() {
  if [ "$REPLACEMENT_STARTED" -ne 1 ]; then
    return
  fi
  if [ "$TARGET_EXISTED" -eq 1 ] && [ -f "$ROLLBACK_ARCHIVE" ]; then
    local_sql "DROP DATABASE IF EXISTS $(sql_identifier "$TARGET_DB");" >/dev/null 2>&1 || true
    local_sql "CREATE DATABASE $(sql_identifier "$TARGET_DB") CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" >/dev/null 2>&1 || true
    if ! gzip -dc "$ROLLBACK_ARCHIVE" | local_import "$TARGET_DB" >/dev/null 2>&1; then
      error "automatic rollback failed; preserve $ROLLBACK_ARCHIVE for manual recovery"
      return
    fi
  else
    local_sql "DROP DATABASE IF EXISTS $(sql_identifier "$TARGET_DB");" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  local exit_code=$?
  set +e
  if [ "$SYNC_SUCCESS" -ne 1 ]; then
    restore_target
    [ -n "$INCOMING_ARCHIVE" ] && rm -f -- "$INCOMING_ARCHIVE"
  fi
  if [ -n "$STAGING_DB" ] && [ -n "$LOCAL_CLIENT_BIN" ]; then
    local_sql "DROP DATABASE IF EXISTS $(sql_identifier "$STAGING_DB");" >/dev/null 2>&1
  fi
  local temp
  for temp in "${TEMP_FILES[@]:-}"; do
    [ -n "$temp" ] && rm -f -- "$temp"
  done
  if [ "$LOCK_ACQUIRED" -eq 1 ]; then
    rm -f -- "$LOCK_DIR/pid"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  return "$exit_code"
}

download_snapshot() {
  INCOMING_ARCHIVE="$SYNC_ROOT/incoming/default-${RUN_ID}.sql.gz"
  local temporary="${INCOMING_ARCHIVE}.tmp.$$"
  TEMP_FILES+=("$temporary")
  if ! (set -o pipefail; run_remote_dump | gzip -9 > "$temporary"); then
    die "remote default database dump failed"
  fi
  gzip -t "$temporary" || die "downloaded archive failed gzip validation"
  local size
  size="$(stat -c '%s' "$temporary" 2>/dev/null || stat -f '%z' "$temporary")"
  [ "$size" -ge "$MIN_DUMP_BYTES" ] || die "downloaded archive is suspiciously small"
  chmod 600 "$temporary"
  mv -f -- "$temporary" "$INCOMING_ARCHIVE"
}

stage_snapshot() {
  STAGING_DB="${TARGET_DB:0:42}__sync_${RUN_ID}"
  STAGING_DB="${STAGING_DB:0:64}"
  validate_db_name "$STAGING_DB"
  local_sql "CREATE DATABASE $(sql_identifier "$STAGING_DB") CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" >/dev/null
  if ! gzip -dc "$INCOMING_ARCHIVE" | local_import "$STAGING_DB" >/dev/null; then
    die "local staging import failed"
  fi
  local table_count
  table_count="$(local_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=$(sql_literal "$STAGING_DB") AND table_type='BASE TABLE';")"
  case "$table_count" in
    ''|*[!0-9]*|0) die "staging database has no imported tables" ;;
  esac
}

backup_target() {
  local exists
  exists="$(local_sql "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=$(sql_literal "$TARGET_DB");")"
  case "$exists" in
    0) TARGET_EXISTED=0; return ;;
    1) TARGET_EXISTED=1 ;;
    *) die "could not determine whether local target exists" ;;
  esac
  ROLLBACK_ARCHIVE="$SYNC_ROOT/rollback/local-default-${RUN_ID}.sql.gz"
  local temporary="${ROLLBACK_ARCHIVE}.tmp.$$"
  TEMP_FILES+=("$temporary")
  if ! (set -o pipefail; local_dump "$TARGET_DB" | gzip -9 > "$temporary"); then
    die "could not back up the local target"
  fi
  gzip -t "$temporary" || die "local rollback archive failed gzip validation"
  chmod 600 "$temporary"
  mv -f -- "$temporary" "$ROLLBACK_ARCHIVE"
}

replace_target() {
  REPLACEMENT_STARTED=1
  local_sql "DROP DATABASE IF EXISTS $(sql_identifier "$TARGET_DB");" >/dev/null || die "could not drop local target"
  local_sql "CREATE DATABASE $(sql_identifier "$TARGET_DB") CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" >/dev/null || die "could not recreate local target"
  if ! gzip -dc "$INCOMING_ARCHIVE" | local_import "$TARGET_DB" >/dev/null; then
    die "replacement import failed; rollback will be attempted"
  fi
}

publish_and_prune() {
  SNAPSHOT_ARCHIVE="$SYNC_ROOT/snapshots/default-${RUN_ID}.sql.gz"
  mv -f -- "$INCOMING_ARCHIVE" "$SNAPSHOT_ARCHIVE"
  chmod 600 "$SNAPSHOT_ARCHIVE"
  INCOMING_ARCHIVE=""
  find "$SYNC_ROOT/snapshots" -type f -name 'default-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
  find "$SYNC_ROOT/rollback" -type f -name 'local-default-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
}

parse_arguments "$@"
validate_configuration

if [ "$APPLY_MODE" -eq 0 ]; then
  printf '[%s] DRY-RUN: production alias default -> local %s at %s:%s; DTF excluded\n' \
    "$SCRIPT_NAME" "$TARGET_DB" "$LOCAL_HOST" "$LOCAL_PORT"
  exit 0
fi

acquire_lock
trap cleanup EXIT
download_snapshot
stage_snapshot
backup_target
replace_target
publish_and_prune
SYNC_SUCCESS=1
printf '[%s] OK: synchronized production alias default to %s; snapshot consistency is InnoDB-consistent and MyISAM best-effort\n' \
  "$SCRIPT_NAME" "$TARGET_DB"
