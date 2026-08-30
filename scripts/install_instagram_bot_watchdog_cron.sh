#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS INSTAGRAM BOT WATCHDOG"
END_MARKER="# END TWOCOMMS INSTAGRAM BOT WATCHDOG"
JOB_MARKER="# codex:instagram-bot-watchdog"

PROJECT_ROOT="${TWC_PROJECT_ROOT:-/home/qlknpodo/TWC/TwoComms_Site}"
DJANGO_ROOT="${TWC_DJANGO_ROOT:-$PROJECT_ROOT/twocomms}"
PYTHON_BIN="${TWC_PYTHON:-/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"
FLOCK_BIN="${TWC_FLOCK_BIN:-/usr/bin/flock}"
TIMEOUT_BIN="${TWC_TIMEOUT_BIN:-/usr/bin/timeout}"
SUPERVISOR_SCRIPT="${TWC_IG_SUPERVISOR_SCRIPT:-$PROJECT_ROOT/scripts/instagram_bot_supervisor.py}"
PRODUCTION_ENV_PREFIX="DJANGO_ENV=production DJANGO_SETTINGS_MODULE=twocomms.production_settings"

usage() { echo "Usage: $0 --check|--install|--check-rollback|--rollback" >&2; exit 64; }
[ "$#" -eq 1 ] || usage
case "$1" in --check|--install|--check-rollback|--rollback) mode="$1" ;; *) usage ;; esac

error() {
  echo "[instagram-watchdog-cron] ERROR: $*" >&2
  exit 66
}

