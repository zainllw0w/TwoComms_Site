"""W0 / IMP-004 — инвариант терминального отказа входящего сообщения.

На проде 26 строк имеют `status=failed, attempts=1, send_state=''`.
Диагностика W0 показала: текущим кодом такая комбинация не производится —
это legacy-кластер 14.06–10.07, когда permanent-ошибка Meta Send помечала
строку failed на первой попытке, а поля `send_state` ещё не существовало.

Чинить нечего. Но инвариант держится только на дисциплине: достаточно
добавить ещё один attempts-агностичный путь, и молчаливая потеря
входящего сообщения вернётся. Этот тест — единственное, что переживёт
следующего агента.
"""
import ast
import re
from pathlib import Path

from django.test import SimpleTestCase

SERVICE = (
    Path(__file__).resolve().parent / "services" / "instagram_bot.py"
)


class FailedStatusInvariantTests(SimpleTestCase):
    """`failed` ⇒ (attempts >= MAX_ATTEMPTS) OR (send_state != '')."""

    def test_max_attempts_is_still_three(self):
        source = SERVICE.read_text(encoding="utf-8")

        self.assertIn(
            "MAX_ATTEMPTS = 3",
            source,
            "если порог изменился, инвариант надо пересмотреть осознанно",
        )

    def test_every_failed_transition_is_attempts_aware_or_sets_send_state(self):
        source = SERVICE.read_text(encoding="utf-8")
        lines = source.splitlines()

        # Нас интересуют только ПЕРЕХОДЫ в failed: присваивание атрибуту и
        # `update(status=...)`. Чтение (`.exclude(status=...FAILED)`,
        # `.filter(...)`) — не переход, поэтому отсекаем по префиксу строки.
        transition_re = re.compile(
            r"(?:^|[^.\w])(?:row|locked|msg)?\.?status\s*=\s*"
            r"(?:InstagramBotMessage\.)?Status\.FAILED|"
            r"status\s*=\s*InstagramBotMessage\.Status\.FAILED\s*,"
        )
        read_re = re.compile(r"\.(?:exclude|filter|get|annotate)\s*\(")
        failed_lines = [
            idx
            for idx, line in enumerate(lines)
            if transition_re.search(line) and not read_re.search(line)
        ]
        self.assertTrue(failed_lines, "не найдено ни одного перехода в failed")

        offenders = []
        for idx in failed_lines:
            # Окно охватывает и условие выше, и присваивания ниже: оба
            # способа удержать инвариант допустимы.
            window = "\n".join(lines[max(0, idx - 6) : idx + 6])
            attempts_aware = "attempts >= MAX_ATTEMPTS" in window
            sets_send_state = re.search(r"send_state\s*=\s*[\"'][a-z]+[\"']", window)
            if not attempts_aware and not sets_send_state:
                offenders.append(f"{SERVICE.name}:{idx + 1}: {lines[idx].strip()}")

        self.assertEqual(
            offenders,
            [],
            "переход в failed без проверки attempts и без непустого send_state "
            "возвращает молчаливую потерю входящего сообщения (F-CORE-010):\n"
            + "\n".join(offenders),
        )

    def test_service_module_still_parses(self):
        """Страховка: тест выше читает файл текстом, значит файл должен быть валиден."""
        ast.parse(SERVICE.read_text(encoding="utf-8"))
