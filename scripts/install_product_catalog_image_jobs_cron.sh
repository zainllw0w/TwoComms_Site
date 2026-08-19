#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS PRODUCT CATALOG IMAGE JOBS"
END_MARKER="# END TWOCOMMS PRODUCT CATALOG IMAGE JOBS"

usage() { echo "Usage: $0 --check|--install" >&2; exit 64; }
die() { echo "[catalog-image-cron] ERROR: $*" >&2; exit 66; }

[ "$#" -eq 1 ] || usage
case "$1" in --check|--install) mode="$1" ;; *) usage ;; esac

# Image execution remains inactive until an operator deliberately runs this
# installer with the CloudLinux-bound production runtime.
: "${TWC_DJANGO_ROOT:?TWC_DJANGO_ROOT is required}"
: "${TWC_PYTHON:?TWC_PYTHON is required}"
DJANGO_ROOT="$TWC_DJANGO_ROOT"
PYTHON_BIN="$TWC_PYTHON"
CLOUDLINUX_PYTHON_WRAPPER="${TWC_CLOUDLINUX_PYTHON_WRAPPER:-/usr/share/l.v.e-manager/utils/python_wrapper}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"
FLOCK_BIN="${TWC_FLOCK_BIN:-/usr/bin/flock}"
TIMEOUT_BIN="${TWC_TIMEOUT_BIN:-/usr/bin/timeout}"
NICE_BIN="${TWC_NICE_BIN:-/usr/bin/nice}"

[ -d "$DJANGO_ROOT" ] || die "Django root does not exist: $DJANGO_ROOT"
[ -f "$DJANGO_ROOT/manage.py" ] || die "manage.py does not exist under Django root"
[ -x "$PYTHON_BIN" ] || die "Python is not executable: $PYTHON_BIN"
[ -f "$CLOUDLINUX_PYTHON_WRAPPER" ] && [ ! -L "$CLOUDLINUX_PYTHON_WRAPPER" ] && [ -x "$CLOUDLINUX_PYTHON_WRAPPER" ] || die "CloudLinux Python wrapper is unavailable"
[ -L "$PYTHON_BIN" ] || die "selected Python is not a CloudLinux-bound symlink"
[ "$(readlink "$PYTHON_BIN")" = "$CLOUDLINUX_PYTHON_WRAPPER" ] || die "selected Python is not bound to the CloudLinux wrapper"
[ -x "$FLOCK_BIN" ] || die "flock is not executable: $FLOCK_BIN"
[ -x "$TIMEOUT_BIN" ] || die "timeout is not executable: $TIMEOUT_BIN"
[ -x "$NICE_BIN" ] || die "nice is not executable: $NICE_BIN"
command -v "$CRONTAB_BIN" >/dev/null 2>&1 || die "crontab command is unavailable: $CRONTAB_BIN"

if ! preflight_output="$(
  (
    cd "$DJANGO_ROOT"
    DJANGO_ENV=production \
    DJANGO_SETTINGS_MODULE=twocomms.production_settings \
    PYTHONPATH="$DJANGO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -c '
import json
import django
django.setup()
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from product_catalog.models import ImageOptimizationJob

connection = connections["default"]
database = connection.settings_dict
if database.get("ENGINE") != "django.db.backends.mysql":
    raise SystemExit("non-mysql backend")
if database.get("CONN_MAX_AGE") != 0:
    raise SystemExit("persistent database connection")
with connection.cursor() as cursor:
    cursor.execute("SELECT VERSION()")
    version = str(cursor.fetchone()[0])
    cursor.execute(
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        [ImageOptimizationJob._meta.db_table],
    )
    engine_row = cursor.fetchone()
    cursor.execute(
        "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        [ImageOptimizationJob._meta.db_table, "lease_token"],
    )
    lease_row = cursor.fetchone()
    cursor.execute(
        "SELECT INDEX_NAME, NON_UNIQUE, "
        "GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) "
        "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = %s AND INDEX_NAME IN (%s, %s) "
        "GROUP BY INDEX_NAME, NON_UNIQUE",
        [
            ImageOptimizationJob._meta.db_table,
            "pc_job_status_upd_9f3d_idx",
            "pc_job_status_crt_9f3d_idx",
        ],
    )
    queue_indexes = {
        str(name): (int(non_unique), str(columns))
        for name, non_unique, columns in cursor.fetchall()
    }
applied = MigrationRecorder(connection).applied_migrations()
ready = (
    ("product_catalog", "0015_reconcile_image_job_schema") in applied
    and engine_row is not None
    and str(engine_row[0]).upper() == "INNODB"
    and lease_row == ("varchar", 32, "NO")
    and queue_indexes == {
        "pc_job_status_upd_9f3d_idx": (1, "status,updated_at"),
        "pc_job_status_crt_9f3d_idx": (1, "status,created_at"),
    }
)
print(json.dumps({
    "conn_max_age": database.get("CONN_MAX_AGE"),
    "engine": database.get("ENGINE"),
    "image_job_schema_ready": ready,
    "mariadb": "mariadb" in version.lower(),
}, separators=(",", ":"), sort_keys=True))
'
  ) 2>/dev/null
)"; then
  die "CloudLinux production database preflight failed"
