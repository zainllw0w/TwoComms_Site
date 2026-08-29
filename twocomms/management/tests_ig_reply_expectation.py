"""ЭБ.1 — техническое извинение только тому, кто действительно ждёт ответа.

Зафиксированный случай (production, 2026-08-29): клиент сделал репост истории и
отметил бренд. Раньше бот благодарил и разбирал изображение; в этот раз он
ответил «Вибачте за технічну затримку. Я відновлюю деталі…». Разбор пути дал два
независимых дефекта, и каждый закреплён здесь тестом:

1. `budget_remaining_ms` не передавался в `holding_decision()` из живого хода,
   поэтому уровень L1 драбины («пока бюджет хода не исчерпан — индикатор набора,
   а не текст») был недостижимым кодом;
2. «нужен ли ответ» определялось через `is_low_intent_turn()`, и её исключение
   «бот задал вопрос → короткая реплика — это ответ» снимало gate с репоста истории,
   который ответом на вопрос не является.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services import ig_provider_incidents as incidents
from management.services.ig_reply_expectation import classify
from management.services.ig_turn_budget import customer_notice_threshold_seconds

STORY_MENTION_MEDIA = [
    {
        "media_type": "story_mention",
        "provenance": "live_webhook",
        "provider_native_mention": True,
        "target_username": "twocomms",
        "status": "owned",
        "storage_name": "ugc/story-1.jpg",
    }
]


def _inbound(client, text="", *, media=None, attachments="", waited_seconds=0.0):
    row = InstagramBotMessage.objects.create(
        sender_id=client.igsid,
        client=client,
        role=InstagramBotMessage.Role.USER,
        text=text,
        status=InstagramBotMessage.Status.PENDING,
        attachments=attachments,
        attachment_media=media or [],
    )
    if waited_seconds:
        older = timezone.now() - timedelta(seconds=waited_seconds)
        InstagramBotMessage.objects.filter(pk=row.pk).update(
            created_at=older, provider_created_at=older
        )
        row.refresh_from_db()
    row.client = client
    return row


def _outgoing(client, text, *, mid="mid-out-1"):
    return InstagramBotMessage.objects.create(
        sender_id=client.igsid,
        client=client,
        role=InstagramBotMessage.Role.MODEL,
        text=text,
        status=InstagramBotMessage.Status.DONE,
        send_state="sent",
        provider_message_id=mid,
    )


class ReplyExpectationTests(TestCase):
    """Три признака, которые раньше были одним."""

    def setUp(self):
        self.igc = IgClient.get_or_create_for_sender("expectation-sender")

    def test_story_repost_owes_an_answer_but_nobody_waits_for_it(self):
        # "(зображення)" — ровно тот текст-заполнитель, который стоял в
        # production-строке 2793 (репост 29.08 10:31:13, ответ «Вибачте за
        # технічну затримку» в 10:31:56). Он и обошёл прежний gate:
        # `reaction_or_sticker` требует ПУСТОГО текста, а заполнитель не пустой
        # и не похож на «Добре», поэтому ход считался требующим ответа.
        for text in ("", "(зображення)", "(медіа)"):
            with self.subTest(text=text):
                row = _inbound(self.igc, text, media=STORY_MENTION_MEDIA)

                expectation = classify(row, ugc_turn=True)

                self.assertFalse(
                    expectation.waiting, "за репост никто не ждёт квитанции"
                )
                self.assertTrue(
                    expectation.substantive_reply_owed,
                    "благодарность мы всё равно должны — просто не срочно",
                )
                self.assertEqual(expectation.reason, "ugc_turn")

    def test_story_repost_after_a_bot_question_is_still_not_an_answer(self):
        """Тот самый путь: исключение «бот задал вопрос» снимало gate."""
        _outgoing(self.igc, "Який розмір вам потрібен?")
        row = _inbound(self.igc, media=STORY_MENTION_MEDIA)

        self.assertFalse(classify(row, ugc_turn=True).waiting)

    def test_reaction_after_a_bot_question_owes_nothing(self):
        _outgoing(self.igc, "Який розмір вам потрібен?")
        row = _inbound(self.igc, media=[{"media_type": "reaction"}])

        expectation = classify(row)

        self.assertFalse(expectation.waiting)
        self.assertFalse(expectation.substantive_reply_owed)
        self.assertEqual(expectation.reason, "reaction_only")

    def test_short_text_after_a_bot_question_is_an_answer_and_is_awaited(self):
        """Сохранённое поведение: «Добре» после вопроса бота — это ответ."""
        _outgoing(self.igc, "Оформляємо замовлення?")
        row = _inbound(self.igc, "Добре")

        expectation = classify(row)

        self.assertTrue(expectation.waiting)
        self.assertEqual(expectation.reason, "answer_to_bot_question")

    def test_short_text_without_a_bot_question_closes_the_topic(self):
        _outgoing(self.igc, "Гарного дня!")
        row = _inbound(self.igc, "Дякую")

        expectation = classify(row)

        self.assertFalse(expectation.waiting)
        self.assertEqual(expectation.reason, "short_ack")

    def test_photo_without_text_is_a_request(self):
        """Клиент прислал скриншот товара — он ждёт ответа."""
        row = _inbound(self.igc, media=[{"media_type": "image"}])

        expectation = classify(row)

        self.assertTrue(expectation.waiting)
        self.assertEqual(expectation.reason, "media_without_text")

    def test_explicit_request_wins_over_any_form(self):
        row = _inbound(self.igc, "Скільки коштує?", media=STORY_MENTION_MEDIA)

        expectation = classify(row, ugc_turn=True)

        self.assertTrue(expectation.waiting, "вопрос о цене сильнее формы хода")
        self.assertEqual(expectation.reason, "explicit_request")

    def test_second_unanswered_message_marks_active_waiting(self):
        _outgoing(self.igc, "Вітаю!")
        _inbound(self.igc, "А є розмір XL?")
        row = _inbound(self.igc, "ну що там?")

        expectation = classify(row)

        self.assertTrue(expectation.waiting)
        self.assertTrue(
            expectation.actively_waiting,
            "клиент переспросил, не получив ответа",
        )

    def test_first_message_of_a_dialog_is_not_active_waiting(self):
        row = _inbound(self.igc, "Привіт, є худі?")

        expectation = classify(row)

        self.assertTrue(expectation.waiting)
        self.assertFalse(expectation.actively_waiting)


class ApologyGateTests(TestCase):
    """Четыре условия, которые должны выполниться ВМЕСТЕ."""

    def setUp(self):
        self.igc = IgClient.get_or_create_for_sender("apology-gate-sender")

    def _decision(self, row, **kwargs):
        threshold_ms = int(customer_notice_threshold_seconds() * 1000)
        waited_since = row.provider_created_at or row.created_at
        waited_ms = int((timezone.now() - waited_since).total_seconds() * 1000)
        kwargs.setdefault("budget_remaining_ms", max(0, threshold_ms - waited_ms))
        return incidents.holding_decision(row, **kwargs)

    def _open_incident(self):
        incidents.register_provider_failure(
            role="chat", failure_kind="quota_429", http_code=429, model="gemini-3.7-flash"
        )

    def test_story_repost_never_receives_a_technical_notice(self):
        """Главный случай отчёта клиента."""
        self._open_incident()
        row = _inbound(
            self.igc, media=STORY_MENTION_MEDIA, waited_seconds=600.0
        )

        decision = self._decision(row, ugc_turn=True)

        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "no_reply_expected")

    def test_fresh_turn_sees_typing_not_text(self):
        """L1: пока бюджет хода не исчерпан — молчим."""
        self._open_incident()
        row = _inbound(self.igc, "Скільки коштує худі?")

        decision = self._decision(row)

        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "budget_not_exhausted")

    def test_isolated_failure_stays_silent_when_recovery_will_answer(self):
        """Один неудачный вызов не прогнозирует долгой паузы."""
        row = _inbound(self.igc, "Скільки коштує худі?", waited_seconds=600.0)

        decision = self._decision(row, recovery_expected=True)

        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "isolated_failure_recovery_pending")

    def test_a_customer_who_re_asked_gets_one_notice_even_without_an_incident(self):
        """Тишина для того, кто уже переспросил, читается как поломка."""
        _outgoing(self.igc, "Вітаю!")
        _inbound(self.igc, "А є розмір XL?")
        row = _inbound(self.igc, "ну що там?", waited_seconds=600.0)

        decision = self._decision(row, recovery_expected=True)

        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "no_open_incident")

    def test_open_incident_and_a_spent_budget_allow_exactly_one_notice(self):
        self._open_incident()
        row = _inbound(self.igc, "Скільки коштує худі?", waited_seconds=600.0)

        first = self._decision(row, recovery_expected=True)
        self.assertTrue(first.should_send)
        self.assertEqual(first.reason, "first_holding_in_incident")

        incidents.reserve_holding(first.episode_id)
        second = self._decision(row, recovery_expected=True)
        self.assertFalse(second.should_send)
        self.assertEqual(second.reason, "already_sent_in_incident")

    def test_reaction_needs_no_later_answer_at_all(self):
        """Реакция попадает в «ответ не нужен вообще», репост — нет."""
        row = _inbound(self.igc, media=[{"media_type": "reaction"}], waited_seconds=600.0)

        decision = self._decision(row)

        self.assertIn(decision.reason, incidents.SUPPRESS_NO_ANSWER_REASONS)

    def test_story_repost_is_answered_later_not_never(self):
        row = _inbound(self.igc, media=STORY_MENTION_MEDIA, waited_seconds=600.0)

        decision = self._decision(row, ugc_turn=True)

        self.assertNotIn(
            decision.reason,
            incidents.SUPPRESS_NO_ANSWER_REASONS,
            "подяку за репост клиент всё равно должен получить",
        )

    @override_settings(IG_LOW_INTENT_HOLDING_GATE=False)
    def test_flag_off_restores_the_previous_behaviour(self):
        self._open_incident()
        row = _inbound(self.igc, media=STORY_MENTION_MEDIA, waited_seconds=600.0)

        decision = self._decision(row, ugc_turn=True, recovery_expected=False)

        self.assertTrue(decision.should_send, "откат должен быть возможен флагом")


class DeterministicUgcReplyTests(TestCase):
    """L3: подяка за відмітку не требует модели вообще."""

    def setUp(self):
        self.igc = IgClient.get_or_create_for_sender("ugc-l3-sender")

    def test_acknowledgement_is_never_empty_without_a_model(self):
        from management.services.ig_ugc_assessment import safe_ugc_acknowledgement

        for language in ("uk", "ru", "en"):
            self.igc.language = language
            self.igc.save(update_fields=["language"])
            text = safe_ugc_acknowledgement(self.igc, "", assessment=None)
            self.assertTrue(text.strip(), language)
            self.assertNotIn("затрим", text.casefold())
            self.assertNotIn("задерж", text.casefold())
            self.assertNotIn("delay", text.casefold())