validate_path() {
  local label="$1"
  local value="$2"
  case "$value" in /*) ;; *) error "$label must be an absolute path" ;; esac
  case "$value" in *[!A-Za-z0-9_./-]*) error "$label contains unsafe characters" ;; esac
  [ "$value" != "/" ] || error "$label must not be the filesystem root"
}

validate_path "Django root" "$DJANGO_ROOT"
validate_path "Python executable" "$PYTHON_BIN"
validate_path "flock executable" "$FLOCK_BIN"
validate_path "timeout executable" "$TIMEOUT_BIN"
validate_path "supervisor script" "$SUPERVISOR_SCRIPT"
[ -d "$DJANGO_ROOT" ] || error "Django root does not exist: $DJANGO_ROOT"
[ -x "$PYTHON_BIN" ] || error "Python is not executable: $PYTHON_BIN"
[ -x "$FLOCK_BIN" ] || error "flock is required: $FLOCK_BIN"
[ -x "$TIMEOUT_BIN" ] || error "timeout is required: $TIMEOUT_BIN"
[ -f "$SUPERVISOR_SCRIPT" ] || error "supervisor script is missing: $SUPERVISOR_SCRIPT"

# The minute owner imports only Python's standard library. The long-lived
# supervisor, not cron, waits for and attributes every daemon-child exit.
cron_line="* * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/ig_bot_watchdog.lock $TIMEOUT_BIN --signal=TERM --kill-after=5s 20s $PYTHON_BIN $SUPERVISOR_SCRIPT --ensure --root $DJANGO_ROOT --python $PYTHON_BIN >> $DJANGO_ROOT/tmp/ig_bot_supervisor_cron.log 2>&1"
legacy_line="* * * * * cd $DJANGO_ROOT && $PYTHON_BIN manage.py run_instagram_bot --ensure >> $DJANGO_ROOT/tmp/ig_bot_cron.log 2>&1"
legacy_managed_line="* * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/ig_bot_watchdog.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 75s $PYTHON_BIN manage.py run_instagram_bot --ensure >> $DJANGO_ROOT/tmp/ig_bot_cron.log 2>&1"
case "$mode" in
  --rollback|--check-rollback) desired_line="$legacy_managed_line" ;;
  *) desired_line="$cron_line" ;;
esac

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-ig-watchdog-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l >"$current" 2>"$read_error"; then
  if grep -qi "no crontab" "$read_error"; then : >"$current"; else
    echo "[instagram-watchdog-cron] ERROR: unable to read crontab" >&2
    cat "$read_error" >&2
    exit 69
  fi
fi

cat >"$expected" <<EOF
$BEGIN_MARKER
$JOB_MARKER
$desired_line
$END_MARKER
EOF

begin_count="$(grep -Fxc "$BEGIN_MARKER" "$current" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$current" || true)"
job_marker_count="$(grep -Fxc "$JOB_MARKER" "$current" || true)"
[ "$job_marker_count" -le 1 ] || {
  echo "[instagram-watchdog-cron] ERROR: duplicate watchdog job markers" >&2
  exit 65
}
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || {
  echo "[instagram-watchdog-cron] ERROR: malformed or duplicate managed marker block" >&2
  exit 65
}
if [ "$begin_count" -eq 1 ]; then
  begin_line="$(grep -Fnx "$BEGIN_MARKER" "$current" | cut -d: -f1)"
  end_line="$(grep -Fnx "$END_MARKER" "$current" | cut -d: -f1)"
  [ "$begin_line" -lt "$end_line" ] || {
    echo "[instagram-watchdog-cron] ERROR: managed block markers are out of order" >&2
    exit 65
  }
  managed_block="$tmp_dir/managed_block"
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { inside = 1 }
    inside { print }
    $0 == end { exit }
  ' "$current" >"$managed_block"
  block_job_markers="$(grep -Fxc "$JOB_MARKER" "$managed_block" || true)"
  total_job_markers="$(grep -Fxc "$JOB_MARKER" "$current" || true)"
  [ "$block_job_markers" -eq 1 ] && [ "$total_job_markers" -eq 1 ] || {
    echo "[instagram-watchdog-cron] ERROR: watchdog marker must occur once inside managed block" >&2
    exit 65
  }
  managed_owner_count=0
  while IFS= read -r managed_line || [ -n "$managed_line" ]; do
    trimmed="${managed_line#"${managed_line%%[![:space:]]*}"}"
    case "$trimmed" in ""|\#*) continue ;; esac
    if [ "$managed_line" = "$cron_line" ] || [ "$managed_line" = "$legacy_managed_line" ]; then
      managed_owner_count=$((managed_owner_count + 1))
      continue
    fi
    echo "[instagram-watchdog-cron] ERROR: unknown command inside managed block" >&2
    exit 65
  done <"$managed_block"
  [ "$managed_owner_count" -eq 1 ] || {
    echo "[instagram-watchdog-cron] ERROR: managed block requires exactly one watchdog owner" >&2
    exit 65
  }
fi

if [ "$begin_count" -eq 0 ] && [ "$job_marker_count" -eq 1 ]; then
  marker_command="$(awk -v marker="$JOB_MARKER" '$0 == marker { getline; print; exit }' "$current")"
  [ "$marker_command" = "$legacy_line" ] || [ "$marker_command" = "$legacy_managed_line" ] || [ "$marker_command" = "$cron_line" ] || {
    echo "[instagram-watchdog-cron] ERROR: loose watchdog marker has unknown owner" >&2
    exit 65
  }
fi

is_watchdog_owner() {
  local line="$1"
  case "$line" in
    \#*|"") return 1 ;;
    *"instagram_bot_supervisor.py --ensure"*|*"manage.py run_instagram_bot --ensure"*) return 0 ;;
    *) return 1 ;;
  esac
}

is_supported_loose_owner() {
  local line="$1"
  [ "$line" = "$legacy_line" ] || [ "$line" = "$legacy_managed_line" ] || [ "$line" = "$cron_line" ]
}

outside_owner_count=0
unsupported_outside_owner_count=0
inside_managed=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$inside_managed" -eq 1 ]; then
    [ "$line" = "$END_MARKER" ] && inside_managed=0
    continue
  fi
  if [ "$line" = "$BEGIN_MARKER" ]; then inside_managed=1; continue; fi
  if is_watchdog_owner "$line"; then
    outside_owner_count=$((outside_owner_count + 1))
    is_supported_loose_owner "$line" || unsupported_outside_owner_count=$((unsupported_outside_owner_count + 1))
  fi
done <"$current"

[ "$outside_owner_count" -le 1 ] || {
  echo "[instagram-watchdog-cron] ERROR: duplicate watchdog owners" >&2
  exit 65
}
if [ "$begin_count" -eq 1 ] && [ "$outside_owner_count" -ne 0 ]; then
  echo "[instagram-watchdog-cron] ERROR: managed block coexists with a loose watchdog owner" >&2
  exit 65
fi
[ "$unsupported_outside_owner_count" -eq 0 ] || {
  echo "[instagram-watchdog-cron] ERROR: unsupported loose watchdog owner" >&2
  exit 65
}

if [ "$mode" = "--check" ] || [ "$mode" = "--check-rollback" ]; then
  [ "$begin_count" -eq 1 ] || {
    echo "[instagram-watchdog-cron] DRIFT: managed block is missing" >&2
    exit 1
  }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { inside = 1 }
    inside { print }
    $0 == end { exit }
  ' "$current" >"$candidate"
  cmp -s "$candidate" "$expected" || {
    echo "[instagram-watchdog-cron] DRIFT: managed block differs from repository configuration" >&2
    exit 1
  }
  echo "[instagram-watchdog-cron] OK: managed block matches $mode"
  exit 0
fi

mkdir -p "$DJANGO_ROOT/tmp"
: >"$candidate"
inserted=0
skip_managed=0
skip_legacy_command=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$skip_legacy_command" -eq 1 ]; then skip_legacy_command=0; continue; fi
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
  if [ "$begin_count" -eq 0 ] && is_supported_loose_owner "$line"; then
    cat "$expected" >>"$candidate"
    inserted=1
    continue
  fi
  if [ "$begin_count" -eq 0 ] && [ "$line" = "$JOB_MARKER" ]; then
    cat "$expected" >>"$candidate"
    inserted=1
    skip_legacy_command=1
    continue
  fi
  printf '%s\n' "$line" >>"$candidate"
done <"$current"

[ "$skip_managed" -eq 0 ] || {
  echo "[instagram-watchdog-cron] ERROR: managed block did not terminate" >&2
  exit 65
}
[ "$inserted" -eq 1 ] || cat "$expected" >>"$candidate"
if cmp -s "$candidate" "$current"; then
  echo "[instagram-watchdog-cron] OK: managed block already installed"
  exit 0
fi
"$CRONTAB_BIN" "$candidate"
if [ "$mode" = "--rollback" ]; then
  echo "[instagram-watchdog-cron] OK: legacy Django watchdog restored before code rollback"
else
  echo "[instagram-watchdog-cron] OK: stdlib supervisor owner installed; unrelated entries preserved"
fi