fi
case "$preflight_output" in *'"engine":"django.db.backends.mysql"'*) ;; *) die "production preflight did not select Django MySQL" ;; esac
case "$preflight_output" in *'"conn_max_age":0'*) ;; *) die "production preflight requires CONN_MAX_AGE=0" ;; esac
case "$preflight_output" in *'"mariadb":true'*) ;; *) die "production preflight did not confirm MariaDB" ;; esac
case "$preflight_output" in *'"image_job_schema_ready":true'*) ;; *) die "production preflight requires product_catalog.0015 and an InnoDB image-job table" ;; esac

shell_quote() { printf '%q' "$1"; }
root_q="$(shell_quote "$DJANGO_ROOT")"
python_q="$(shell_quote "$PYTHON_BIN")"
manage_q="$(shell_quote "$DJANGO_ROOT/manage.py")"
lock_q="$(shell_quote "$DJANGO_ROOT/tmp/product_catalog_image_jobs.lock")"
log_q="$(shell_quote "$DJANGO_ROOT/logs/product_catalog_image_jobs_cron.log")"
flock_q="$(shell_quote "$FLOCK_BIN")"
timeout_q="$(shell_quote "$TIMEOUT_BIN")"
nice_q="$(shell_quote "$NICE_BIN")"

cron_line="* * * * * cd $root_q && DJANGO_ENV=production DJANGO_SETTINGS_MODULE=twocomms.production_settings exec $flock_q -n $lock_q $timeout_q --signal=TERM --kill-after=30s 1500s $nice_q -n 10 $python_q $manage_q reconcile_image_optimization_jobs --max-jobs 4 --stale-after-seconds 1800 --allow-production >> $log_q 2>&1"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-catalog-image-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l > "$current" 2> "$read_error"; then
  if grep -qi "no crontab" "$read_error"; then : > "$current"; else
    echo "[catalog-image-cron] ERROR: unable to read crontab" >&2
    exit 69
  fi
fi

printf '%s\n%s\n%s\n' "$BEGIN_MARKER" "$cron_line" "$END_MARKER" > "$expected"
begin_count="$(grep -Fxc "$BEGIN_MARKER" "$current" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$current" || true)"
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || {
  die "malformed or duplicate managed block"
}

managed_depth=0
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    "$BEGIN_MARKER") managed_depth=1 ;;
    "$END_MARKER") managed_depth=0 ;;
    *)
      trimmed_line="${line#"${line%%[![:space:]]*}"}"
      if [ "$managed_depth" -eq 0 ] && [[ "$trimmed_line" != \#* ]] && [[ "$line" == *reconcile_image_optimization_jobs* ]]; then
        die "image-job owner exists outside the managed block"
      fi
      ;;
  esac
done < "$current"

if [ "$mode" = "--check" ]; then
  [ "$begin_count" -eq 1 ] || { echo "[catalog-image-cron] DRIFT: managed block is missing" >&2; exit 1; }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '$0 == begin { inside = 1 } inside { print } $0 == end { exit }' "$current" > "$candidate"
  cmp -s "$candidate" "$expected" || { echo "[catalog-image-cron] DRIFT: managed block differs" >&2; exit 1; }
  echo "[catalog-image-cron] OK: managed block matches"
  exit 0
fi

mkdir -p "$DJANGO_ROOT/tmp" "$DJANGO_ROOT/logs"
: > "$candidate"
inserted=0
skip_managed=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$skip_managed" -eq 1 ]; then [ "$line" = "$END_MARKER" ] && skip_managed=0; continue; fi
  if [ "$line" = "$BEGIN_MARKER" ]; then
    cat "$expected" >> "$candidate"
    inserted=1
    skip_managed=1
    continue
  fi
  printf '%s\n' "$line" >> "$candidate"
done < "$current"

if [ "$inserted" -eq 0 ]; then cat "$expected" >> "$candidate"; fi
if cmp -s "$candidate" "$current"; then echo "[catalog-image-cron] OK: managed block already installed"; exit 0; fi
"$CRONTAB_BIN" "$candidate"
echo "[catalog-image-cron] OK: managed block installed; unrelated entries preserved"
