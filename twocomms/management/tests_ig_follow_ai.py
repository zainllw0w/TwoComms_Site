from types import SimpleNamespace
from unittest import TestCase


class FollowAiContractTests(TestCase):
    def test_prompts_allow_optional_follow_cta_without_requiring_it(self):
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT
        from management.services.instagram_bot import PAYMENT_PROTOCOL_NOTE

        for prompt in (DEFAULT_BOT_SYSTEM_PROMPT, PAYMENT_PROTOCOL_NOTE):
            with self.subTest(prompt=prompt[:40]):
                self.assertIn("reply_text і controls — обов'язкові", prompt)
                self.assertIn("follow_cta — необов'язковий", prompt)
                self.assertIn('"include": boolean', prompt)
                self.assertIn('"text": string', prompt)
                self.assertIn("повністю пропусти ключ follow_cta", prompt)

        self.assertNotIn(
            "рівно з ключами reply_text і controls",
            PAYMENT_PROTOCOL_NOTE,
        )

    def test_follow_copy_reasoning_policy_is_bounded(self):
        from management.services.call_ai_analysis import (
            _payload_for_model,
            reasoning_policy,
        )

        policy = reasoning_policy("follow_cta_copy")

        self.assertEqual(policy["task"], "follow_cta_copy")
        self.assertEqual(policy["level"], "low")
        self.assertLessEqual(policy["max_output_tokens"], 512)

        payload = _payload_for_model(
            "gemini-2.5-flash",
            {"generationConfig": {}},
            reasoning_task="follow_cta_copy",
        )
        generation = payload["generationConfig"]
        self.assertEqual(generation["thinkingConfig"]["thinkingBudget"], 0)
        self.assertLess(
            generation["thinkingConfig"]["thinkingBudget"],
            generation["maxOutputTokens"],
        )

        payload = _payload_for_model(
            "gemini-3.7-flash",
            {"generationConfig": {"thinkingConfig": {"thinkingBudget": 999}}},
            reasoning_task="follow_cta_copy",
        )
        generation = payload["generationConfig"]
        self.assertEqual(generation["maxOutputTokens"], 256)
        self.assertEqual(generation["thinkingConfig"]["thinkingLevel"], "low")
        self.assertNotIn("thinkingBudget", generation["thinkingConfig"])

    def test_parser_and_policy_share_static_follow_copy_rejections(self):
        from management.services.ig_follow_cta import _candidate_error
        from management.services.ig_response_control import follow_cta_static_error

        unsafe = (
            "Підпишіться на t.me/twocomms і залишайтеся з нами.",
            "Деталі є на bit.ly/twocomms-follow, будемо раді вам.",
            "Приєднуйтесь до нас на t\u200b.me/twocomms, будемо раді вам.",
            "Підпишіться та використайте код TWOCOMMS10 при замовленні.",
            "Підпишіться та використайте TWOCOMMS10 при замовленні.",
            "Ваш персональний промокод: SUMMER2026 для наступної покупки.",
            "Підпишіться, щоб отримати знижку на наступне замовлення.",
            "Ми бачимо, що ви ще не підписані на нашу сторінку.",
            "Я бачу, що ви ще не підписані на нашу сторінку.",
            "Ви ще не підписані на сторінку, будемо раді вам.",
            "Схоже, ви ще не підписані на сторінку, будемо раді вам.",
            "Статус вашої підписки ще не активний, будемо раді вам.",
            "Будемо раді вам серед підписників [FOLLOW:TRUE].",
        )

        for candidate in unsafe:
            with self.subTest(candidate=candidate):
                parser_reason = follow_cta_static_error(candidate)
                self.assertTrue(parser_reason)
                self.assertEqual(
                    _candidate_error(candidate, base_text="Дякуємо за замовлення."),
                    parser_reason,
                )

    def test_prompt_exposes_follow_opportunity_without_discount_or_surveillance(self):
        from management.services.ig_follow_cta import (
            FollowOpportunity,
            follow_opportunity_prompt_note,
        )

        note = follow_opportunity_prompt_note(
            FollowOpportunity(
                allowed=True,
                client_id=1,
                opportunity="hesitation",
                episode_id=2,
                source_message_id=3,
                order_id=None,
                lifecycle_event_id=None,
                follow_state="not_following",
                follow_state_revision=4,
                conversation_watermark=3,
                context_fingerprint="a" * 64,
                base_text="",
                trigger_key="hesitation:1:message:3",
            )
        )

        self.assertIn("follow_cta.include=false", note)
        self.assertNotIn("10%", note)
        self.assertNotIn("ми не підписані", note)

    def test_irrelevant_opportunity_has_no_prompt_note(self):
        from management.services.ig_follow_cta import (
            FollowOpportunity,
            follow_opportunity_prompt_note,
        )

        self.assertEqual(follow_opportunity_prompt_note(None), "")
        self.assertEqual(
            follow_opportunity_prompt_note(
                FollowOpportunity(
                    allowed=False,
                    client_id=1,
                    opportunity="hesitation",
                    episode_id=2,
                    source_message_id=3,
                    order_id=None,
                    lifecycle_event_id=None,
                    follow_state="unknown",
                    follow_state_revision=0,
                    conversation_watermark=3,
                    context_fingerprint="b" * 64,
                    base_text="",
                    trigger_key="hesitation:1:message:3",
                    reason_codes=("follow_state",),
                )
            ),
            "",
        )
