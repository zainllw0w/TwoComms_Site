#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS DJANGO61 DURABLE TASKS"
END_MARKER="# END TWOCOMMS DJANGO61 DURABLE TASKS"

usage() { echo "Usage: $0 --check|--install" >&2; exit 64; }
die() { echo "[django61-task-cron] ERROR: $*" >&2; exit 66; }

[ "$#" -eq 1 ] || usage
case "$1" in --check|--install) mode="$1" ;; *) usage ;; esac

# Do not silently fall back to a host/Python/SQLite layout. The caller must
# provide the CloudLinux-bound project root and its selected virtualenv.
: "${TWC_DJANGO_ROOT:?TWC_DJANGO_ROOT is required}"
: "${TWC_PYTHON:?TWC_PYTHON is required}"
DJANGO_ROOT="$TWC_DJANGO_ROOT"
PYTHON_BIN="$TWC_PYTHON"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"
FLOCK_BIN="${TWC_FLOCK_BIN:-/usr/bin/flock}"
TIMEOUT_BIN="${TWC_TIMEOUT_BIN:-/usr/bin/timeout}"

[ -d "$DJANGO_ROOT" ] || die "Django root does not exist: $DJANGO_ROOT"
[ -f "$DJANGO_ROOT/manage.py" ] || die "manage.py does not exist under Django root"
[ -x "$PYTHON_BIN" ] || die "Python is not executable: $PYTHON_BIN"
[ -x "$FLOCK_BIN" ] || die "flock is not executable: $FLOCK_BIN"
[ -x "$TIMEOUT_BIN" ] || die "timeout is not executable: $TIMEOUT_BIN"
command -v "$CRONTAB_BIN" >/dev/null 2>&1 || die "crontab command is unavailable: $CRONTAB_BIN"

shell_quote() {
  printf '%q' "$1"
}

root_q="$(shell_quote "$DJANGO_ROOT")"
python_q="$(shell_quote "$PYTHON_BIN")"
manage_q="$(shell_quote "$DJANGO_ROOT/manage.py")"
lock_q="$(shell_quote "$DJANGO_ROOT/tmp/django61_durable_tasks.lock")"
log_q="$(shell_quote "$DJANGO_ROOT/logs/django61_durable_tasks_cron.log")"
flock_q="$(shell_quote "$FLOCK_BIN")"
timeout_q="$(shell_quote "$TIMEOUT_BIN")"

cron_line="* * * * * cd $root_q && $flock_q -n $lock_q $timeout_q --signal=TERM 240 $python_q $manage_q run_durable_tasks --limit 25 --lease-seconds 60 --worker-id=cron-no-send >> $log_q 2>&1"

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-django61-task-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l >"$current" 2>"$read_error"; then
  if grep -qi "no crontab" "$read_error"; then
    : >"$current"
  else
    die "unable to read crontab"
  fi
fi

printf '%s\n%s\n%s\n' "$BEGIN_MARKER" "$cron_line" "$END_MARKER" >"$expected"
begin_count="$(grep -Fxc "$BEGIN_MARKER" "$current" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$current" || true)"
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || {
  die "malformed or duplicate managed block"
}

if [ "$mode" = "--check" ]; then
  [ "$begin_count" -eq 1 ] || {
    echo "[django61-task-cron] DRIFT: managed block is missing" >&2
    exit 1
  }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" \
    '$0 == begin { inside = 1 } inside { print } $0 == end { exit }' \
    "$current" >"$candidate"
  cmp -s "$candidate" "$expected" || {
    echo "[django61-task-cron] DRIFT: managed block differs" >&2
    exit 1
  }
  echo "[django61-task-cron] OK: managed block matches"
  exit 0
fi

mkdir -p "$DJANGO_ROOT/tmp" "$DJANGO_ROOT/logs"
: >"$candidate"
inserted=0
skip_managed=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$skip_managed" -eq 1 ]; then
    [ "$line" = "$END_MARKER" ] && skip_managed=0
    continue
  fi
  if [ "$line" = "$BEGIN_MARKER" ]; then
    cat "$expected" >>"$candidate"
    inserted=1
    skip_managed=1
    continue
  fi
  printf '%s\n' "$line" >>"$candidate"
done <"$current"

if [ "$inserted" -eq 0 ]; then cat "$expected" >>"$candidate"; fi
if cmp -s "$candidate" "$current"; then
  echo "[django61-task-cron] OK: managed block already installed"
  exit 0
fi
"$CRONTAB_BIN" "$candidate"
echo "[django61-task-cron] OK: managed block installed; unrelated entries preserved"
