"""ЭА.18 — переход takeover и наблюдение за ним это разные события.

После фактического takeover каждое сообщение менеджера создавало ещё один
`warning`-рядок «менеджер підключився». Внешний алерт дедуплицирован правильно —
он под `if takeover_started`, — а внутренний поток предупреждений содержал
повторы, из-за чего разбор инцидента труднее, а уровень `warning` обесценивается.
"""
from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot


class TakeoverEventTests(TestCase):
    def setUp(self):
        InstagramBotSettings.load()
        self.igsid = "70000000000000001"

    def _manager_message(self, text, *, index):
        instagram_bot._handle_echo(
            self.igsid,
            text,
            mid=f"manager-echo-{index}",
            received_at=timezone.now(),
        )

    def _events(self, *names):
        return list(
            InstagramBotLog.objects.filter(event__in=names)
            .order_by("id")
            .values_list("event", "level")
        )

    def test_five_manager_messages_produce_one_transition_warning(self):
        for index in range(5):
            self._manager_message(f"повідомлення менеджера {index}", index=index)

        events = self._events("takeover_transition", "takeover_observed", "takeover")

        self.assertEqual(
            events,
            [("takeover_transition", "warning")],
            "спостереження не має створювати рядок у консолі на кожне повідомлення",
        )

    def test_observed_messages_really_take_the_observed_branch(self):
        """Без этой проверки предыдущий тест мог пройти по неверной причине.

        Отсутствие консольных рядков одинаково выглядит и когда наблюдение ушло
        в `debug`, и когда переход вообще не применился. Здесь ловится сам факт
        `takeover_observed` в файловом логе.
        """
        self._manager_message("перше", index=0)

        with self.assertLogs("ig_bot", level="DEBUG") as captured:
            self._manager_message("друге", index=1)
            self._manager_message("третє", index=2)

        observed = [
            line for line in captured.output if "takeover_observed" in line
        ]
        self.assertEqual(len(observed), 2, captured.output)
        self.assertTrue(all("level=debug" in line for line in observed))

    def test_the_transition_itself_is_never_lost(self):
        self._manager_message("перше повідомлення менеджера", index=0)

        client = IgClient.objects.get(igsid=self.igsid)
        self.assertTrue(client.manager_takeover)
        self.assertTrue(client.bot_paused)
        self.assertEqual(client.paused_reason, "manager_takeover")
        self.assertEqual(
            self._events("takeover_transition"), [("takeover_transition", "warning")]
        )

    def test_takeover_state_is_set_once_and_idempotently(self):
        self._manager_message("перше", index=0)
        client = IgClient.objects.get(igsid=self.igsid)
        epoch_after_first = int(client.reply_permission_epoch or 0)
        paused_at_after_first = client.paused_at

        for index in range(1, 4):
            self._manager_message(f"ще {index}", index=index)

        client.refresh_from_db()
        self.assertEqual(int(client.reply_permission_epoch or 0), epoch_after_first)
        self.assertEqual(client.paused_at, paused_at_after_first)

    def test_releasing_and_re_enabling_takeover_records_a_new_transition(self):
        self._manager_message("перше", index=0)
        client = IgClient.objects.get(igsid=self.igsid)
        IgClient.objects.filter(pk=client.pk).update(
            manager_takeover=False, bot_paused=False, paused_reason=""
        )

        self._manager_message("менеджер повернувся", index=99)

        self.assertEqual(
            self._events("takeover_transition"),
            [("takeover_transition", "warning"), ("takeover_transition", "warning")],
            "повторне включення takeover — новий перехід, а не спостереження",
        )

    def test_manager_messages_still_land_as_evidence(self):
        """Тихий рівень логу не має права з'їсти сам рядок менеджера."""
        for index in range(3):
            self._manager_message(f"повідомлення {index}", index=index)

        self.assertEqual(
            InstagramBotMessage.objects.filter(
                sender_id=self.igsid, role=InstagramBotMessage.Role.MANAGER
            ).count(),
            3,
        )


class DebugLogLevelTests(TestCase):
    """`debug` пишеться у файловий лог, але не створює рядок консолі."""

    def test_debug_level_does_not_create_a_console_row(self):
        instagram_bot.log("debug", "unit_probe", "деталь")
        self.assertFalse(InstagramBotLog.objects.filter(event="unit_probe").exists())

    def test_warning_level_still_creates_a_console_row(self):
        instagram_bot.log("warning", "unit_probe_warning", "деталь")
        self.assertTrue(
            InstagramBotLog.objects.filter(event="unit_probe_warning").exists()
        )

    def test_unknown_level_falls_back_to_info_and_is_visible(self):
        instagram_bot.log("nonsense", "unit_probe_unknown")
        row = InstagramBotLog.objects.filter(event="unit_probe_unknown").first()
        self.assertIsNotNone(row)
        self.assertEqual(row.level, "info")
