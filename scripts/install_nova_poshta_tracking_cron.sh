#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS NOVA POSHTA TRACKING"
END_MARKER="# END TWOCOMMS NOVA POSHTA TRACKING"
LEGACY_MARKER="# codex:nova-poshta-tracking"

PROJECT_ROOT="${TWC_PROJECT_ROOT:-/home/qlknpodo/TWC/TwoComms_Site}"
DJANGO_ROOT="${TWC_DJANGO_ROOT:-$PROJECT_ROOT/twocomms}"
PYTHON_BIN="${TWC_PYTHON:-/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"

usage() { echo "Usage: $0 --check|--install" >&2; exit 64; }
[ "$#" -eq 1 ] || usage
case "$1" in --check|--install) mode="$1" ;; *) usage ;; esac

[ -d "$DJANGO_ROOT" ] || { echo "[nova-poshta-cron] ERROR: Django root does not exist: $DJANGO_ROOT" >&2; exit 66; }
[ -x "$PYTHON_BIN" ] || { echo "[nova-poshta-cron] ERROR: Python is not executable: $PYTHON_BIN" >&2; exit 66; }

cron_line="*/5 * * * * cd $DJANGO_ROOT && /usr/bin/flock -n $DJANGO_ROOT/tmp/nova_poshta_tracking.lock /usr/bin/nice -n 10 $PYTHON_BIN manage.py update_tracking_statuses >> $DJANGO_ROOT/logs/nova_poshta_cron.log 2>&1"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-np-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l > "$current" 2> "$read_error"; then
  if grep -qi "no crontab" "$read_error"; then : > "$current"; else
    echo "[nova-poshta-cron] ERROR: unable to read crontab" >&2
    cat "$read_error" >&2
    exit 69
  fi
fi

cat > "$expected" <<EOF
$BEGIN_MARKER
$LEGACY_MARKER
$cron_line
$END_MARKER
EOF

begin_count="$(grep -Fxc "$BEGIN_MARKER" "$current" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$current" || true)"
legacy_count="$(grep -Fxc "$LEGACY_MARKER" "$current" || true)"
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || { echo "[nova-poshta-cron] ERROR: malformed or duplicate managed marker block" >&2; exit 65; }
if [ "$begin_count" -eq 1 ] && [ "$legacy_count" -ne 1 ]; then
  echo "[nova-poshta-cron] ERROR: managed block must contain exactly one job marker" >&2
  exit 65
fi
if [ "$begin_count" -eq 0 ] && [ "$legacy_count" -gt 1 ]; then
  echo "[nova-poshta-cron] ERROR: duplicate legacy job markers" >&2
  exit 65
fi

if [ "$mode" = "--check" ]; then
  [ "$begin_count" -eq 1 ] || { echo "[nova-poshta-cron] DRIFT: managed block is missing" >&2; exit 1; }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '$0 == begin { inside = 1 } inside { print } $0 == end { exit }' "$current" > "$candidate"
  cmp -s "$candidate" "$expected" || { echo "[nova-poshta-cron] DRIFT: managed block differs from repository configuration" >&2; exit 1; }
  echo "[nova-poshta-cron] OK: managed block matches"
  exit 0
fi

mkdir -p "$DJANGO_ROOT/tmp" "$DJANGO_ROOT/logs"
if [ "$begin_count" -eq 0 ] && [ "$legacy_count" -eq 1 ]; then
  legacy_command="$(awk -v marker="$LEGACY_MARKER" '$0 == marker { getline; print; exit }' "$current")"
  [ "$legacy_command" = "$cron_line" ] || { echo "[nova-poshta-cron] ERROR: legacy marker is followed by an unknown command" >&2; exit 65; }
fi

: > "$candidate"
inserted=0
skip_managed=0
skip_legacy_command=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$skip_legacy_command" -eq 1 ]; then skip_legacy_command=0; continue; fi
  if [ "$skip_managed" -eq 1 ]; then [ "$line" = "$END_MARKER" ] && skip_managed=0; continue; fi
  if [ "$line" = "$BEGIN_MARKER" ]; then cat "$expected" >> "$candidate"; inserted=1; skip_managed=1; continue; fi
  if [ "$begin_count" -eq 0 ] && [ "$line" = "$LEGACY_MARKER" ]; then cat "$expected" >> "$candidate"; inserted=1; skip_legacy_command=1; continue; fi
  printf '%s\n' "$line" >> "$candidate"
done < "$current"

if [ "$inserted" -eq 0 ]; then cat "$expected" >> "$candidate"; fi
if cmp -s "$candidate" "$current"; then echo "[nova-poshta-cron] OK: managed block already installed"; exit 0; fi
"$CRONTAB_BIN" "$candidate"
echo "[nova-poshta-cron] OK: managed block installed; unrelated entries preserved"
