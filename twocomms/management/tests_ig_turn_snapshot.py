"""Э8.5 — один снимок фактов на сборку промпта вместо N+1.

Замер до правки: 29 SQL-запросов на одну сборку `assemble_system_instruction()`,
из них повторных по одной и той же строке — `open_service_case` 4 раза,
`client_has_verified_payment` 3, `client_has_confirmed_purchase` 2, указатель
эпизода 2, граница сброса воронки 4. После — 17.

Тесты закрепляют три вещи, а не только число:

1. текст промпта не изменился (кэш не должен влиять на содержание);
2. сборка промпта ничего не пишет — это и есть основание кэшировать внутри неё;
3. платёжная истина **не** кэшируется на весь ход: ход длится до двух минут, и
   оплату может подтвердить вебхук в другом процессе.
"""
import re
from collections import Counter
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from management.ig_bot_models import (
    IgClient,
    IgDeal,
    IgFunnelResetAudit,
    IgObjection,
)
from management.models import InstagramBotSettings
from management.services import instagram_bot as bot
from management.services import ig_turn_snapshot
from management.services.bot_payment_truth import client_has_verified_payment
from management.services.ig_funnel_reset import latest_reset_after_message_id

# Ограничение сверху, а не точное равенство «17»: новый блок промпта имеет право
# добавить свои запросы. Что здесь ловится — возврат N+1: повторное чтение одного
# и того же факта разными блоками. Если бюджет вырос осознанно — поднимите число
# и объясните в `04_IMPLEMENTATION.md`, чем именно.
PROMPT_ASSEMBLY_QUERY_BUDGET = 17

WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


class PromptAssemblySnapshotTests(TestCase):
    def setUp(self):
        cache.clear()
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.system_prompt = "Ти менеджер TwoComms."
        self.settings.knowledge_base = "Доставка Новою Поштою."
        self.settings.save()
        self.igc = IgClient.get_or_create_for_sender("snapshot-8-5")
        self.igc.stage = IgClient.Stage.PRODUCT_MATCHED
        self.igc.save()
        IgDeal.objects.create(client=self.igc, invoice_id="snapshot-inv-1")
        IgObjection.objects.create(
            client=self.igc,
            objection_type=IgObjection.Type.PRICE,
            dedupe_key="snapshot-8-5:price",
        )
        IgFunnelResetAudit.objects.create(
            client=self.igc, reset_after_message_id=5, reason="test"
        )
        # Каталог и база знаний кэшируются приложением, поэтому первая сборка
        # всегда дороже. Измерять надо установившееся состояние, иначе число
        # запросов зависит от порядка тестов.
        self._assemble()

    def _assemble(self):
        return bot.assemble_system_instruction(
            self.settings,
            client=self.igc,
            turn_text="Скільки коштує худі і які розміри є?",
        )

    def test_prompt_assembly_stays_within_the_measured_query_budget(self):
        with CaptureQueriesContext(connection) as captured:
            self._assemble()

        self.assertLessEqual(
            len(captured.captured_queries),
            PROMPT_ASSEMBLY_QUERY_BUDGET,
            "сборка промпта снова читает один факт несколько раз",
        )

    def test_no_cached_fact_is_read_more_than_once_per_assembly(self):
        """Именно те четыре чтения, которые повторялись до Э8.5."""
        with CaptureQueriesContext(connection) as captured:
            self._assemble()

        tables = Counter()
        for query in captured.captured_queries:
            match = re.search(r'\bFROM\s+"?([a-z_0-9]+)"?', query["sql"], re.IGNORECASE)
            if match:
                tables[match.group(1)] += 1

        self.assertEqual(tables["management_igpostsalecase"], 1, "open_service_case")
        self.assertEqual(tables["management_igfunnelresetaudit"], 1, "граница сброса")
        self.assertEqual(tables["management_igclient"], 1, "указатель эпизода")
        self.assertEqual(
            tables["management_igpaymentconfirmationreview"], 1, "confirmed_purchase"
        )
        self.assertEqual(tables["management_igorderassignment"], 1, "confirmed_purchase")

    def test_prompt_text_is_identical_without_the_snapshot(self):
        """Golden-сравнение: кэш меняет число запросов, а не содержание."""
        with_snapshot = self._assemble()

        with patch.object(
            ig_turn_snapshot, "prompt_cached", lambda key, producer: producer()
        ), patch.object(ig_turn_snapshot, "cached", lambda key, producer: producer()):
            without_snapshot = self._assemble()

        self.assertEqual(with_snapshot, without_snapshot)

    def test_prompt_assembly_performs_no_writes(self):
        """Основание кэша: внутри области сборки нечему устареть."""
        with CaptureQueriesContext(connection) as captured:
            self._assemble()

        writes = [q["sql"] for q in captured.captured_queries if WRITE.match(q["sql"])]
        self.assertEqual(writes, [], "сборка промпта пишет в БД — кэш стал небезопасен")

    def test_missing_source_still_leaves_the_rest_of_the_prompt(self):
        """`_prompt_section` остаётся: сбой одного блока не уносит остальные."""
        healthy = self._assemble()

        with patch(
            "management.services.ig_objections.objection_prompt_note",
            side_effect=RuntimeError("db down"),
        ):
            degraded = self._assemble()

        self.assertIn("[ПРАВИЛО ТОЧНОСТІ", degraded)
        self.assertIn("[СТАН ДІАЛОГУ", degraded)
        self.assertGreater(len(degraded), len(healthy) - 400)


