from datetime import timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from management.ig_bot_models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    IgDeal,
    IgDealItem,
    IgPaymentConfirmationReview,
    IgPaymentProjection,
)
from management.models import InstagramBotMessage
from management.services.ig_payment_review import record_review_decision
from orders.models import Order


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
)
class CommercialEpisodeTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="episode-manager",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client = IgClient.get_or_create_for_sender(
            "episode-client",
            defaults={"username": "repeat_buyer", "display_name": "Олена"},
        )

    def _order(self, *, total="1200.00", discount="0.00", status="new", ttn=""):
        return Order.objects.create(
            full_name="Олена Тест",
            phone="380501112233",
            city="Харків",
            np_office="Відділення №1",
            total_sum=Decimal(total),
            discount_amount=Decimal(discount),
            status=status,
            tracking_number=ttn,
            source="manual",
            sale_source="Instagram",
        )

    def _confirmed_review(self, *, deal=None, key="episode-review"):
        confirmed_amount = Decimal(deal.amount if deal is not None else "1200.00")
        review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=deal,
            dedupe_key=key,
            watermark_message_id=101,
            evidence={"order_draft": {"quoted_total": str(confirmed_amount)}},
        )
        record_review_decision(
            review,
            actor=self.actor,
            decision="manager_verified",
            verification_scope="full_payment",
            confirmed_amount=confirmed_amount,
        )
        review.refresh_from_db()
        return review

    def test_one_client_can_have_multiple_immutable_episode_histories(self):
        from management.ig_bot_models import IgCommercialEpisode
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
            start_repeat_episode,
        )

        first_review = self._confirmed_review(key="episode-first")
        first = ensure_episode_for_review(first_review)
        bind_episode_order(first, self._order(total="1200.00"), creation_mode="linked_existing")

        second = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[501],
            confidence=Decimal("0.96"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )

        first.refresh_from_db()
        self.client.refresh_from_db()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.sequence, 1)
        self.assertEqual(second.sequence, 2)
        self.assertEqual(first.intended_order.total_sum, Decimal("1200.00"))
        self.assertEqual(first.repeat_kind, IgCommercialEpisode.RepeatKind.FIRST_PURCHASE)
        self.assertEqual(second.repeat_kind, IgCommercialEpisode.RepeatKind.EXPLICIT_MORE)
        self.assertEqual(second.evidence_message_ids, [501])
        self.assertEqual(self.client.current_commercial_episode_id, second.pk)

    def test_one_physical_order_cannot_belong_to_two_episodes(self):
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
            start_repeat_episode,
        )

        first = ensure_episode_for_review(self._confirmed_review(key="episode-order-one"))
        second = start_repeat_episode(
            self.client,
            repeat_kind="reorder",
            evidence_message_ids=[502],
            confidence=Decimal("0.90"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )
        order = self._order()

        bind_episode_order(first, order, creation_mode="linked_existing")
        self.assertEqual(
            bind_episode_order(first, order, creation_mode="linked_existing").pk,
            first.pk,
        )
        with self.assertRaisesMessage(ValueError, "іншому комерційному епізоду"):
            bind_episode_order(second, order, creation_mode="linked_existing")

    def test_replay_attaches_new_attribution_to_episode_already_bound_to_same_order(self):
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
            episode_payload,
        )
        from management.services.ig_order_links import create_order_attribution

        review = self._confirmed_review(key="episode-attribution-repair")
        order = self._order(total="1200.00")
        review.order = order
        review.save(update_fields=["order", "updated_at"])
        episode = ensure_episode_for_review(review)
        bind_episode_order(episode, order)

        attribution = create_order_attribution(
            order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            review=review,
            created_by=self.actor,
        )

        episode.refresh_from_db()
        self.assertEqual(episode.order_attribution_id, attribution.pk)
        self.assertEqual(episode.primary_payment_review_id, review.pk)
        payload = episode_payload(episode)
        self.assertEqual(payload["creation_mode"], "linked_existing")
        self.assertEqual(payload["payment_source"], "manager_verified")

    def test_reconcile_command_converges_unattributed_components_after_release(self):
        from django.core.management import call_command
        from management.ig_bot_models import IgCommercialEpisode, IgDeal

        deal = IgDeal.objects.create(client=self.client, amount=Decimal("640.00"))

        call_command("reconcile_ig_commercial_episodes", passes=3)

        episode = IgCommercialEpisode.objects.get(deal=deal)
        self.assertEqual(episode.client_id, self.client.pk)

    def test_order_truth_change_closes_only_the_exact_episode(self):
        from management.ig_bot_models import IgCommercialEpisode
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
            start_repeat_episode,
        )

        first = ensure_episode_for_review(self._confirmed_review(key="episode-fulfillment"))
        first_order = self._order(status="new", ttn="20450000000011")
        bind_episode_order(first, first_order, creation_mode="linked_existing")
        second = start_repeat_episode(
            self.client,
            repeat_kind="gift",
            evidence_message_ids=[611],
            confidence=Decimal("0.91"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )

        with self.captureOnCommitCallbacks(execute=True):
            first_order.status = "done"
            first_order.shipment_status = "Отримано"
            first_order.save(update_fields=["status", "shipment_status"])

        first.refresh_from_db()
        second.refresh_from_db()
        self.client.refresh_from_db()
        self.assertEqual(first.state, IgCommercialEpisode.State.FULFILLED)
        self.assertEqual(first.outcome, "fulfilled")
        self.assertIsNotNone(first.closed_at)
        self.assertEqual(first.fulfillment_snapshot["shipment_status"], "Отримано")
        self.assertEqual(second.state, IgCommercialEpisode.State.ACTIVE)
        self.assertEqual(self.client.current_commercial_episode_id, second.pk)
        self.assertEqual(
            first.events.filter(event_type="fulfillment_updated").count(),
            1,
        )

    def test_repeat_episode_requires_message_evidence(self):
        from management.services.ig_commercial_episodes import start_repeat_episode

        with self.assertRaisesMessage(ValueError, "доказ повідомлення"):
            start_repeat_episode(
                self.client,
                repeat_kind="reorder",
                evidence_message_ids=[],
                confidence=Decimal("0.90"),
                analysis_model="gemini-test",
                analysis_prompt_version="repeat-v1",
            )

    def test_manager_decision_refreshes_episode_payment_snapshot(self):
        from management.ig_bot_models import IgCommercialEpisode

        deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("2100.00"),
            pay_type=IgDeal.PayType.PREPAYMENT,
            requested_payment_amount=Decimal("500.00"),
            requested_payment_evidence_ids=[701],
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=deal,
            dedupe_key="episode-payment-snapshot",
            evidence={"order_draft": {"quoted_total": "2100.00"}},
        )

        record_review_decision(
            review,
            actor=self.actor,
            decision="manager_verified",
            verification_scope="prepayment",
            confirmed_amount="500.00",
        )

        episode = IgCommercialEpisode.objects.get(primary_payment_review=review)
        self.assertEqual(episode.payment_snapshot["order_total"], "2100.00")
        self.assertEqual(episode.payment_snapshot["requested_payment_amount"], "500.00")
        self.assertEqual(episode.payment_snapshot["manager_confirmed_amount"], "500.00")
        self.assertEqual(episode.payment_snapshot["remaining_amount"], "1600.00")
        self.assertEqual(episode.payment_snapshot["manager_scope"], "prepayment")
        self.assertEqual(episode.payment_snapshot["manager_decision_id"], review.decisions.get().pk)
        from management.services.ig_commercial_episodes import client_payment_truth_state

        payment_truth = client_payment_truth_state(self.client)["payment_truth"]
        self.assertEqual([row["episode_id"] for row in payment_truth], [episode.pk])

    def test_linked_order_total_controls_remaining_without_erasing_negotiated_total(self):
        from management.services.ig_commercial_episodes import payment_truth_snapshot

        deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("2100.00"),
            pay_type=IgDeal.PayType.ONLINE_FULL,
            requested_payment_amount=Decimal("2100.00"),
        )
        review = self._confirmed_review(deal=deal, key="episode-actual-total")
        order = self._order(total="2180.00")

        truth = payment_truth_snapshot(deal=deal, review=review, order=order)

        self.assertEqual(truth["negotiated_order_total"], "2100.00")
        self.assertEqual(truth["actual_order_total"], "2180.00")
        self.assertEqual(truth["order_total"], "2180.00")
        self.assertEqual(truth["remaining_amount"], "80.00")

    def test_discounted_linked_order_uses_final_payable_total_for_payment_truth(self):
        from management.services.ig_commercial_episodes import payment_truth_snapshot

        deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("2100.00"),
            pay_type=IgDeal.PayType.ONLINE_FULL,
            requested_payment_amount=Decimal("2100.00"),
        )
        review = self._confirmed_review(deal=deal, key="episode-discounted-order-total")
        order = self._order(total="2180.00", discount="80.00")

        truth = payment_truth_snapshot(deal=deal, review=review, order=order)

        self.assertEqual(truth["order_subtotal"], "2180.00")
        self.assertEqual(truth["order_discount_amount"], "80.00")
        self.assertEqual(truth["actual_order_total"], "2100.00")
        self.assertEqual(truth["order_total"], "2100.00")
        self.assertEqual(truth["remaining_amount"], "0.00")

    def test_review_only_payment_truth_derives_its_exact_deal_and_projection(self):
        from management.services.ig_commercial_episodes import payment_truth_snapshot

        deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("1280.00"),
            requested_payment_amount=Decimal("315.00"),
            currency="UAH",
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("315.00"),
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=deal,
            dedupe_key="review-only-scoped-payment-truth",
        )

        truth = payment_truth_snapshot(review=review)

        self.assertEqual(truth["deal_id"], deal.pk)
        self.assertEqual(truth["negotiated_order_total"], "1280.00")
        self.assertEqual(truth["requested_payment_amount"], "315.00")
        self.assertEqual(truth["provider_confirmed_amount"], "315.00")

    def test_failed_order_materialization_does_not_leave_current_episode(self):
        from management.ig_bot_models import IgCommercialEpisode
        from orders.services.order_builder import create_order_from_deal

        unverified = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("500.00"),
        )
        with self.assertRaisesMessage(ValueError, "source-qualified"):
            create_order_from_deal(unverified)
        self.client.refresh_from_db()
        self.assertIsNone(self.client.current_commercial_episode_id)
        self.assertFalse(IgCommercialEpisode.objects.filter(client=self.client).exists())

        mismatched = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("1000.00"),
        )
        IgDealItem.objects.create(
            deal=mismatched,
            title="Футболка",
            qty=1,
            unit_price=Decimal("900.00"),
            line_total=Decimal("900.00"),
        )
        IgPaymentProjection.objects.create(
            client=self.client,
            deal=mismatched,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("1000.00"),
        )
        with self.assertRaisesMessage(ValueError, "total does not match"):
            create_order_from_deal(mismatched)
        self.client.refresh_from_db()
        self.assertIsNone(self.client.current_commercial_episode_id)
        self.assertFalse(IgCommercialEpisode.objects.filter(client=self.client).exists())

    def test_exact_resolver_finds_attribution_only_order_by_number_and_ttn(self):
        from management.services.ig_commercial_episodes import resolve_client_order
        from management.services.ig_order_links import create_order_attribution

        order = self._order(status="ship", ttn="20450000000001")
        create_order_attribution(
            order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            created_by=self.actor,
        )

        by_number = resolve_client_order(self.client, order.order_number)
        by_ttn = resolve_client_order(self.client, "20450000000001")

        self.assertEqual(by_number.order.pk, order.pk)
        self.assertEqual(by_ttn.order.pk, order.pk)
        self.assertEqual(by_number.match_kind, "order_number")
        self.assertEqual(by_ttn.match_kind, "ttn")

    def test_blank_reference_is_ambiguous_for_multiple_physical_orders(self):
        from management.services.ig_commercial_episodes import (
            OrderResolutionError,
            resolve_client_order,
        )
        from management.services.ig_order_links import create_order_attribution

        for suffix in ("1", "2"):
            create_order_attribution(
                self._order(ttn=f"2045000000000{suffix}"),
                client=self.client,
                creation_mode="linked_existing",
                payment_source="manager_verified",
                created_by=self.actor,
            )

        with self.assertRaises(OrderResolutionError) as caught:
            resolve_client_order(self.client, "")
        self.assertEqual(caught.exception.code, "ambiguous_order")

    def test_linking_cancelled_order_is_blocked(self):
        from management.services.ig_order_links import link_existing_order_to_review

        review = self._confirmed_review(key="episode-cancelled")
        order = self._order(status="cancelled")

        with self.assertRaisesMessage(ValueError, "скасоване"):
            link_existing_order_to_review(
                review,
                order_identifier=order.order_number,
                actor=self.actor,
            )

    def test_linking_shipped_order_requires_structured_override(self):
        from management.services.ig_order_links import link_existing_order_to_review

        review = self._confirmed_review(key="episode-shipped")
        order = self._order(status="ship")
        order.payment_status = "paid"
        order.save(update_fields=["payment_status"])

        with self.assertRaisesMessage(ValueError, "структурована причина"):
            link_existing_order_to_review(
                review,
                order_identifier=order.order_number,
                actor=self.actor,
            )

        linked = link_existing_order_to_review(
            review,
            order_identifier=order.order_number,
            actor=self.actor,
            override_code="historical_fulfilled_order",
            override_reason="Замовлення було створено менеджером раніше",
        )
        self.assertEqual(linked.pk, order.pk)

    def test_client_api_counts_physical_orders_and_exposes_episode_history(self):
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
            start_repeat_episode,
        )

        first_review = self._confirmed_review(key="episode-api-first")
        first = ensure_episode_for_review(first_review)
        order = self._order(total="900.00")
        bind_episode_order(first, order, creation_mode="linked_existing")
        from management.services.ig_order_links import create_order_attribution

        create_order_attribution(
            order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            review=first_review,
            created_by=self.actor,
        )
        start_repeat_episode(
            self.client,
            repeat_kind="gift",
            evidence_message_ids=[503],
            confidence=Decimal("0.94"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )
        web_client = Client()
        web_client.force_login(self.actor)

        response = web_client.get(
            reverse("management_bot_client_detail_api", args=[self.client.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["orders"]["physical_count"], 1)
        self.assertEqual(payload["commercial_episodes"]["count"], 2)
        self.assertEqual(payload["commercial_episodes"]["current"]["repeat_kind"], "gift")
        ordered_episode = next(
            item
            for item in payload["commercial_episodes"]["items"]
            if item.get("order", {}).get("id")
        )
        self.assertEqual(
            ordered_episode["order"]["amount"],
            "900.00",
        )
        self.assertEqual(payload["orders"]["attribution_count"], 1)

    def test_client_api_exposes_unknown_then_episode_scoped_stale_potential(self):
        from management.services.ig_commercial_episodes import start_repeat_episode

        web_client = Client()
        web_client.force_login(self.actor)
        detail_url = reverse("management_bot_client_detail_api", args=[self.client.pk])

        unknown = web_client.get(detail_url, secure=True).json()["potential"]
        self.assertEqual(unknown["state"], "unknown")
        self.assertEqual(unknown["band"], "unknown")
        self.assertIsNone(unknown["probability"])
        self.assertEqual(unknown["source"], "none")

        repeat_message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу ще одну футболку",
        )
        episode = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[repeat_message.pk],
            confidence=Decimal("0.95"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v2",
        )
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            commercial_episode=episode,
            last_analyzed_message=repeat_message,
            dedupe_key="potential-current-episode",
            score_band=IgConversationAnalysisSnapshot.Band.HIGH_INTENT,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            purchase_probability=Decimal("0.8700"),
            confidence=Decimal("0.9100"),
            evidence=[{
                "message_id": repeat_message.pk,
                "source_role": "user",
                "quote": "Хочу ще одну футболку",
                "claim": "repeat_purchase",
            }],
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v2",
        )

        current = web_client.get(detail_url, secure=True).json()["potential"]
        self.assertEqual(current["state"], "current")
        self.assertEqual(current["scope"], "current_episode")
        self.assertEqual(current["episode_id"], episode.pk)
        self.assertEqual(current["evidence_message_ids"], [repeat_message.pk])
        self.assertNotIn("factual_payment", current)
        self.assertNotIn("factual_order_count", current)

        later_message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="А чорна є?",
        )
        stale = web_client.get(detail_url, secure=True).json()["potential"]
        self.assertEqual(stale["state"], "stale")
        self.assertFalse(stale["fresh"])
        self.assertEqual(stale["watermark_message_id"], snapshot.last_analyzed_message_id)
        self.assertEqual(stale["latest_message_id"], later_message.pk)

    def test_existing_order_candidate_api_searches_compact_safe_cards(self):
        from management.services.ig_order_links import create_order_attribution

        candidate = self._order(total="1350.00")
        candidate.full_name = "Олена Вокзальна"
        candidate.save(update_fields=["full_name"])
        unsafe = self._order(total="700.00", status="cancelled")
        other_client = IgClient.get_or_create_for_sender("other-instagram-client")
        owned = self._order(total="990.00")
        create_order_attribution(
            owned,
            client=other_client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            created_by=self.actor,
        )
        web_client = Client()
        web_client.force_login(self.actor)

        response = web_client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.client.pk, "q": "Вокзальна"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload["items"]], [candidate.pk])
        self.assertEqual(payload["items"][0]["number"], candidate.order_number)
        self.assertEqual(payload["items"][0]["amount"], "1350.00")
        self.assertTrue(payload["items"][0]["selectable"])

        all_response = web_client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.client.pk, "q": ""},
            secure=True,
        ).json()
        by_id = {item["id"]: item for item in all_response["items"]}
        self.assertFalse(by_id[unsafe.pk]["selectable"])
        self.assertEqual(by_id[unsafe.pk]["blocked_reason"], "cancelled")
        self.assertFalse(by_id[owned.pk]["selectable"])
        self.assertEqual(by_id[owned.pk]["blocked_reason"], "owned_by_other_client")

    def test_existing_order_candidates_expose_review_scoped_payment_overrides(self):
        unpaid = self._order(total="1350.00")
        paid = self._order(total="1350.00")
        paid.payment_status = "paid"
        paid.save(update_fields=["payment_status"])
        shipped_unpaid = self._order(total="1350.00", status="ship")
        review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="episode-candidate-payment",
            watermark_message_id=810,
            evidence={"order_draft": {"quoted_total": "1350.00"}},
        )
        record_review_decision(
            review,
            actor=self.actor,
            decision="manager_verified",
            verification_scope="full_payment",
            confirmed_amount="1350.00",
        )
        review.refresh_from_db()
        web_client = Client()
        web_client.force_login(self.actor)

        payload = web_client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.client.pk, "review_id": review.pk},
            secure=True,
        ).json()

        by_id = {item["id"]: item for item in payload["items"]}
        self.assertTrue(by_id[unpaid.pk]["requires_override"])
        self.assertEqual(by_id[unpaid.pk]["override_conflicts"], ["payment_state_mismatch"])
        self.assertEqual(
            by_id[unpaid.pk]["allowed_override_codes"],
            ["payment_state_mismatch", "historical_import"],
        )
        self.assertFalse(by_id[paid.pk]["requires_override"])
        self.assertEqual(by_id[paid.pk]["override_conflicts"], [])
        self.assertEqual(by_id[paid.pk]["allowed_override_codes"], [])
        self.assertTrue(by_id[shipped_unpaid.pk]["requires_override"])
        self.assertEqual(
            by_id[shipped_unpaid.pk]["override_conflicts"],
            ["terminal_order", "payment_state_mismatch"],
        )
        self.assertEqual(
            by_id[shipped_unpaid.pk]["allowed_override_codes"],
            ["historical_import"],
        )

    def test_order_candidate_review_must_belong_to_requested_client(self):
        other_client = IgClient.get_or_create_for_sender("candidate-other-client")
        other_review = IgPaymentConfirmationReview.objects.create(
            client=other_client,
            dedupe_key="candidate-other-review",
            watermark_message_id=811,
        )
        web_client = Client()
        web_client.force_login(self.actor)

        response = web_client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.client.pk, "review_id": other_review.pk},
            secure=True,
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_candidate_override_contract_matches_link_action_acceptance(self):
        review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="candidate-action-parity",
            watermark_message_id=812,
            evidence={"order_draft": {"quoted_total": "1350.00"}},
        )
        record_review_decision(
            review,
            actor=self.actor,
            decision="manager_verified",
            verification_scope="full_payment",
            confirmed_amount="1350.00",
        )
        review.refresh_from_db()
        order = self._order(total="1350.00")
        web_client = Client()
        web_client.force_login(self.actor)
        action_url = reverse(
            "management_bot_payment_review_action_api",
            args=[review.pk],
        )

        rejected = web_client.post(
            action_url,
            {"action": "link_order", "order_identifier": order.order_number},
            secure=True,
        )
        accepted = web_client.post(
            action_url,
            {
                "action": "link_order",
                "order_identifier": order.order_number,
                "override_code": "payment_state_mismatch",
                "override_reason": "Менеджер звірив ручну оплату з випискою",
            },
            secure=True,
        )

        self.assertEqual(rejected.status_code, 409)
        self.assertIn("стан оплати", rejected.json()["error"].lower())
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()["order_id"], order.pk)

    def test_clients_api_includes_requested_client_outside_current_filter(self):
        self.client.stage = IgClient.Stage.COLD
        self.client.save(update_fields=["stage"])
        web_client = Client()
        web_client.force_login(self.actor)

        without_deep_link = web_client.get(
            reverse("management_bot_clients_api"),
            {"view": "active"},
            secure=True,
        ).json()
        with_deep_link = web_client.get(
            reverse("management_bot_clients_api"),
            {"view": "active", "client_id": self.client.pk},
            secure=True,
        ).json()

        self.assertNotIn(self.client.pk, [row["id"] for row in without_deep_link["clients"]])
        self.assertIn(self.client.pk, [row["id"] for row in with_deep_link["clients"]])

    def test_repeat_materialization_key_hashes_the_complete_evidence_tuple(self):
        from management.services.ig_commercial_episodes import start_repeat_episode

        common = [int("6" * 13 + f"{index:05d}") for index in range(1, 20)]
        first = start_repeat_episode(
            self.client,
            repeat_kind="reorder",
            evidence_message_ids=common + [int("7" * 18)],
            confidence=Decimal("0.91"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-contract-v1-a",
        )
        second = start_repeat_episode(
            self.client,
            repeat_kind="reorder",
            evidence_message_ids=common + [int("8" * 18)],
            confidence=Decimal("0.92"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-contract-v1-b",
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(first.materialization_key, second.materialization_key)

    def test_replaying_old_repeat_signal_never_rewinds_current_episode(self):
        from management.services.ig_commercial_episodes import start_repeat_episode

        first = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[601],
            confidence=Decimal("0.92"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )
        second = start_repeat_episode(
            self.client,
            repeat_kind="gift",
            evidence_message_ids=[602],
            confidence=Decimal("0.93"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )

        replay = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[601],
            confidence=Decimal("0.92"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )

        self.client.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(replay.pk, first.pk)
        self.assertIsNone(first.open_slot)
        self.assertEqual(self.client.current_commercial_episode_id, second.pk)

    def test_repeat_reanalysis_reuses_episode_across_prompt_and_evidence_expansion(self):
        from management.services.ig_commercial_episodes import start_repeat_episode

        first = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[701],
            confidence=Decimal("0.91"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )
        prompt_upgrade = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[701],
            confidence=Decimal("0.94"),
            analysis_model="gemini-test-2",
            analysis_prompt_version="repeat-v2",
        )
        expanded = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[701, 702],
            confidence=Decimal("0.95"),
            analysis_model="gemini-test-2",
            analysis_prompt_version="repeat-v2",
        )

        self.assertEqual(prompt_upgrade.pk, first.pk)
        self.assertEqual(expanded.pk, first.pk)
        self.assertEqual(self.client.commercial_episodes.count(), 1)

    def test_new_repeat_evidence_after_deal_started_opens_a_new_episode(self):
        from management.services.ig_commercial_episodes import (
            ensure_episode_for_deal,
            start_repeat_episode,
        )

        first = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[751],
            confidence=Decimal("0.92"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )
        deal = IgDeal.objects.create(client=self.client, amount=Decimal("790.00"))
        attached = ensure_episode_for_deal(deal)
        self.assertEqual(attached.pk, first.pk)

        second = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[751, 752],
            confidence=Decimal("0.96"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v2",
        )

        self.assertNotEqual(second.pk, first.pk)
        self.assertEqual(second.repeat_evidence_message_ids, [751, 752])
        self.assertEqual(self.client.commercial_episodes.count(), 2)

    def test_attribution_only_order_is_in_analysis_truth_and_schedules_reanalysis(self):
        from management.services.bot_conversation_analysis import _required_truth_state
        from management.services.ig_order_links import create_order_attribution

        InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Де моє замовлення?",
        )
        order = self._order(status="new", ttn="20450000000021")
        create_order_attribution(
            order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            created_by=self.actor,
        )

        truth = _required_truth_state(self.client)
        self.assertEqual([row["order_id"] for row in truth["order_truth"]], [order.pk])

        with patch(
            "management.services.bot_conversation_analysis.schedule_client_truth_analysis"
        ) as schedule:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = "ship"
                order.save(update_fields=["status"])

        self.assertEqual(schedule.call_count, 1)
        self.assertEqual(schedule.call_args.args[0].pk, self.client.pk)
        self.assertEqual(schedule.call_args.kwargs["trigger"], "order_truth")

    def test_instagram_owned_order_delete_is_blocked_before_dangling_links(self):
        from management.services.ig_order_links import create_order_attribution

        order = self._order()
        create_order_attribution(
            order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            created_by=self.actor,
        )

        with self.assertRaisesMessage(ValueError, "Instagram"):
            with transaction.atomic():
                order.delete()
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_review_without_deal_cannot_claim_order_owned_by_other_deal(self):
        from management.services.ig_order_links import link_existing_order_to_review

        other_client = IgClient.get_or_create_for_sender("episode-other-owner")
        order = self._order()
        IgDeal.objects.create(client=other_client, order=order, amount=order.total_sum)
        review = self._confirmed_review(key="episode-review-no-deal")

        with self.assertRaisesMessage(ValueError, "іншого Instagram-клієнта"):
            link_existing_order_to_review(
                review,
                order_identifier=order.order_number,
                actor=self.actor,
            )

    def test_review_episode_cannot_link_order_owned_by_another_episode(self):
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_review,
        )
        from management.services.ig_order_links import link_existing_order_to_review

        first_review = self._confirmed_review(key="episode-owner-first")
        first_episode = ensure_episode_for_review(first_review)
        order = self._order()
        order.payment_status = "paid"
        order.save(update_fields=["payment_status"])
        bind_episode_order(first_episode, order, creation_mode="linked_existing")
        second_review = self._confirmed_review(key="episode-owner-second")
        second_episode = ensure_episode_for_review(second_review)
        self.assertNotEqual(first_episode.pk, second_episode.pk)

        with self.assertRaisesMessage(ValueError, "іншому комерційному епізоду"):
            link_existing_order_to_review(
                second_review,
                order_identifier=order.order_number,
                actor=self.actor,
            )

    def test_current_payment_truth_uses_commercial_chronology_not_group_order(self):
        from django.utils import timezone
        from management.services.ig_commercial_episodes import client_payment_truth_state

        stale_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="stale-orphan-review",
            watermark_message_id=10,
            evidence={"order_draft": {"quoted_total": "315.00"}},
        )
        IgPaymentConfirmationReview.objects.filter(pk=stale_review.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        current_deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("1280.00"),
            requested_payment_amount=Decimal("1280.00"),
        )

        state = client_payment_truth_state(self.client)

        self.assertEqual(state["current_payment_truth"]["deal_id"], current_deal.pk)
        self.assertEqual(state["current_payment_truth"]["order_total"], "1280.00")

    def test_delayed_old_review_cannot_claim_new_repeat_episode(self):
        from management.services.ig_commercial_episodes import (
            ensure_episode_for_review,
            start_repeat_episode,
        )

        old_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="delayed-old-review",
            watermark_message_id=100,
            evidence={"order_draft": {"quoted_total": "790.00"}},
        )
        repeat = start_repeat_episode(
            self.client,
            repeat_kind="explicit_more",
            evidence_message_ids=[500],
            confidence=Decimal("0.97"),
            analysis_model="gemini-test",
            analysis_prompt_version="repeat-v1",
        )

        historical = ensure_episode_for_review(old_review)

        repeat.refresh_from_db()
        self.client.refresh_from_db()
        self.assertNotEqual(historical.pk, repeat.pk)
        self.assertEqual(historical.primary_payment_review_id, old_review.pk)
        self.assertIsNone(historical.open_slot)
        self.assertIsNone(repeat.primary_payment_review_id)
        self.assertEqual(repeat.open_slot, 1)
        self.assertEqual(self.client.current_commercial_episode_id, repeat.pk)


