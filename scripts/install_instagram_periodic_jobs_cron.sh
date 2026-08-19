#!/usr/bin/env bash

set -euo pipefail
umask 077

BEGIN_MARKER="# BEGIN TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
END_MARKER="# END TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
BEGIN_PREFIX="# BEGIN TWOCOMMS INSTAGRAM PERIODIC JOBS"

DJANGO_ROOT="${TWC_DJANGO_ROOT:-/home/qlknpodo/TWC/TwoComms_Site/twocomms}"
PYTHON_BIN="${TWC_PYTHON:-/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python}"
CRONTAB_BIN="${TWC_CRONTAB_BIN:-crontab}"
FLOCK_BIN="${TWC_FLOCK_BIN:-/usr/bin/flock}"
TIMEOUT_BIN="${TWC_TIMEOUT_BIN:-/usr/bin/timeout}"
CMP_BIN="${TWC_CMP_BIN:-/usr/bin/cmp}"
FIND_BIN="${TWC_FIND_BIN:-/usr/bin/find}"
PRODUCTION_ENV_PREFIX="DJANGO_ENV=production DJANGO_SETTINGS_MODULE=twocomms.production_settings"
CALL_MARKER="$DJANGO_ROOT/tmp/call_auto_analysis.enabled"

usage() {
  echo "Usage: $0 --check|--install" >&2
  exit 64
}

[ "$#" -eq 1 ] || usage
case "$1" in
  --check|--install) mode="$1" ;;
  *) usage ;;
esac

contract_error() {
  echo "[instagram-periodic-cron] ERROR: $*" >&2
  exit 65
}

config_error() {
  echo "[instagram-periodic-cron] ERROR: $*" >&2
  exit 66
}

validate_path() {
  local label="$1"
  local value="$2"
  case "$value" in
    /*) ;;
    *) config_error "$label must be an absolute path" ;;
  esac
  case "$value" in
    *[!A-Za-z0-9_./-]*) config_error "$label contains unsafe characters" ;;
  esac
  [ "$value" != "/" ] || config_error "$label must not be the filesystem root"
}

validate_path "Django root" "$DJANGO_ROOT"
validate_path "Python executable" "$PYTHON_BIN"
validate_path "flock executable" "$FLOCK_BIN"
validate_path "timeout executable" "$TIMEOUT_BIN"
validate_path "cmp executable" "$CMP_BIN"
validate_path "find executable" "$FIND_BIN"
[ -d "$DJANGO_ROOT" ] || config_error "Django root does not exist: $DJANGO_ROOT"
[ -x "$PYTHON_BIN" ] || config_error "Python is not executable: $PYTHON_BIN"
[ -x "$FLOCK_BIN" ] || config_error "flock is required: $FLOCK_BIN"
[ -x "$TIMEOUT_BIN" ] || config_error "timeout is required: $TIMEOUT_BIN"
[ -x "$CMP_BIN" ] || config_error "cmp is required: $CMP_BIN"
[ -x "$FIND_BIN" ] || config_error "find is required: $FIND_BIN"
command -v "$CRONTAB_BIN" >/dev/null 2>&1 || config_error "crontab command is unavailable"

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/twocomms-instagram-periodic-cron.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM
current="$tmp_dir/current"
read_error="$tmp_dir/read_error"
expected="$tmp_dir/expected"
candidate="$tmp_dir/candidate"

if ! "$CRONTAB_BIN" -l >"$current" 2>"$read_error"; then
  if grep -qi "no crontab" "$read_error"; then
    : >"$current"
  else
    echo "[instagram-periodic-cron] ERROR: unable to read crontab" >&2
    cat "$read_error" >&2
    exit 69
  fi
fi

cat >"$expected" <<EOF
$BEGIN_MARKER
# codex:order-telegram-reconcile
*/2 * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/order_telegram_reconcile.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 90s $PYTHON_BIN manage.py reconcile_order_telegram_notifications --max-age-hours 168 --min-age-seconds 60 --limit 50 >> $DJANGO_ROOT/logs/order_telegram_reconcile.log 2>&1
# codex:ig-checkout-reconcile
*/2 * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/ig_checkout_reconcile.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 90s $PYTHON_BIN manage.py reconcile_ig_checkout --limit 100 >> $DJANGO_ROOT/logs/ig_checkout_reconcile.log 2>&1
# codex:ig-order-fulfillment
*/2 * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/ig_order_fulfillment.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 90s $PYTHON_BIN manage.py reconcile_ig_order_fulfillment --limit 100 >> $DJANGO_ROOT/logs/ig_order_fulfillment.log 2>&1
# codex:ig-deal-payments
*/4 * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/poll_ig_deal_payments.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 180s $PYTHON_BIN manage.py poll_ig_deal_payments --limit 50 >> $DJANGO_ROOT/logs/poll_ig_deal_payments.log 2>&1
# codex:call-auto-analysis
*/5 * * * * if [ -f "$CALL_MARKER" ] && [ ! -L "$CALL_MARKER" ] && [ "\$("$FIND_BIN" "$CALL_MARKER" -prune -type f -perm 600 -print 2>/dev/null)" = "$CALL_MARKER" ] && { echo call-auto-analysis-enabled-v1 | "$CMP_BIN" -s - "$CALL_MARKER"; }; then cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/run_call_ai_analyses.lock /bin/sh -c 'if [ -f "$CALL_MARKER" ] && [ ! -L "$CALL_MARKER" ] && [ "\$("$FIND_BIN" "$CALL_MARKER" -prune -type f -perm 600 -print 2>/dev/null)" = "$CALL_MARKER" ] && { echo call-auto-analysis-enabled-v1 | "$CMP_BIN" -s - "$CALL_MARKER"; }; then exec $TIMEOUT_BIN --signal=TERM --kill-after=15s 240s $PYTHON_BIN manage.py run_call_ai_analyses --limit 1; fi' >> $DJANGO_ROOT/logs/run_call_ai_analyses.log 2>&1; fi
# codex:ig-gemini-metadata-health
0 * * * * cd $DJANGO_ROOT && $PRODUCTION_ENV_PREFIX $FLOCK_BIN -n -E 75 $DJANGO_ROOT/tmp/check_ig_gemini_metadata_health.lock $TIMEOUT_BIN --signal=TERM --kill-after=15s 90s $PYTHON_BIN manage.py check_ig_gemini_metadata_health >> $DJANGO_ROOT/logs/check_ig_gemini_metadata_health.log 2>&1
$END_MARKER
EOF

begin_count="$(grep -Fxc "$BEGIN_MARKER" "$current" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$current" || true)"
[ "$begin_count" -eq "$end_count" ] && [ "$begin_count" -le 1 ] || {
  contract_error "malformed or duplicate managed block"
}

