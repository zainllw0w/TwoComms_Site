"""Э3.5 — доказ менеджера не стає наміром клієнта (`NEW-ANALYSIS-002`)."""

from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisJob,
    IgConversationAnalysisSnapshot,
    InstagramBotMessage,
)
from management.services import ig_analysis_roles as roles
from management.services.bot_conversation_analysis import _normalize


_TYPES = IgConversationAnalysisSnapshot.InteractionType
_BANDS = IgConversationAnalysisSnapshot.Band


def _message(client, text, *, role=InstagramBotMessage.Role.USER):
    return InstagramBotMessage.objects.create(
        client=client,
        sender_id=client.igsid,
        role=role,
        text=text,
        status=InstagramBotMessage.Status.DONE,
    )


def _row(message, role):
    return {"message_id": message.pk, "role": role, "text": message.text or ""}


class ManagerEvidenceBoundaryTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="role-boundary")
        self.manager_message = _message(
            self.client_row,
            "клієнт точно купить, оформлюю замовлення і чекаю оплату",
            role=InstagramBotMessage.Role.MANAGER,
        )
        self.user_message = _message(self.client_row, "Скільки коштує худі?")
        self.manager_by_id = {
            self.manager_message.pk: _row(self.manager_message, "manager"),
        }
        self.mixed_by_id = {
            self.manager_message.pk: _row(self.manager_message, "manager"),
            self.user_message.pk: _row(self.user_message, "user"),
        }

    def _parsed(self, interaction, *, band="qualified", evidence_message, quote,
                probability=0.95):
        return {
            "interaction_type": interaction,
            "score_band": band,
            "purchase_probability": probability,
            "confidence": 0.9,
            "evidence": [{
                "message_id": evidence_message.pk,
                "quote": quote,
                "claim": "intent",
            }],
            "uncertainties": [],
            "repeat_intent": {},
        }

    # --- RED: manager-only note cannot become customer intent ----------------

    def test_manager_only_note_cannot_create_product_interest(self):
        parsed = self._parsed(
            "product_interest",
            evidence_message=self.manager_message,
            quote="клієнт точно купить",
        )

        normalized = _normalize(
            parsed,
            self.manager_by_id,
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.MANAGER_OBSERVATION)
        self.assertEqual(normalized["score_band"], _BANDS.COLD)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.0000"))
        self.assertEqual(normalized["confidence"], Decimal("0.0000"))
        self.assertIn(
            roles.UNCERTAINTY_MANAGER_EVIDENCE,
            normalized["uncertainties"],
        )
        self.assertEqual(
            [item["claim_scope"] for item in normalized["evidence"]],
            [roles.CLAIM_SCOPE_MANAGER],
        )

    @override_settings(IG_ANALYSIS_MANAGER_EVIDENCE_BOUNDARY=False)
    def test_control_flag_off_keeps_the_old_manager_only_intent(self):
        """Контроль: без флага відтворюється саме дефектна поведінка."""
        parsed = self._parsed(
            "product_interest",
            evidence_message=self.manager_message,
            quote="клієнт точно купить",
        )

        normalized = _normalize(
            parsed,
            self.manager_by_id,
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.PRODUCT_INTEREST)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.9500"))
        self.assertNotIn(
            roles.UNCERTAINTY_MANAGER_EVIDENCE,
            normalized["uncertainties"],
        )

    def test_manager_only_note_cannot_create_payment_or_partnership_states(self):
        for interaction, band in (
            ("payment_pending", "checkout"),
            ("collaboration", "qualified"),
            ("wholesale_b2b", "qualified"),
            ("high_intent", "high_intent"),
            ("support_complaint", "exploring"),
        ):
            with self.subTest(interaction=interaction):
                normalized = _normalize(
                    self._parsed(
                        interaction,
                        band=band,
                        evidence_message=self.manager_message,
                        quote="чекаю оплату",
                    ),
                    self.manager_by_id,
                    verified_payment=False,
                )

                self.assertEqual(
                    normalized["interaction_type"],
                    _TYPES.MANAGER_OBSERVATION,
                )
                self.assertEqual(
                    normalized["purchase_probability"],
                    Decimal("0.0000"),
                )

    # --- RED: mixed transcript splits claims by role -------------------------

    def test_mixed_transcript_manager_quote_alone_is_not_customer_intent(self):
        normalized = _normalize(
            self._parsed(
                "high_intent",
                band="high_intent",
                evidence_message=self.manager_message,
                quote="оформлюю замовлення",
            ),
            self.mixed_by_id,
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.MANAGER_OBSERVATION)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.0000"))

    def test_mixed_transcript_keeps_customer_claim_and_labels_manager_rows(self):
        parsed = {
            "interaction_type": "product_interest",
            "score_band": "exploring",
            "purchase_probability": 0.4,
            "confidence": 0.6,
            "evidence": [
                {
                    "message_id": self.user_message.pk,
                    "quote": "Скільки коштує худі?",
                    "claim": "price question",
                },
                {
                    "message_id": self.manager_message.pk,
                    "quote": "оформлюю замовлення",
                    "claim": "manager context",
                },
            ],
            "uncertainties": [],
            "repeat_intent": {},
        }

        normalized = _normalize(parsed, self.mixed_by_id, verified_payment=False)
        coverage = roles.evidence_role_coverage(normalized["evidence"])

        self.assertEqual(normalized["interaction_type"], _TYPES.PRODUCT_INTEREST)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.4000"))
        self.assertEqual(
            coverage.customer_message_ids,
            (self.user_message.pk,),
        )
        self.assertEqual(
            coverage.manager_message_ids,
            (self.manager_message.pk,),
        )
        self.assertEqual(
            {
                item["message_id"]: item["claim_scope"]
                for item in normalized["evidence"]
            },
            {
                self.user_message.pk: roles.CLAIM_SCOPE_CUSTOMER,
                self.manager_message.pk: roles.CLAIM_SCOPE_MANAGER,
            },
        )

    # --- Guards against a fix that would itself assert an untruth -----------

    def test_verified_payment_conclusion_is_not_downgraded_by_role_boundary(self):
        normalized = _normalize(
            {
                "interaction_type": "paid_order_waiting",
                "score_band": "paid",
                "purchase_probability": 0.9,
                "confidence": 0.9,
                "evidence": [],
                "uncertainties": [],
                "repeat_intent": {},
            },
            self.manager_by_id,
            verified_payment=True,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.PAID_ORDER_WAITING)
        self.assertEqual(normalized["score_band"], _BANDS.PAID)
        self.assertNotIn(
            roles.UNCERTAINTY_MANAGER_EVIDENCE,
            normalized["uncertainties"],
        )

    def test_media_only_customer_message_is_not_relabelled_as_manager(self):
        media_message = _message(self.client_row, "")
        by_id = {
            media_message.pk: {
                "message_id": media_message.pk,
                "role": "user",
                "text": "",
                "media": [{"role": "product", "intent": "product_question"}],
            },
        }

        normalized = _normalize(
            {
                "interaction_type": "product_interest",
                "score_band": "exploring",
                "purchase_probability": 0.5,
                "confidence": 0.5,
                "evidence": [],
                "uncertainties": [],
                "repeat_intent": {},
            },
            by_id,
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.PRODUCT_INTEREST)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.5000"))
        self.assertIn(
            roles.UNCERTAINTY_EVIDENCE_UNVERIFIED,
            normalized["uncertainties"],
        )

    def test_unverified_customer_quote_is_reported_not_relabelled(self):
        """Модель не дала перевіреної цитати — це не порушення ролі.

        Пониження типу тут стверджувало б факт («клієнт лише цікавився»),
        якого дані не підтверджують: клієнт у вікні є, а детермінований
        user-чек (явний запит кастомного принту) взагалі не дає цитати.
        """
        normalized = _normalize(
            {
                "interaction_type": "high_intent",
                "score_band": "high_intent",
                "purchase_probability": 0.9,
                "confidence": 0.9,
                "evidence": [{
                    "message_id": self.user_message.pk,
                    "quote": "точно беру дві штуки",
                    "claim": "paraphrased, not in the message",
                }],
                "uncertainties": [],
                "repeat_intent": {},
            },
            {self.user_message.pk: _row(self.user_message, "user")},
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.HIGH_INTENT)
        self.assertEqual(normalized["evidence"], [])
        self.assertIn(
            roles.UNCERTAINTY_EVIDENCE_UNVERIFIED,
            normalized["uncertainties"],
        )
        self.assertEqual(
            normalized["role_boundary_reason"],
            roles.REASON_CUSTOMER_QUOTE_UNVERIFIED,
        )

    def test_manager_only_window_without_evidence_is_manager_observation(self):
        """У вікні немає клієнта взагалі — висновок неатрибутовний клієнту."""
        normalized = _normalize(
            {
                "interaction_type": "payment_pending",
                "score_band": "checkout",
                "purchase_probability": 0.8,
                "confidence": 0.8,
                "evidence": [],
                "uncertainties": [],
                "repeat_intent": {},
            },
            self.manager_by_id,
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.MANAGER_OBSERVATION)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.0000"))
        self.assertEqual(
            normalized["role_boundary_reason"],
            roles.REASON_MANAGER_ONLY_WINDOW,
        )

    def test_bot_own_words_are_not_customer_intent_and_not_manager_note(self):
        bot_message = _message(
            self.client_row,
            "Готові оформити замовлення?",
            role=InstagramBotMessage.Role.MODEL,
        )
        normalized = _normalize(
            {
                "interaction_type": "high_intent",
                "score_band": "high_intent",
                "purchase_probability": 0.99,
                "confidence": 0.99,
                "evidence": [{
                    "message_id": bot_message.pk,
                    "quote": "Готові оформити замовлення?",
                    "claim": "intent",
                }],
                "uncertainties": [],
                "repeat_intent": {},
            },
            {
                bot_message.pk: _row(bot_message, "model"),
                self.user_message.pk: _row(self.user_message, "user"),
            },
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], _TYPES.INFORMATION_ONLY)
        self.assertEqual(normalized["purchase_probability"], Decimal("0.0000"))
        self.assertEqual(
            [item["claim_scope"] for item in normalized["evidence"]],
            [roles.CLAIM_SCOPE_BOT],
        )