class SnapshotScopeTests(TestCase):
    """Область жизни кэша — отдельное свойство, и оно про деньги."""

    def setUp(self):
        self.igc = IgClient.get_or_create_for_sender("snapshot-scope-8-5")

    def _confirm_payment_as_a_webhook_would(self, invoice_id):
        """Провайдер подтверждает оплату: сделка + проекция платежа."""
        from django.utils import timezone

        from management.ig_bot_models import IgPaymentProjection

        deal = IgDeal.objects.create(
            client=self.igc,
            invoice_id=invoice_id,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.igc,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=950,
            paid_at=timezone.now(),
        )
        return deal

    def test_prompt_cache_is_a_passthrough_outside_the_scope(self):
        calls = []

        def producer():
            calls.append(1)
            return 7

        self.assertEqual(ig_turn_snapshot.prompt_cached("k", producer), 7)
        self.assertEqual(ig_turn_snapshot.prompt_cached("k", producer), 7)
        self.assertEqual(len(calls), 2, "вне области сборки кэша быть не должно")

    def test_prompt_cache_returns_a_falsy_value_from_the_snapshot(self):
        calls = []

        def producer():
            calls.append(1)
            return False

        with ig_turn_snapshot.prompt_snapshot():
            self.assertFalse(ig_turn_snapshot.prompt_cached("k", producer))
            self.assertFalse(ig_turn_snapshot.prompt_cached("k", producer))
        self.assertEqual(len(calls), 1, "False — тоже посчитанное значение")

    def test_payment_truth_is_not_cached_for_the_whole_turn(self):
        """Вебхук в другом процессе подтверждает оплату внутри хода.

        Если бы платёжная истина кэшировалась на ход, `payment_link_allowed`
        после генерации ответа выписал бы второй инвойс уже оплаченному клиенту.
        """
        with ig_turn_snapshot.turn_snapshot():
            self.assertFalse(client_has_verified_payment(self.igc))

            self._confirm_payment_as_a_webhook_would("paid-mid-turn")

            self.assertTrue(
                client_has_verified_payment(self.igc),
                "оплата, подтверждённая внутри хода, обязана быть видна",
            )

    def test_payment_truth_is_cached_inside_one_prompt_assembly(self):
        with ig_turn_snapshot.prompt_snapshot():
            self.assertFalse(client_has_verified_payment(self.igc))
            with CaptureQueriesContext(connection) as captured:
                self.assertFalse(client_has_verified_payment(self.igc))
        self.assertEqual(len(captured.captured_queries), 0)

    def test_turn_snapshot_caches_the_reset_floor(self):
        IgFunnelResetAudit.objects.create(
            client=self.igc, reset_after_message_id=11, reason="test"
        )
        with ig_turn_snapshot.turn_snapshot():
            self.assertEqual(latest_reset_after_message_id(self.igc), 11)
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(latest_reset_after_message_id(self.igc), 11)
        self.assertEqual(len(captured.captured_queries), 0)

    def test_invalidate_forgets_the_reset_floor_after_a_reset(self):
        IgFunnelResetAudit.objects.create(
            client=self.igc, reset_after_message_id=11, reason="test"
        )
        with ig_turn_snapshot.turn_snapshot():
            self.assertEqual(latest_reset_after_message_id(self.igc), 11)
            IgFunnelResetAudit.objects.create(
                client=self.igc, reset_after_message_id=42, reason="test"
            )
            ig_turn_snapshot.invalidate(f"funnel_reset_floor:{self.igc.pk}")
            self.assertEqual(latest_reset_after_message_id(self.igc), 42)

    def test_a_new_thread_starts_with_an_empty_snapshot(self):
        """ContextVar в потоках демона: новый поток не наследует чужой кэш."""
        import threading

        seen = []

        with ig_turn_snapshot.turn_snapshot():
            ig_turn_snapshot.cached("k", lambda: "parent")

            def worker():
                seen.append(ig_turn_snapshot.active())

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

        self.assertEqual(seen, [False])
