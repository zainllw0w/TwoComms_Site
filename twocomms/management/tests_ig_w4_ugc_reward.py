"""W4 regression tests for manager-verified UGC promo rewards."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgClient,
    IgOrderCustomerEvent,
    IgUgcReward,
    IgUgcRewardDelivery,
    InstagramBotMessage,
)
from management.services.ig_order_assignments import link_order_to_client
from management.services.ig_order_fulfillment import _message
from management.services.ig_ugc_rewards import (
    UgcRewardConflict,
    award_ugc_reward,
)
from orders.models import Order
from storefront.models import PromoCode


class DeliveredReviewCopyTests(SimpleTestCase):
    def test_review_copy_asks_about_the_order_before_the_verified_reward(self):
        order = type("OrderStub", (), {"order_number": "TWC-UGC-01", "pk": 1})()
        expected = {
            "uk": ("якістю", "посадкою", "після перевірки", "10%"),
            "ru": ("качеством", "посадкой", "после проверки", "10%"),
            "en": ("quality", "fit", "after we verify", "10%"),
        }

        for locale, phrases in expected.items():
            with self.subTest(locale=locale):
                text = _message("delivered_review", locale, order, "").lower()
                for phrase in phrases:
                    self.assertIn(phrase, text)
                self.assertLess(text.index(phrases[0]), text.index("10%"))


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
)
class UgcRewardTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="ugc-reviewer",
            email="ugc-reviewer@example.com",
            password="test-password",
        )
        self.ig_client = IgClient.get_or_create_for_sender("ugc-client")
        self.delivered_at = timezone.now() - timedelta(hours=1)
        self.order = Order.objects.create(
            order_number="TWC-UGC-02",
            full_name="UGC Buyer",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            total_sum=Decimal("1000.00"),
            payment_status="paid",
            status="done",
            tracking_number="20450000000002",
            tracking_status_code=9,
            tracking_provider_event_at=self.delivered_at,
            tracking_terminal_at=self.delivered_at,
        )
        self.assignment = link_order_to_client(
            self.order,
            client=self.ig_client,
            actor=self.actor,
        )
        self.evidence = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="Відмітила вас у сторіс",
            attachments="https://cdn.example/story-proof.jpg",
            status=InstagramBotMessage.Status.DONE,
            provider_created_at=self.delivered_at + timedelta(minutes=1),
        )

    def _open_service_case(self, suffix):
        from management.ig_bot_models import IgPostSaleCase

        complaint = InstagramBotMessage.objects.create(
            sender_id=self.ig_client.igsid,
            client=self.ig_client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу повернути замовлення",
            source="webhook",
            mid=f"ugc-delivered-open-service-case-{suffix}",
            provider_created_at=timezone.now(),
        )
        return IgPostSaleCase.objects.create(
            client=self.ig_client,
            source_message=complaint,
            case_type=IgPostSaleCase.CaseType.RETURN,
            status=IgPostSaleCase.Status.OPEN,
        )

    def test_verified_evidence_issues_one_bounded_single_use_code(self):
        before = timezone.now()

        reward, created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
            review_note="Story mark checked in Direct",
        )

        self.assertTrue(created)
        self.assertEqual(reward.assignment_id, self.assignment.id)
        self.assertEqual(reward.assignment_version, self.assignment.version)
        self.assertEqual(reward.reviewed_by_id, self.actor.id)
        self.assertIsNotNone(reward.reviewed_at)
        self.assertEqual(reward.evidence_message_id, self.evidence.id)
        self.assertEqual(reward.review_note, "Story mark checked in Direct")
        promo = reward.promo_code
        self.assertEqual(promo.discount_type, "percentage")
        self.assertEqual(promo.discount_value, Decimal("10.00"))
        self.assertEqual(promo.max_uses, 1)
        self.assertFalse(promo.one_time_per_user)
        self.assertTrue(promo.guest_redeemable)
        self.assertTrue(promo.is_guest_ugc_capability())
        self.assertTrue(promo.is_active)
        self.assertGreaterEqual(promo.valid_from, before)
        self.assertGreaterEqual(promo.valid_until, before + timedelta(days=89))
        self.assertLessEqual(promo.valid_until, before + timedelta(days=91))
        delivery = IgUgcRewardDelivery.objects.get(reward=reward)
        self.assertIn(promo.code, delivery.message_snapshot)
        self.assertIn("90", delivery.message_snapshot)

    def test_manual_reward_enqueues_outbox_without_synchronous_customer_send(self):
        outbound_roles = (
            InstagramBotMessage.Role.MODEL,
            InstagramBotMessage.Role.MANAGER,
        )
        outbound_before = InstagramBotMessage.objects.filter(
            client=self.ig_client,
            role__in=outbound_roles,
        ).count()
        customer_events_before = IgOrderCustomerEvent.objects.filter(
            client=self.ig_client,
        ).count()

        award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )

        self.assertEqual(
            InstagramBotMessage.objects.filter(
                client=self.ig_client,
                role__in=outbound_roles,
            ).count(),
            outbound_before,
        )
        self.assertEqual(
            IgOrderCustomerEvent.objects.filter(client=self.ig_client).count(),
            customer_events_before,
        )
        self.assertEqual(
            IgUgcRewardDelivery.objects.filter(client=self.ig_client).count(),
            1,
        )

    def test_order_linked_outbox_failure_rolls_back_reward_promo_and_lifetime(self):
        from unittest.mock import patch

        from management.ig_bot_models import IgUgcRewardLifetime

        with patch.object(
            IgUgcRewardDelivery.objects,
            "get_or_create",
            side_effect=RuntimeError("forced order-linked outbox failure"),
        ), self.assertRaisesRegex(RuntimeError, "forced order-linked outbox failure"):
            award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )

        self.assertFalse(IgUgcReward.objects.exists())
        self.assertFalse(IgUgcRewardLifetime.objects.exists())
        self.assertFalse(IgUgcRewardDelivery.objects.exists())
        self.assertFalse(PromoCode.objects.exists())

    def test_open_service_case_blocks_delivered_order_award_without_side_effects(self):
        from management.ig_bot_models import IgUgcRewardLifetime

        self._open_service_case("new-award")

        with self.assertRaisesRegex(UgcRewardConflict, "активне звернення"):
            award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )

        self.assertFalse(IgUgcReward.objects.exists())
        self.assertFalse(PromoCode.objects.exists())
        self.assertFalse(IgUgcRewardDelivery.objects.exists())
        self.assertFalse(IgUgcRewardLifetime.objects.exists())

    def test_existing_reward_replay_survives_late_open_service_case(self):
        from management.ig_bot_models import IgUgcRewardLifetime

        first, first_created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )
        self._open_service_case("idempotent-replay")

        try:
            replay, replay_created = award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )
        except UgcRewardConflict as exc:
            self.fail(f"Idempotent reward replay was blocked: {exc}")

        self.assertTrue(first_created)
        self.assertFalse(replay_created)
        self.assertEqual(replay.pk, first.pk)
        self.assertEqual(replay.promo_code_id, first.promo_code_id)
        self.assertEqual(IgUgcReward.objects.count(), 1)
        self.assertEqual(PromoCode.objects.count(), 1)
        self.assertEqual(IgUgcRewardDelivery.objects.count(), 1)
        self.assertEqual(IgUgcRewardLifetime.objects.count(), 1)

    def test_same_evidence_is_idempotent_and_never_creates_a_second_code(self):
        first, first_created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )

        second, second_created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(PromoCode.objects.count(), 1)
        self.assertEqual(IgUgcReward.objects.count(), 1)

    def test_same_instagram_url_ignores_tracking_query_for_idempotency(self):
        first, first_created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_url="https://www.instagram.com/p/UGC123/?utm_source=share",
        )

        second, second_created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_url="https://www.instagram.com/p/UGC123/?igsh=tracking-token",
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(PromoCode.objects.count(), 1)

    def test_different_evidence_cannot_issue_a_second_code_for_the_same_order(self):
        award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )

        with self.assertRaises(UgcRewardConflict):
            award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_url="https://www.instagram.com/stories/twocomms/123456789/",
            )

        self.assertEqual(PromoCode.objects.count(), 1)

    def test_unassigned_order_is_rejected(self):
        other_order = Order.objects.create(
            order_number="TWC-UGC-UNASSIGNED",
            full_name="Other Buyer",
            phone="380501112244",
            city="Kyiv",
            np_office="Branch 2",
            total_sum=Decimal("900.00"),
            payment_status="paid",
            status="done",
        )

        with self.assertRaises(UgcRewardConflict):
            award_ugc_reward(
                client=self.ig_client,
                order=other_order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )

    def test_reward_is_rejected_until_the_assigned_order_is_done(self):
        for status in ("new", "prep", "ship", "cancelled"):
            with self.subTest(status=status):
                self.order.status = status
                self.order.save(update_fields=["status"])

                with self.assertRaisesMessage(
                    UgcRewardConflict,
                    "Нагороду можна видати лише після підтвердженого отримання замовлення.",
                ):
                    award_ugc_reward(
                        client=self.ig_client,
                        order=self.order,
                        actor=self.actor,
                        evidence_message_id=self.evidence.pk,
                    )

        self.assertFalse(IgUgcReward.objects.exists())
        self.assertFalse(PromoCode.objects.exists())

    def test_manual_done_without_carrier_delivery_is_rejected(self):
        self.order.tracking_status_code = 7
        self.order.tracking_terminal_at = None
        self.order.save(
            update_fields=["tracking_status_code", "tracking_terminal_at"]
        )

        with self.assertRaisesMessage(
            UgcRewardConflict,
            "Нагороду можна видати лише після підтвердженого отримання замовлення.",
        ):
            award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )

        self.assertFalse(IgUgcReward.objects.exists())
        self.assertFalse(PromoCode.objects.exists())

    def test_direct_evidence_before_provider_delivery_event_is_rejected(self):
        self.evidence.provider_created_at = self.delivered_at - timedelta(seconds=1)
        self.evidence.save(update_fields=["provider_created_at"])

        with self.assertRaisesMessage(
            UgcRewardConflict,
            "Доказ Direct має бути створений після підтвердженого отримання замовлення.",
        ):
            award_ugc_reward(
                client=self.ig_client,
                order=self.order,
                actor=self.actor,
                evidence_message_id=self.evidence.pk,
            )

        self.assertFalse(IgUgcReward.objects.exists())
        self.assertFalse(PromoCode.objects.exists())

    def test_provider_delivery_time_wins_over_delayed_terminal_polling_time(self):
        provider_delivery_at = timezone.now() - timedelta(hours=2)
        self.order.tracking_provider_event_at = provider_delivery_at
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=["tracking_provider_event_at", "tracking_terminal_at"]
        )
        self.evidence.provider_created_at = provider_delivery_at + timedelta(minutes=5)
        self.evidence.save(update_fields=["provider_created_at"])

        reward, created = award_ugc_reward(
            client=self.ig_client,
            order=self.order,
            actor=self.actor,
            evidence_message_id=self.evidence.pk,
        )

        self.assertTrue(created)
        self.assertEqual(reward.evidence_message_id, self.evidence.pk)

    def test_staff_endpoint_is_idempotent_and_client_detail_exposes_reward(self):
        self.client.force_login(self.actor)
        url = reverse(
            "management_bot_client_ugc_reward_api",
            args=[self.ig_client.pk],
        )
        payload = {
            "order_id": self.order.pk,
            "evidence_message_id": self.evidence.pk,
            "review_note": "Checked",
        }

        first = self.client.post(url, payload)
        second = self.client.post(url, payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_json = first.json()
        second_json = second.json()
        self.assertTrue(first_json["created"])
        self.assertFalse(second_json["created"])
        self.assertEqual(
            first_json["reward"]["promo_code"],
            second_json["reward"]["promo_code"],
        )

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.ig_client.pk])
        )
        self.assertEqual(detail.status_code, 200)
        ugc = detail.json()["ugc_rewards"]
        self.assertFalse(ugc["reward_eligible"])
        self.assertEqual(ugc["eligibility_reason"], "already_rewarded")
        self.assertEqual(ugc["items"][0]["order_id"], self.order.id)
        self.assertFalse(ugc["items"][0]["reward_eligible"])
        self.assertEqual(
            ugc["items"][0]["eligibility_reason"],
            "already_rewarded",
        )
        self.assertEqual(
            ugc["items"][0]["promo_code"],
            first_json["reward"]["promo_code"],
        )
        self.assertEqual(ugc["award_url"], url)

    def test_detail_marks_delivered_unrewarded_order_as_reward_eligible(self):
        self.client.force_login(self.actor)

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.ig_client.pk])
        )

        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertTrue(payload["ugc_rewards"]["reward_eligible"])
        self.assertEqual(
            payload["ugc_rewards"]["eligibility_reason"],
            "delivered_order_eligible",
        )
        assignment = payload["orders"]["assignments"][0]
        self.assertTrue(assignment["reward_eligible"])
        self.assertEqual(
            assignment["eligibility_reason"],
            "delivered_order_eligible",
        )

    def test_dashboard_contains_the_manager_ugc_action(self):
        self.client.force_login(self.actor)

        response = self.client.get(reverse("management_bot"))

        self.assertContains(response, "renderUgcRewards")
        self.assertContains(response, "Підтвердити UGC і видати -10%")
        self.assertContains(response, "item.order.status==='done'")
