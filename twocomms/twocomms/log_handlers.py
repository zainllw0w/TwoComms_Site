"""
W3-2 (TD-022/TECH-041): Telegram-алерты для серверных ошибок.

Раньше django.request ERROR писался только в stderr.log «в никуда» —
о 500-ках узнавали от покупателей. Этот handler шлёт краткий алерт
админу в Telegram с жёстким rate-limit (антифлуд при каскадных сбоях).

Дизайн-решения:
- Rate-limit через Django cache: не больше MAX_ALERTS_PER_WINDOW за
  WINDOW_SECONDS; при превышении шлётся один «suppressed N» алерт.
- Отправка в daemon-потоке — logging не должен блокировать request.
- Emergency transport is one direct Bot API request to one target with a
  two-second cap; it intentionally bypasses the normal retrying notifier flow.
- Любая ошибка внутри handler'а глотается (иначе рекурсия
  logging → error → logging).
- Текст обрезается: Telegram лимит 4096, нам хватает 1000.
"""

import logging
import re
import sys
import threading

import requests

WINDOW_SECONDS = 600
MAX_ALERTS_PER_WINDOW = 5
# The alert is deliberately best-effort: requests must not wait for Telegram,
# and a direct stderr line remains available when the transport is unavailable.
TELEGRAM_ALERT_TIMEOUT_SECONDS = 2.0
EMAIL_RE = re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')
PHONE_RE = re.compile(
    r'(?<![\w])(?:\+?380|0)[\s-]?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)'
)
LONG_NUMBER_RE = re.compile(r'(?<!\d)\d{12,19}(?!\d)')
WEBHOOK_VERIFY_TOKEN_RE = re.compile(
    r'(?i)([?&]hub\.verify_token=)[^&\s"\']+'
)


def redact_pii(text):
    """Mask common PII shapes before they reach persistent logs."""
    if not text:
        return text
    text = EMAIL_RE.sub('[email]', str(text))
    text = PHONE_RE.sub('[phone]', text)
    text = LONG_NUMBER_RE.sub('[number]', text)
    text = WEBHOOK_VERIFY_TOKEN_RE.sub(r'\1[redacted]', text)
    return text


class PIIRedactionFilter(logging.Filter):
    """Redact email/phone/long numeric identifiers from log records."""

    def filter(self, record):
        try:
            record.msg = redact_pii(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


class TelegramAlertHandler(logging.Handler):
    """Send ERROR+ records through an independent, bounded emergency channel."""

    _recursion_state = threading.local()

    def emit(self, record):
        if getattr(self._recursion_state, 'active', False):
            return
        self._recursion_state.active = True
        try:
            self._emit_inner(record)
        except Exception:
            # Никогда не даём handler'у уронить логирование.
            pass
        finally:
            self._recursion_state.active = False

    def _emit_inner(self, record):
        from django.core.cache import cache

        # --- rate limit ---
        key = 'tg_error_alert:window'
        try:
            count = cache.get(key, 0)
            if count >= MAX_ALERTS_PER_WINDOW:
                # Один раз за окно сообщаем о подавлении.
                if count == MAX_ALERTS_PER_WINDOW:
                    cache.set(key, count + 1, WINDOW_SECONDS)
                    self._send_async(
                        '\u26a0\ufe0f Error alerts rate-limited: '
                        'больше {}/10 мин. Смотри stderr.log.'.format(MAX_ALERTS_PER_WINDOW)
                    )
                return
            cache.set(key, count + 1, WINDOW_SECONDS)
        except Exception:
            # Кэш недоступен → шлём без лимита (лучше алерт, чем тишина).
            pass

        message = self.format(record)
        if len(message) > 1000:
            message = message[:1000] + '\u2026'
        incident = getattr(record, 'incident_code', None)
        prefix = '\U0001f6a8 SERVER ERROR'
        if incident:
            prefix += f' [{incident}]'
        self._send_async(f'{prefix}\n{message}')

    @staticmethod
    def _write_fallback(text, reason):
        """Write a bounded emergency trace without going through logging."""
        try:
            sys.stderr.write(
                'Telegram alert fallback ({0}): {1}\n'.format(reason, text[:1000])
            )
            sys.stderr.flush()
        except Exception:
            pass

    @classmethod
    def _send_async(cls, text):
        state = {'success': False, 'fallback': False}
        state_lock = threading.Lock()
        completed = threading.Event()

        def fallback(reason):
            with state_lock:
                if state['success'] or state['fallback']:
                    return
                state['fallback'] = True
            cls._write_fallback(text, reason)

        def _worker():
            cls._recursion_state.active = True
            try:
                if cls._send_emergency_alert(text):
                    with state_lock:
                        state['success'] = True
                else:
                    fallback('failed')
            except Exception:
                fallback('exception')
            finally:
                completed.set()
                cls._recursion_state.active = False

        def _deadline_watcher():
            if not completed.wait(TELEGRAM_ALERT_TIMEOUT_SECONDS):
                fallback('timeout')

        try:
            threading.Thread(target=_worker, daemon=True).start()
            threading.Thread(target=_deadline_watcher, daemon=True).start()
        except Exception:
            fallback('thread_start')

    @staticmethod
    def _send_emergency_alert(text):
        """Send one bounded Bot API request without entering the normal notifier flow."""
        from orders.telegram_notifications import TelegramNotifier

        notifier = TelegramNotifier()
        if not notifier.is_configured():
            return False
        targets = notifier._resolve_targets(admin=True)
        if not targets:
            return False

        response = requests.post(
            f'https://api.telegram.org/bot{notifier.bot_token}/sendMessage',
            data={'chat_id': targets[0], 'text': text},
            timeout=TELEGRAM_ALERT_TIMEOUT_SECONDS,
        )
        return bool(response.ok)