class CommercialEpisodeMigrationContractTests(TestCase):
    def test_superseded_review_detection_is_safe_for_pre_0109_migration_state(self):
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        self.assertFalse(migration._is_superseded_review(SimpleNamespace(status="pending")))
        self.assertTrue(migration._is_superseded_review(SimpleNamespace(status="superseded")))
        self.assertFalse(
            migration._has_canonical_supersession(SimpleNamespace(status="superseded"))
        )

    def test_schema_and_data_rollout_are_separate_for_mariadb_recovery(self):
        schema = import_module("management.migrations.0106_ig_commercial_episodes")
        data = import_module("management.migrations.0107_ig_commercial_episode_backfill")

        self.assertFalse(any(type(op).__name__ == "RunPython" for op in schema.Migration.operations))
        self.assertTrue(all(type(op).__name__ == "RunPython" for op in data.Migration.operations))

    def test_trigger_creation_drops_partial_triggers_before_recreating(self):
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        class Connection:
            vendor = "mysql"

        class SchemaEditor:
            connection = Connection()

            def __init__(self):
                self.sql = []

            def execute(self, sql):
                self.sql.append(sql)

        editor = SchemaEditor()
        migration.create_append_only_triggers(None, editor)

        self.assertEqual(
            editor.sql[:2],
            [
                "DROP TRIGGER IF EXISTS ig_episode_event_no_update",
                "DROP TRIGGER IF EXISTS ig_episode_event_no_delete",
            ],
        )

    def test_backfill_links_historical_order_and_keeps_latest_unresolved_cycle_current(self):
        from django.apps import apps
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgDeal,
            IgOrderAttribution,
            IgPaymentConfirmationReview,
        )

        client = IgClient.get_or_create_for_sender("episode-migration-backfill")
        order = Order.objects.create(
            full_name="Олена",
            phone="380501112233",
            total_sum=Decimal("790.00"),
        )
        historical_deal = IgDeal.objects.create(
            client=client,
            order=order,
            amount=Decimal("790.00"),
        )
        historical_review = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=historical_deal,
            order=order,
            dedupe_key="episode-migration-historical-review",
            watermark_message_id=100,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=client,
            deal=historical_deal,
            payment_review=historical_review,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        active_deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("1280.00"),
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_commercial_episodes(apps, None)
        migration.backfill_commercial_episodes(apps, None)

        order_episode = IgCommercialEpisode.objects.get(intended_order=order)
        active_episode = IgCommercialEpisode.objects.get(deal=active_deal)
        client.refresh_from_db()
        self.assertEqual(order_episode.order_attribution_id, attribution.pk)
        self.assertEqual(order_episode.primary_payment_review_id, historical_review.pk)
        self.assertIsNone(order_episode.open_slot)
        self.assertEqual(active_episode.open_slot, 1)
        self.assertEqual(client.current_commercial_episode_id, active_episode.pk)
        self.assertEqual(IgCommercialEpisode.objects.filter(client=client).count(), 2)
        self.assertTrue(order_episode.product_snapshot == [] or isinstance(order_episode.product_snapshot, list))
        self.assertEqual(order_episode.price_snapshot["actual_order_total"], "790.00")
        self.assertEqual(order_episode.events.get().event_type, "historical_backfill")

    def test_backfill_uses_real_chronology_and_terminal_rows_never_become_current(self):
        from django.apps import apps
        from django.utils import timezone
        from management.ig_bot_models import IgCommercialEpisode, IgDeal, IgPaymentConfirmationReview

        client = IgClient.get_or_create_for_sender("episode-migration-chronology")
        old_deal = IgDeal.objects.create(client=client, amount=Decimal("700.00"))
        old_review = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=old_deal,
            status=IgPaymentConfirmationReview.Status.CANCELLED,
            dedupe_key="episode-old-cancelled",
        )
        IgPaymentConfirmationReview.objects.filter(pk=old_review.pk).update(
            created_at=timezone.now() - timedelta(days=4)
        )
        IgDeal.objects.filter(pk=old_deal.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )
        current = IgDeal.objects.create(client=client, amount=Decimal("1280.00"))
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_commercial_episodes(apps, None)

        old_episode = IgCommercialEpisode.objects.get(deal=old_deal)
        current_episode = IgCommercialEpisode.objects.get(deal=current)
        client.refresh_from_db()
        self.assertLess(old_episode.sequence, current_episode.sequence)
        self.assertEqual(old_episode.state, IgCommercialEpisode.State.CANCELLED)
        self.assertIsNotNone(old_episode.closed_at)
        self.assertIsNone(old_episode.open_slot)
        self.assertEqual(current_episode.open_slot, 1)
        self.assertEqual(client.current_commercial_episode_id, current_episode.pk)

    def test_backfill_fails_before_writes_when_one_deal_maps_to_two_orders(self):
        from django.apps import apps
        from management.ig_bot_models import IgCommercialEpisode, IgDeal, IgOrderAttribution

        client = IgClient.get_or_create_for_sender("episode-migration-conflict")
        deal = IgDeal.objects.create(client=client, amount=Decimal("1000.00"))
        first = Order.objects.create(full_name="A", phone="380501112231", total_sum=500)
        second = Order.objects.create(full_name="B", phone="380501112232", total_sum=500)
        IgOrderAttribution.objects.create(
            order=first,
            client=client,
            deal=deal,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        IgOrderAttribution.objects.create(
            order=second,
            client=client,
            deal=deal,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        with self.assertRaisesMessage(RuntimeError, "multiple deals, attributions"):
            migration.backfill_commercial_episodes(apps, None)
        self.assertFalse(IgCommercialEpisode.objects.filter(client=client).exists())

    def test_backfill_uses_authoritative_projection_instead_of_stale_deal_mirror(self):
        from django.apps import apps
        from management.ig_bot_models import IgCommercialEpisode, IgDeal, IgPaymentProjection

        client = IgClient.get_or_create_for_sender("episode-migration-provider-projection")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("1280.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("1280.00"),
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=client,
            truth=IgDeal.PaymentTruth.REFUNDED,
            gross_amount=Decimal("1280.00"),
            refunded_amount=Decimal("1280.00"),
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_commercial_episodes(apps, None)

        episode = IgCommercialEpisode.objects.get(deal=deal)
        client.refresh_from_db()
        self.assertEqual(episode.state, IgCommercialEpisode.State.CANCELLED)
        self.assertEqual(episode.payment_snapshot["provider_truth"], IgDeal.PaymentTruth.REFUNDED)
        self.assertEqual(episode.payment_snapshot["provider_confirmed_amount"], "0.00")
        self.assertEqual(episode.payment_snapshot["provider_refunded_amount"], "1280.00")
        self.assertIsNone(episode.open_slot)
        self.assertIsNone(client.current_commercial_episode_id)

    def test_backfill_terminal_projection_overrides_nonterminal_order_and_keeps_reconciliation(self):
        from django.apps import apps
        from management.ig_bot_models import IgCommercialEpisode, IgDeal, IgPaymentProjection

        client = IgClient.get_or_create_for_sender("episode-migration-terminal-order")
        order = Order.objects.create(
            full_name="Legacy",
            phone="380501234567",
            total_sum=Decimal("1280.00"),
            status="new",
        )
        deal = IgDeal.objects.create(
            client=client,
            order=order,
            amount=Decimal("1280.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("1280.00"),
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=client,
            truth=IgDeal.PaymentTruth.REVERSED,
            gross_amount=Decimal("1280.00"),
            needs_reconciliation=True,
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_commercial_episodes(apps, None)

        episode = IgCommercialEpisode.objects.get(deal=deal)
        self.assertEqual(episode.state, IgCommercialEpisode.State.CANCELLED)
        self.assertEqual(episode.outcome, IgDeal.PaymentTruth.REVERSED)
        self.assertTrue(episode.payment_snapshot["needs_reconciliation"])
        self.assertIsNone(episode.open_slot)

    def test_backfill_scopes_manager_decision_to_selected_primary_review(self):
        from django.apps import apps
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgDeal,
            IgPaymentConfirmationReview,
            IgPaymentReviewDecision,
        )

        actor = get_user_model().objects.create_user(username="migration-review-actor")
        client = IgClient.get_or_create_for_sender("episode-migration-review-scope")
        deal = IgDeal.objects.create(client=client, amount=Decimal("1280.00"))
        older = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="migration-older-review",
        )
        IgPaymentReviewDecision.objects.create(
            review=older,
            client=client,
            actor=actor,
            decision="manager_verified",
            verification_source="manager",
            verification_scope="prepayment",
            confirmed_amount="315.00",
            currency="UAH",
            actor_source="management_user",
            actor_external_id=str(actor.pk),
        )
        newer = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="migration-newer-review",
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_commercial_episodes(apps, None)

        episode = IgCommercialEpisode.objects.get(deal=deal)
        self.assertEqual(episode.primary_payment_review_id, newer.pk)
        self.assertEqual(episode.payment_snapshot["manager_truth"], "")
        self.assertEqual(episode.payment_snapshot["manager_confirmed_amount"], "")
        remaining = migration._unmaterialized_component_counts(apps, "default")
        self.assertEqual(remaining["reviews"], 0)
        self.assertEqual(
            migration.backfill_until_quiescent(apps, None, max_passes=3),
            {"deals": 0, "reviews": 0, "attributions": 0},
        )

    def test_backfill_prefers_canonical_review_over_later_superseded_reviews(self):
        from django.apps import apps
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgOrderAttribution,
            IgPaymentConfirmationReview,
        )

        client = IgClient.get_or_create_for_sender("episode-migration-superseded-review")
        order = Order.objects.create(
            full_name="Canonical review",
            phone="380501112299",
            total_sum=Decimal("1280.00"),
        )
        older = IgPaymentConfirmationReview.objects.create(
            client=client,
            order=order,
            dedupe_key="migration-superseded-older",
        )
        canonical = IgPaymentConfirmationReview.objects.create(
            client=client,
            order=order,
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            dedupe_key="migration-canonical-review",
        )
        later = IgPaymentConfirmationReview.objects.create(
            client=client,
            order=order,
            status=IgPaymentConfirmationReview.Status.SUPERSEDED,
            superseded_by=canonical,
            dedupe_key="migration-superseded-later",
        )
        IgPaymentConfirmationReview.objects.filter(pk=older.pk).update(
            status=IgPaymentConfirmationReview.Status.SUPERSEDED,
            superseded_by=canonical,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=client,
            payment_review=canonical,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=None,
            materialization_key="migration-superseded-older-episode",
            primary_payment_review=older,
            state=IgCommercialEpisode.State.LOST,
        )
        canonical_episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=2,
            open_slot=None,
            materialization_key="migration-canonical-episode",
            primary_payment_review=canonical,
            order_attribution=attribution,
            intended_order=order,
            state=IgCommercialEpisode.State.ORDER_CREATED,
        )
        later_episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=3,
            open_slot=None,
            materialization_key="migration-superseded-later-episode",
            primary_payment_review=later,
            state=IgCommercialEpisode.State.LOST,
        )
        client.current_commercial_episode = later_episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        remaining = migration.backfill_until_quiescent(apps, None, max_passes=3)

        canonical_episode.refresh_from_db()
        self.assertEqual(canonical_episode.primary_payment_review_id, canonical.pk)
        self.assertEqual(canonical_episode.order_attribution_id, attribution.pk)
        self.assertEqual(canonical_episode.intended_order_id, order.pk)
        client.refresh_from_db()
        self.assertIsNone(client.current_commercial_episode_id)
        self.assertEqual(remaining, {"deals": 0, "reviews": 0, "attributions": 0})

    def test_backfill_never_reopens_orphaned_superseded_review(self):
        from django.apps import apps
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgPaymentConfirmationReview,
        )

        client = IgClient.get_or_create_for_sender("episode-migration-orphaned-superseded")
        duplicate = IgPaymentConfirmationReview.objects.create(
            client=client,
            status=IgPaymentConfirmationReview.Status.SUPERSEDED,
            dedupe_key="migration-orphaned-superseded",
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_until_quiescent(apps, None, max_passes=3)

        episode = IgCommercialEpisode.objects.get(primary_payment_review=duplicate)
        client.refresh_from_db()
        self.assertEqual(episode.state, IgCommercialEpisode.State.LOST)
        self.assertEqual(episode.outcome, "superseded_duplicate_payment_review")
        self.assertIsNotNone(episode.closed_at)
        self.assertIsNone(episode.open_slot)
        self.assertIsNone(client.current_commercial_episode_id)

    def test_backfill_validates_existing_relation_collisions_before_any_new_write(self):
        from django.apps import apps
        from management.ig_bot_models import IgCommercialEpisode, IgDeal, IgPaymentConfirmationReview

        earlier = IgClient.get_or_create_for_sender("episode-migration-preflight-earlier")
        earlier_deal = IgDeal.objects.create(client=earlier, amount=Decimal("700.00"))
        conflicted = IgClient.get_or_create_for_sender("episode-migration-preflight-conflicted")
        conflicted_deal = IgDeal.objects.create(client=conflicted, amount=Decimal("900.00"))
        conflicted_review = IgPaymentConfirmationReview.objects.create(
            client=conflicted,
            deal=conflicted_deal,
            dedupe_key="episode-migration-preflight-review",
        )
        existing_deal_episode = IgCommercialEpisode.objects.create(
            client=conflicted,
            sequence=1,
            open_slot=None,
            materialization_key="preflight-existing-deal",
            deal=conflicted_deal,
        )
        existing_review_episode = IgCommercialEpisode.objects.create(
            client=conflicted,
            sequence=2,
            open_slot=None,
            materialization_key="preflight-existing-review",
            primary_payment_review=conflicted_review,
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        with self.assertRaises(RuntimeError) as captured:
            migration.backfill_commercial_episodes(apps, None)

        message = str(captured.exception)
        self.assertIn("already spans multiple", message)
        self.assertIn(f"client_id={conflicted.pk}", message)
        self.assertIn(f"d:{conflicted_deal.pk}", message)
        self.assertIn(f"r:{conflicted_review.pk}", message)
        self.assertIn("expected_relations=", message)
        self.assertIn(
            f"matching_episode_ids={sorted([existing_deal_episode.pk, existing_review_episode.pk])}",
            message,
        )
        self.assertFalse(IgCommercialEpisode.objects.filter(deal=earlier_deal).exists())

    def test_superseded_duplicate_episode_stays_separate_across_repeated_backfill(self):
        from django.apps import apps
        from django.utils import timezone
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgOrderAttribution,
            IgPaymentConfirmationReview,
        )
        from management.services.ig_payment_review import reconcile_duplicate_payment_review

        client = IgClient.get_or_create_for_sender("episode-migration-superseded-duplicate")
        order = Order.objects.create(
            full_name="Historical buyer",
            phone="380501234567",
            total_sum=Decimal("1760.00"),
            status="done",
        )
        claim_anchor = "c" * 64
        canonical_review = IgPaymentConfirmationReview.objects.create(
            client=client,
            order=order,
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            dedupe_key="episode-migration-canonical-review",
            watermark_message_id=1136,
            evidence={"claim_anchor": claim_anchor},
            confirmed_at=timezone.now(),
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=client,
            payment_review=canonical_review,
            creation_mode="manager_review",
            payment_source="manager_verified",
        )
        canonical_episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=None,
            materialization_key="episode-migration-canonical-episode",
            state=IgCommercialEpisode.State.FULFILLED,
            outcome="fulfilled",
            primary_payment_review=canonical_review,
            order_attribution=attribution,
            intended_order=order,
            closed_at=timezone.now(),
        )
        duplicate_review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key="episode-migration-duplicate-review",
            watermark_message_id=1141,
            evidence={"claim_anchor": claim_anchor},
        )
        duplicate_episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=2,
            open_slot=1,
            materialization_key="episode-migration-duplicate-episode",
            primary_payment_review=duplicate_review,
        )
        client.current_commercial_episode = duplicate_episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])

        reconciled = reconcile_duplicate_payment_review(duplicate_review)

        self.assertEqual(reconciled.pk, canonical_review.pk)
        duplicate_review.refresh_from_db()
        duplicate_episode.refresh_from_db()
        client.refresh_from_db()
        self.assertEqual(duplicate_review.status, IgPaymentConfirmationReview.Status.SUPERSEDED)
        self.assertEqual(duplicate_review.superseded_by_id, canonical_review.pk)
        self.assertEqual(duplicate_review.order_id, order.pk)
        self.assertEqual(duplicate_episode.state, IgCommercialEpisode.State.LOST)
        self.assertEqual(duplicate_episode.outcome, "superseded_duplicate_payment_review")
        self.assertIsNone(client.current_commercial_episode_id)

        migration = import_module("management.migrations.0106_ig_commercial_episodes")
        migration.backfill_commercial_episodes(apps, None)
        migration.backfill_commercial_episodes(apps, None)

        canonical_episode.refresh_from_db()
        duplicate_episode.refresh_from_db()
        duplicate_review.refresh_from_db()
        client.refresh_from_db()
        self.assertEqual(IgCommercialEpisode.objects.filter(client=client).count(), 2)
        self.assertEqual(canonical_episode.state, IgCommercialEpisode.State.FULFILLED)
        self.assertEqual(canonical_episode.primary_payment_review_id, canonical_review.pk)
        self.assertEqual(canonical_episode.order_attribution_id, attribution.pk)
        self.assertEqual(canonical_episode.intended_order_id, order.pk)
        self.assertEqual(duplicate_episode.state, IgCommercialEpisode.State.LOST)
        self.assertEqual(duplicate_episode.outcome, "superseded_duplicate_payment_review")
        self.assertEqual(duplicate_episode.primary_payment_review_id, duplicate_review.pk)
        self.assertIsNone(duplicate_episode.intended_order_id)
        self.assertEqual(duplicate_episode.closed_at, duplicate_review.superseded_at)
        self.assertIsNone(client.current_commercial_episode_id)

    def test_reconcile_promotes_late_review_connected_to_existing_deal_episode(self):
        from django.apps import apps
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgDeal,
            IgPaymentConfirmationReview,
        )

        client = IgClient.get_or_create_for_sender("episode-migration-late-review")
        deal = IgDeal.objects.create(client=client, amount=Decimal("1280.00"))
        older = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="migration-review-before-restart",
        )
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        migration.backfill_until_quiescent(apps, None, max_passes=3)
        episode = IgCommercialEpisode.objects.get(deal=deal)
        self.assertEqual(episode.primary_payment_review_id, older.pk)

        newer = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="migration-review-during-release-window",
        )

        remaining = migration.backfill_until_quiescent(apps, None, max_passes=3)

        episode.refresh_from_db()
        self.assertEqual(IgCommercialEpisode.objects.filter(deal=deal).count(), 1)
        self.assertEqual(episode.primary_payment_review_id, newer.pk)
        self.assertEqual(remaining, {"deals": 0, "reviews": 0, "attributions": 0})


