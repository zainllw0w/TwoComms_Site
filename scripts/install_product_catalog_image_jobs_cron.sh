#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS PRODUCT CATALOG IMAGE JOBS"
END_MARKER="# END TWOCOMMS PRODUCT CATALOG IMAGE JOBS"

DJANGO_ROOT="${TWC_DJANGO_ROOT:-/home/qlknpodo/TWC/TwoComms_Site/twocomms}"
PYTHON_BIN="${TWC_PYTHON:-/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"

usage() { echo "Usage: $0 --check|--install" >&2; exit 64; }
[ "$#" -eq 1 ] || usage
case "$1" in --check|--install) mode="$1" ;; *) usage ;; esac

[ -d "$DJANGO_ROOT" ] || { echo "[catalog-image-cron] ERROR: Django root does not exist: $DJANGO_ROOT" >&2; exit 66; }
[ -x "$PYTHON_BIN" ] || { echo "[catalog-image-cron] ERROR: Python is not executable: $PYTHON_BIN" >&2; exit 66; }

cron_line="* * * * * cd $DJANGO_ROOT && /usr/bin/flock -n $DJANGO_ROOT/tmp/product_catalog_image_jobs.lock /usr/bin/nice -n 10 $PYTHON_BIN manage.py reconcile_image_optimization_jobs --max-jobs 4 --stale-after-seconds 1800 >> $DJANGO_ROOT/logs/product_catalog_image_jobs_cron.log 2>&1"
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
  echo "[catalog-image-cron] ERROR: malformed or duplicate managed block" >&2
  exit 65
}

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