class ManagerObservationOperationalScopeTests(TestCase):
    """Manager-only знімок не змінює customer follow-up і CRM-фільтри."""

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_adversarial_manager_note_stays_outside_customer_selectors(self, generate):
        from management.services import bot_conversation_analysis as analysis
        from management.services.bot_followups import _suppressed_interaction
        from management.services.ig_analysis_materiality import (
            current_analysis_snapshot,
        )

        client = IgClient.objects.create(igsid="role-boundary-e2e")
        episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=1,
            materialization_key="role-boundary-e2e:episode:1",
        )
        client.current_commercial_episode = episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        manager_message = _message(
            client,
            "опт: клієнт бере 50 худі, чекаю оплату",
            role=InstagramBotMessage.Role.MANAGER,
        )
        now = timezone.now()
        job = analysis.schedule_analysis(
            client,
            manager_message,
            now=now,
            delay_seconds=0,
        )
        self.assertIsNotNone(job)
        generate.return_value = {
            "parsed": {
                "interaction_type": "wholesale_b2b",
                "score_band": "high_intent",
                "purchase_probability": 0.99,
                "confidence": 0.99,
                "evidence": [{
                    "message_id": manager_message.pk,
                    "quote": "клієнт бере 50 худі",
                    "claim": "wholesale intent",
                }],
                "uncertainties": [],
                "repeat_intent": {},
            },
            "model": "gemini-3.6-flash",
            "meta": {},
        }

        result = analysis.process_due_analysis(limit=1, now=now)

        self.assertEqual(result["done"], 1, result)
        snapshot = IgConversationAnalysisSnapshot.objects.get(client=client)
        self.assertEqual(snapshot.interaction_type, _TYPES.MANAGER_OBSERVATION)
        self.assertEqual(snapshot.purchase_probability, Decimal("0.0000"))
        self.assertEqual(snapshot.rules_version, roles.ROLE_BOUNDARY_POLICY_VERSION)
        self.assertIsNone(current_analysis_snapshot(client))
        self.assertEqual(
            current_analysis_snapshot(client, include_manager=True).pk,
            snapshot.pk,
        )
        self.assertEqual(_suppressed_interaction(client), "")
        job.refresh_from_db()
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.DONE)