unsupported_markers="$(awk -v prefix="$BEGIN_PREFIX" -v current="$BEGIN_MARKER" '
  index($0, prefix) == 1 && $0 != current { count++ }
  END { print count + 0 }
' "$current")"
[ "$unsupported_markers" -eq 0 ] || contract_error "unsupported managed block version"

if [ "$begin_count" -eq 1 ]; then
  begin_line="$(grep -Fnx "$BEGIN_MARKER" "$current" | cut -d: -f1)"
  end_line="$(grep -Fnx "$END_MARKER" "$current" | cut -d: -f1)"
  [ "$begin_line" -lt "$end_line" ] || contract_error "managed block markers are out of order"
fi

legacy_kind=""
owner_kind=""
is_owner_line() {
  local line="$1"
  owner_kind=""
  case "$line" in
    \#*|"") return 1 ;;
    *"manage.py reconcile_order_telegram_notifications"*) owner_kind="order" ;;
    *"manage.py reconcile_ig_checkout"*) owner_kind="checkout" ;;
    *"manage.py reconcile_ig_order_fulfillment"*) owner_kind="fulfillment" ;;
    *"manage.py poll_ig_deal_payments"*) owner_kind="payments" ;;
    *"manage.py run_call_ai_analyses"*) owner_kind="call_analysis" ;;
    *"manage.py check_ig_gemini_metadata_health"*) owner_kind="gemini_metadata" ;;
    *) return 1 ;;
  esac
  return 0
}

is_legacy_job_line() {
  local line="$1"
  legacy_kind=""
  case "$line" in
    "*/2 * * * * "*"$DJANGO_ROOT"*"manage.py reconcile_order_telegram_notifications"*) legacy_kind="order" ;;
    "*/2 * * * * "*"$DJANGO_ROOT"*"manage.py reconcile_ig_checkout"*) legacy_kind="checkout" ;;
    "*/2 * * * * "*"$DJANGO_ROOT"*"manage.py reconcile_ig_order_fulfillment"*) legacy_kind="fulfillment" ;;
    "*/4 * * * * "*"$DJANGO_ROOT"*"manage.py poll_ig_deal_payments"*) legacy_kind="payments" ;;
    "*/5 * * * * "*"$DJANGO_ROOT"*"manage.py run_call_ai_analyses --limit 1 >> $DJANGO_ROOT/logs/run_call_ai_analyses.log 2>&1") legacy_kind="call_analysis" ;;
    "0 * * * * "*"$DJANGO_ROOT"*"manage.py check_ig_gemini_metadata_health >> $DJANGO_ROOT/logs/check_ig_gemini_metadata_health.log 2>&1") legacy_kind="gemini_metadata" ;;
    *) return 1 ;;
  esac
  return 0
}