class RepeatIntentNormalizationTests(TestCase):
    def test_repeat_intent_is_evidence_bound_and_normalized(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "high_intent",
                "score_band": "high_intent",
                "purchase_probability": 0.9,
                "confidence": 0.9,
                "evidence": [
                    {"message_id": 77, "quote": "хочу ще одну", "claim": "repeat"},
                ],
                "repeat_intent": {
                    "kind": "explicit_more",
                    "confidence": 0.95,
                    "evidence_message_ids": [77, 999],
                },
            },
            {77: {"role": "user", "text": "Мені сподобалось, хочу ще одну"}},
            verified_payment=False,
        )

        self.assertEqual(normalized["repeat_intent"]["kind"], "explicit_more")
        self.assertEqual(normalized["repeat_intent"]["evidence_message_ids"], [77])
        self.assertEqual(str(normalized["repeat_intent"]["confidence"]), "0.9500")

    def test_repeat_intent_rejects_manager_evidence_unknown_kind_and_low_confidence(self):
        from management.services.bot_conversation_analysis import _normalize

        base = {
            "interaction_type": "high_intent",
            "score_band": "high_intent",
            "purchase_probability": 0.8,
            "confidence": 0.8,
        }
        cases = [
            (
                {"kind": "reorder", "confidence": 0.95, "evidence_message_ids": [1]},
                {1: {"role": "manager", "text": "Клієнт хоче ще"}},
            ),
            (
                {"kind": "made_up", "confidence": 0.95, "evidence_message_ids": [2]},
                {2: {"role": "user", "text": "Хочу ще"}},
            ),
            (
                {"kind": "gift", "confidence": 0.49, "evidence_message_ids": [3]},
                {3: {"role": "user", "text": "Хочу на подарунок"}},
            ),
        ]

        for repeat_intent, by_id in cases:
            with self.subTest(repeat_intent=repeat_intent):
                normalized = _normalize(
                    {**base, "repeat_intent": repeat_intent},
                    by_id,
                    verified_payment=False,
                )
                self.assertEqual(normalized["repeat_intent"], {})

    def test_repeat_intent_rejects_exchange_or_return_evidence(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "support_complaint",
                "score_band": "exploring",
                "purchase_probability": 0.2,
                "confidence": 0.9,
                "repeat_intent": {
                    "kind": "reorder",
                    "confidence": 0.96,
                    "evidence_message_ids": [931],
                },
            },
            {
                931: {
                    "role": "user",
                    "text": "Футболка вже у вас. Є розміри для заміни?",
                }
            },
            verified_payment=True,
        )

        self.assertEqual(normalized["repeat_intent"], {})

    def test_repeat_intent_accepts_explicit_request_for_one_more_item(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "product_interest",
                "score_band": "qualified",
                "purchase_probability": 0.8,
                "confidence": 0.9,
                "repeat_intent": {
                    "kind": "explicit_more",
                    "confidence": 0.94,
                    "evidence_message_ids": [950],
                },
            },
            {950: {"role": "user", "text": "Хочу замовити ще одну футболку"}},
            verified_payment=True,
        )

        self.assertEqual(normalized["repeat_intent"]["kind"], "explicit_more")

    def test_custom_print_requires_explicit_user_manufacturing_evidence(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "custom_print",
                "score_band": "qualified",
                "purchase_probability": 0.7,
                "confidence": 0.9,
            },
            {960: {"role": "user", "text": "Принт ось цей, розмір M"}},
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], "information_only")
        self.assertIn("custom_print_user_evidence_missing", normalized["uncertainties"])

    def test_custom_print_accepts_explicit_user_manufacturing_evidence(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "custom_print",
                "score_band": "qualified",
                "purchase_probability": 0.7,
                "confidence": 0.9,
            },
            {
                961: {
                    "role": "user",
                    "text": "Можете надрукувати мій власний дизайн на футболці?",
                }
            },
            verified_payment=False,
        )

        self.assertEqual(normalized["interaction_type"], "custom_print")

    def test_verified_payment_does_not_overwrite_conversation_potential(self):
        from management.services.bot_conversation_analysis import _normalize

        normalized = _normalize(
            {
                "interaction_type": "information_only",
                "score_band": "exploring",
                "purchase_probability": 0.31,
                "confidence": 0.72,
                "evidence": [
                    {"message_id": 91, "quote": "Я тільки питаю", "claim": "interest"},
                ],
            },
            {91: {"role": "user", "text": "Я тільки питаю про розмір"}},
            verified_payment=True,
        )

        self.assertEqual(normalized["score_band"], "exploring")
        self.assertEqual(normalized["interaction_type"], "information_only")
        self.assertEqual(str(normalized["purchase_probability"]), "0.3100")
        self.assertEqual(str(normalized["confidence"]), "0.7200")
