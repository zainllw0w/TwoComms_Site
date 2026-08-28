"""Cost-гарди, які не вимикаються від збою кешу (Э2.3, перша ланка).

Ланцюг, що зупиняв канал продажів повністю від однієї інфраструктурної поломки:

    кеш недоступний
      → _rate_exceeded=False, _match_allowed=True, _repeated_question=0
      → усі cost-гарди вимкнені
      → повторні фото й питання йдуть у Gemini/vision без ліміту
      → квота вигорає швидше звичайного
      → усі chat-ключі в cooldown
      → _defer_for_gemini_cooldown повертає рядки в PENDING
      → інбокс молчить повністю

Кожен дефект окремо помірний. Разом вони дають повну остановку. Тут розривається
перша ланка: при збої кешу гарди переходять на **внутріпроцесний** лічильник, а
не відкриваються навстіж. Це грубіше за спільний кеш (кожен процес рахує своє),
але грубий ліміт незрівнянно краще за відсутність ліміту.

Лічильник обмежений за розміром: він не має стати другим джерелом проблем з
пам'яттю в довгоживучому демоні.
"""
from __future__ import annotations

import threading
import time

from django.core.cache import cache

# Стеля кількості ключів у внутріпроцесному лічильнику. Перевищення чистить
# протухлі записи, і лише потім найстаріші.
MAX_TRACKED_KEYS = 5000


class _InProcessCounter:
    """Обмежений TTL-лічильник на процес, безпечний для потоків демона."""

    def __init__(self, max_keys: int = MAX_TRACKED_KEYS):
        self._lock = threading.Lock()
        self._values: dict = {}
        self._max_keys = max_keys

    def incr(self, key: str, window: int) -> int:
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            count, expires_at = self._values.get(key, (0, 0.0))
            if expires_at <= now:
                count = 0
                expires_at = now + max(1, int(window))
            count += 1
            self._values[key] = (count, expires_at)
            return count

    def get(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            count, expires_at = self._values.get(key, (0, 0.0))
            return count if expires_at > now else 0

    def _evict(self, now: float) -> None:
        if len(self._values) < self._max_keys:
            return
        expired = [key for key, (_c, exp) in self._values.items() if exp <= now]
        for key in expired:
            self._values.pop(key, None)
        if len(self._values) < self._max_keys:
            return
        # Усі записи ще живі: знімаємо найстаріші за строком дії.
        oldest = sorted(self._values.items(), key=lambda item: item[1][1])
        for key, _value in oldest[: max(1, self._max_keys // 10)]:
            self._values.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


_counter = _InProcessCounter()


def reset_local_counters() -> None:
    """Скинути внутріпроцесний стан (використовується тестами)."""
    _counter.clear()


def counted(key: str, window: int) -> tuple[int, bool]:
    """Збільшити лічильник і повернути (значення, чи використано кеш).

    При збої кешу лічильник продовжується локально. Другий елемент дозволяє
    викликаючому шару побачити деградацію, а не вважати цифру спільною.
    """
    try:
        current = cache.get(key) or 0
        cache.set(key, current + 1, window)
        return int(current) + 1, True
    except Exception:
        return _counter.incr(key, window), False


def current_count(key: str) -> tuple[int, bool]:
    try:
        return int(cache.get(key) or 0), True
    except Exception:
        return _counter.get(key), False