legacy_order_count=0
legacy_checkout_count=0
legacy_fulfillment_count=0
legacy_payments_count=0
legacy_call_analysis_count=0
legacy_gemini_metadata_count=0
inside_managed=0
while IFS= read -r line || [ -n "$line" ]; do
  if [ "$inside_managed" -eq 1 ]; then
    [ "$line" = "$END_MARKER" ] && inside_managed=0
    continue
  fi
  if [ "$line" = "$BEGIN_MARKER" ]; then
    inside_managed=1
    continue
  fi
  if is_owner_line "$line"; then
    observed_kind="$owner_kind"
    is_legacy_job_line "$line" || contract_error "unsupported loose $observed_kind owner"
    case "$legacy_kind" in
      order) legacy_order_count=$((legacy_order_count + 1)); [ "$legacy_order_count" -eq 1 ] || contract_error "duplicate order reconcile owner" ;;
      checkout) legacy_checkout_count=$((legacy_checkout_count + 1)); [ "$legacy_checkout_count" -eq 1 ] || contract_error "duplicate checkout reconcile owner" ;;
      fulfillment) legacy_fulfillment_count=$((legacy_fulfillment_count + 1)); [ "$legacy_fulfillment_count" -eq 1 ] || contract_error "duplicate fulfillment owner" ;;
      payments) legacy_payments_count=$((legacy_payments_count + 1)); [ "$legacy_payments_count" -eq 1 ] || contract_error "duplicate payment poll owner" ;;
      call_analysis) legacy_call_analysis_count=$((legacy_call_analysis_count + 1)); [ "$legacy_call_analysis_count" -eq 1 ] || contract_error "duplicate call auto-analysis owner" ;;
      gemini_metadata) legacy_gemini_metadata_count=$((legacy_gemini_metadata_count + 1)); [ "$legacy_gemini_metadata_count" -eq 1 ] || contract_error "duplicate Gemini metadata owner" ;;
    esac
  fi
done <"$current"

outside_owner_count=$((legacy_order_count + legacy_checkout_count + legacy_fulfillment_count + legacy_payments_count + legacy_call_analysis_count + legacy_gemini_metadata_count))
if [ "$begin_count" -eq 1 ] && [ "$outside_owner_count" -ne 0 ]; then
  contract_error "managed block coexists with a loose periodic owner"
fi

if [ "$mode" = "--check" ]; then
  [ "$begin_count" -eq 1 ] || {
    echo "[instagram-periodic-cron] DRIFT: managed block is missing" >&2
    exit 1
  }
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { inside = 1 }
    inside { print }
    $0 == end { exit }
  ' "$current" >"$candidate"
  "$CMP_BIN" -s "$candidate" "$expected" || {
    echo "[instagram-periodic-cron] DRIFT: managed block differs" >&2
    exit 1
  }
  echo "[instagram-periodic-cron] OK: managed block matches"
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
  if [ "$begin_count" -eq 0 ] && is_legacy_job_line "$line"; then
    continue
  fi
  if [ "$begin_count" -eq 0 ]; then
    case "$line" in
      "# codex:order-telegram-reconcile"|"# codex:ig-checkout-reconcile"|"# codex:ig-order-fulfillment"|"# codex:ig-deal-payments"|"# codex:call-auto-analysis"|"# codex:binotel-call-ai"|"# codex:ig-gemini-metadata-health") continue ;;
    esac
  fi
  printf '%s\n' "$line" >>"$candidate"
done <"$current"

[ "$skip_managed" -eq 0 ] || contract_error "managed block did not terminate"
if [ "$inserted" -eq 0 ]; then
  cat "$expected" >>"$candidate"
fi

if "$CMP_BIN" -s "$candidate" "$current"; then
  echo "[instagram-periodic-cron] OK: managed block already installed"
  exit 0
fi

"$CRONTAB_BIN" "$candidate"
echo "[instagram-periodic-cron] OK: managed block installed; unrelated entries preserved"
