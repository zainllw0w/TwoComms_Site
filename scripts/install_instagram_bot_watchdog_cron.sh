#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS INSTAGRAM BOT WATCHDOG"
END_MARKER="# END TWOCOMMS INSTAGRAM BOT WATCHDOG"
LEGACY_MARKER="# codex:instagram-bot-watchdog"

PROJECT_ROOT="${TWC_PROJECT_ROOT:-/home/qlknpodo/TWC/TwoComms_Site}"
DJANGO_ROOT="${TWC_DJANGO_ROOT:-$PROJECT_ROOT/twocomms}"
PYTHON_BIN="${TWC_PYTHON:-/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"
FLOCK_BIN="${TWC_FLOCK_BIN:-/usr/bin/flock}"
TIMEOUT_BIN="${TWC_TIMEOUT_BIN:-/usr/bin/timeout}"

usage() { echo "Usage: $0 --check|--install" >&2; exit 64; }
[ "$#" -eq 1 ] || usage
case "$1" in --check|--install) mode="$1" ;; *) usage ;; esac

[ -d "$DJANGO_ROOT" ] || { echo "[instagram-watchdog-cron] ERROR: Django root does not exist: $DJANGO_ROOT" >&2; exit 66; }
[ -x "$PYTHON_BIN" ] || { echo "[instagram-watchdog-cron] ERROR: Python is not executable: $PYTHON_BIN" >&2; exit 66; }
[ -x "$FLOCK_BIN" ] || { echo "[instagram-watchdog-cron] ERROR: flock is required: $FLOCK_BIN" >&2; exit 66; }
[ -x "$TIMEOUT_BIN" ] || { echo "[instagram-watchdog-cron] ERROR: timeout is required: $TIMEOUT_BIN" >&2; exit 66; }

cron_line="* * * * * cd $DJANGO_ROOT && $FLOCK_BIN -n $DJANGO_ROOT/tmp/ig_bot_watchdog.lock $TIMEOUT_BIN --signal=TERM 50s $PYTHON_BIN manage.py run_instagram_bot --ensure >> $DJANGO_ROOT/tmp/ig_bot_cron.log 2>&1"
legacy_line="* * * * * cd $DJANGO_ROOT && $PYTHON_BIN manage.py run_instagram_bot --ensure >> $DJANGO_ROOT/tmp/ig_bot_cron.log 2>&1"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-ig-watchdog-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l > "$current" 2> "$read_error"; then
  if grep -qi "no crontab" "$read_error"; then : > "$current"; else
    echo "[instagram-watchdog-cron] ERROR: unable to read crontab" >&2
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
legacy_marker_count="$(grep -Fxc "$LEGACY_MARKER" "$current" || true)"
legacy_line_count="$(grep -Fxc "$legacy_line" "$current" || true)"
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || {
  echo "[instagram-watchdog-cron] ERROR: malformed or duplicate managed marker block" >&2
  exit 65
}
[ "$legacy_line_count" -le 1 ] || {
  echo "[instagram-watchdog-cron] ERROR: duplicate legacy watchdog lines" >&2
  exit 65
}
if [ "$begin_count" -eq 1 ] && [ "$legacy_marker_count" -ne 1 ]; then
  echo "[instagram-watchdog-cron] ERROR: managed block must contain exactly one job marker" >&2
  exit 65
fi
if [ "$begin_count" -eq 0 ] && [ "$legacy_marker_count" -gt 1 ]; then
  echo "[instagram-watchdog-cron] ERROR: duplicate legacy job markers" >&2
  exit 65
fi

if [ "$mode" = "--check" ]; then
  [ "$begin_count" -eq 1 ] || {
    echo "[instagram-watchdog-cron] DRIFT: managed block is missing" >&2
    exit 1
  }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '$0 == begin { inside = 1 } inside { print } $0 == end { exit }' "$current" > "$candidate"
  cmp -s "$candidate" "$expected" || {
    echo "[instagram-watchdog-cron] DRIFT: managed block differs from repository configuration" >&2
    exit 1
  }
  echo "[instagram-watchdog-cron] OK: managed block matches"
  exit 0
fi

mkdir -p "$DJANGO_ROOT/tmp"
: > "$candidate"
inserted=0
skip_managed=0
skip_legacy_command=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$skip_legacy_command" -eq 1 ]; then skip_legacy_command=0; continue; fi
  if [ "$skip_managed" -eq 1 ]; then [ "$line" = "$END_MARKER" ] && skip_managed=0; continue; fi
  if [ "$line" = "$BEGIN_MARKER" ]; then
    cat "$expected" >> "$candidate"
    inserted=1
    skip_managed=1
    continue
  fi
  if [ "$begin_count" -eq 0 ] && [ "$line" = "$legacy_line" ]; then
    cat "$expected" >> "$candidate"
    inserted=1
    continue
  fi
  printf '%s\n' "$line" >> "$candidate"
done < "$current"

if [ "$inserted" -eq 0 ]; then cat "$expected" >> "$candidate"; fi
if cmp -s "$candidate" "$current"; then
  echo "[instagram-watchdog-cron] OK: managed block already installed"
  exit 0
fi
"$CRONTAB_BIN" "$candidate"
echo "[instagram-watchdog-cron] OK: managed block installed; unrelated entries preserved"
