from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.ig_bot_models import IgClient, IgOrderCustomerEvent
from management.models import InstagramBotSettings
from management.services.ig_order_assignments import link_order_to_client, unlink_order_from_client


@override_settings(ROOT_URLCONF="twocomms.urls")
class IgOrderFulfillmentTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from orders.models import Order

        self.manager = get_user_model().objects.create_user("fulfillment-manager", password="x", is_staff=True)
        self.client.force_login(self.manager)
        InstagramBotSettings.objects.update_or_create(
            pk=1,
            defaults={"is_enabled": True},
        )
        self.ig_client = IgClient.get_or_create_for_sender("fulfillment-locale-client")
        self.ig_client.language = "en"
        self.ig_client.last_message_at = timezone.now()
        self.ig_client.save(update_fields=["language", "last_message_at", "updated_at"])
        self.order = Order.objects.create(
            order_number="TWC-FULFILLMENT-01",
            full_name="Website buyer",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            total_sum=Decimal("790.00"),
            payment_status="paid",
            status="ship",
            tracking_number="20400000000000",
        )

    def test_materializes_english_ttn_once_and_delivers(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        assignment = link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        def send_with_evidence(_settings, _igsid, _message, **kwargs):
            kwargs["provider_message_callback"]("mid.fulfillment.english")
            return True, "", ""

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=send_with_evidence,
        ) as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)
        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.SENT)
        self.assertIn("Your order", event.message_snapshot)
        self.assertIn("20400000000000", event.message_snapshot)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(result["sent"], 1)
        reconcile_order_customer_events(order_id=self.order.pk, send=True)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(assignment.version, 1)

    def test_unlink_cancels_pending_event_and_relink_uses_new_version_key(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        assignment = link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED)
        unlink_order_from_client(
            self.order,
            client=self.ig_client,
            actor=self.manager,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Wrong customer selected",
        )
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        event.refresh_from_db()
        self.assertEqual(event.state, IgOrderCustomerEvent.State.CANCELLED)
        second_client = IgClient.get_or_create_for_sender("fulfillment-relink-client")
        relinked = link_order_to_client(self.order, client=second_client, actor=self.manager)
        self.assertEqual(relinked.version, 3)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        self.assertEqual(IgOrderCustomerEvent.objects.filter(order=self.order, kind="ttn_assigned").count(), 2)

    def test_legacy_backfill_does_not_materialize_historical_notifications(self):
        from management.ig_bot_models import IgOrderAssignment
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        self.order.status = "done"
        self.order.save(update_fields=["status"])
        link_order_to_client(
            self.order,
            client=self.ig_client,
            source=IgOrderAssignment.Source.LEGACY_ATTRIBUTION,
            reason_code="legacy_attribution",
            reason="Imported by migration 0119",
        )

        result = reconcile_order_customer_events(order_id=self.order.pk, send=False)

        self.assertEqual(result["created"], 0)
        self.assertFalse(IgOrderCustomerEvent.objects.filter(order=self.order).exists())

    def test_opted_in_after_opt_out_remains_eligible(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        now = timezone.now()
        self.ig_client.opted_out_at = now - timedelta(hours=2)
        self.ig_client.opted_in_at = now - timedelta(hours=1)
        self.ig_client.save(update_fields=["opted_out_at", "opted_in_at", "updated_at"])
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=lambda _settings, _igsid, _message, **kwargs: (
                kwargs["provider_message_callback"]("mid.fulfillment.optin")
                or (True, "", "")
            ),
        ) as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        self.assertEqual(result["sent"], 1)
        send.assert_called_once()

    def test_blocked_client_event_is_cancelled_without_send(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        self.ig_client.is_blocked = True
        self.ig_client.save(update_fields=["is_blocked", "updated_at"])
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        with patch("management.services.instagram_bot.send_text") as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(order=self.order)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.CANCELLED)
        self.assertEqual(result["cancelled"], 1)
        send.assert_not_called()

    def test_closed_response_window_routes_event_to_manager_review(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        self.ig_client.last_message_at = timezone.now() - timedelta(hours=24)
        self.ig_client.save(update_fields=["last_message_at", "updated_at"])
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        with patch("management.services.instagram_bot.send_text") as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(order=self.order)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.MANAGER_REVIEW)
        self.assertEqual(result["manager_review"], 1)
        self.assertIn("response window", event.last_error)
        send.assert_not_called()

    def test_delivery_uses_final_assignment_boundary_and_persists_provider_id(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        def send_with_evidence(_settings, _igsid, _message, **kwargs):
            self.assertIn("permission_boundary_factory", kwargs)
            callback = kwargs.get("provider_message_callback")
            self.assertIsNotNone(callback)
            callback("mid.fulfillment.1")
            with kwargs["permission_boundary_factory"]() as allowed:
                self.assertTrue(allowed)
            return True, "", ""

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=send_with_evidence,
        ):
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(order=self.order)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(event.provider_message_id, "mid.fulfillment.1")

    def test_http_success_without_provider_message_id_is_ambiguous(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        with patch(
            "management.services.instagram_bot.send_text",
            return_value=(True, "", ""),
        ):
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(order=self.order)
        self.assertEqual(result["ambiguous"], 1)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.AMBIGUOUS)
        self.assertEqual(event.provider_message_id, "")
        self.assertIn("message_id", event.last_error)

    def test_partial_delivery_keeps_provider_ids_and_is_ambiguous(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        def send_partial(_settings, _igsid, _message, **kwargs):
            kwargs["provider_message_callback"]("mid.fulfillment.partial")
            return False, "unknown", "partial delivery"

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=send_partial,
        ):
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(order=self.order)
        self.assertEqual(result["ambiguous"], 1)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.AMBIGUOUS)
        self.assertEqual(event.provider_message_id, "mid.fulfillment.partial")

    def test_materialization_limit_cannot_starve_older_assignments(self):
        from orders.models import Order
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        second_client = IgClient.get_or_create_for_sender("fulfillment-older-client")
        second_client.last_message_at = timezone.now()
        second_client.save(update_fields=["last_message_at", "updated_at"])
        older_order = Order.objects.create(
            order_number="TWC-FULFILLMENT-OLDER",
            full_name="Older website buyer",
            phone="380509998877",
            total_sum=Decimal("790.00"),
            payment_status="paid",
            status="ship",
            tracking_number="20400000000001",
        )
        link_order_to_client(older_order, client=second_client, actor=self.manager)
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        reconcile_order_customer_events(limit=1, send=False)
        reconcile_order_customer_events(limit=1, send=False)

        self.assertTrue(IgOrderCustomerEvent.objects.filter(order=older_order).exists())
        self.assertTrue(IgOrderCustomerEvent.objects.filter(order=self.order).exists())

    def test_done_order_creates_localized_review_request(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        self.order.status = "done"
        self.order.save(update_fields=["status"])
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.DELIVERED_REVIEW)
        self.assertIn("Thank you", event.message_snapshot)
        self.assertEqual(event.locale, "en")
        self.assertFalse(
            IgOrderCustomerEvent.objects.filter(
                order=self.order,
                kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
            ).exists()
        )

    def test_done_transition_cancels_stale_pending_ttn_before_review_send(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        stale_ttn = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
        )
        self.assertEqual(stale_ttn.state, IgOrderCustomerEvent.State.PENDING)

        self.order.status = "done"
        self.order.save(update_fields=["status"])

        def send_with_evidence(_settings, _igsid, message, **kwargs):
            self.assertIn("Thank you", message)
            kwargs["provider_message_callback"]("mid.fulfillment.review")
            return True, "", ""

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=send_with_evidence,
        ) as send:
            result = reconcile_order_customer_events(
                order_id=self.order.pk,
                send=True,
            )

        stale_ttn.refresh_from_db()
        review = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.DELIVERED_REVIEW,
        )
        self.assertEqual(stale_ttn.state, IgOrderCustomerEvent.State.CANCELLED)
        self.assertIn("superseded", stale_ttn.last_error)
        self.assertEqual(review.state, IgOrderCustomerEvent.State.SENT)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["cancelled"], 1)
        send.assert_called_once()

    def test_tracking_replacement_cancels_old_pending_ttn_and_materializes_current_one(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        stale_ttn = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
            payload__tracking_number="20400000000000",
        )

        self.order.tracking_number = "20400000000001"
        self.order.save(update_fields=["tracking_number"])

        result = reconcile_order_customer_events(order_id=self.order.pk, send=False)

        stale_ttn.refresh_from_db()
        current_ttn = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
            payload__tracking_number="20400000000001",
        )
        self.assertEqual(stale_ttn.state, IgOrderCustomerEvent.State.CANCELLED)
        self.assertIn("superseded", stale_ttn.last_error)
        self.assertEqual(current_ttn.state, IgOrderCustomerEvent.State.PENDING)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["cancelled"], 1)

    def test_cancelled_transition_cancels_pending_ttn_without_send(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        stale_ttn = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
        )

        self.order.status = "cancelled"
        self.order.save(update_fields=["status"])

        with patch("management.services.instagram_bot.send_text") as send:
            result = reconcile_order_customer_events(
                order_id=self.order.pk,
                send=True,
            )

        stale_ttn.refresh_from_db()
        self.assertEqual(stale_ttn.state, IgOrderCustomerEvent.State.CANCELLED)
        self.assertIn("superseded", stale_ttn.last_error)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["cancelled"], 1)
        send.assert_not_called()

    def test_send_boundary_cancels_ttn_when_order_becomes_done_after_claim(self):
        from orders.models import Order
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)

        def transition_before_meta_io(_settings, _igsid, _message, **kwargs):
            Order.objects.filter(pk=self.order.pk).update(status="done")
            with kwargs["permission_boundary_factory"]() as permitted:
                self.assertFalse(permitted)
            return False, "cancelled", "final eligibility check refused delivery"

        with patch(
            "management.services.instagram_bot.send_text",
            side_effect=transition_before_meta_io,
        ) as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(
            order=self.order,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
        )
        self.assertEqual(event.state, IgOrderCustomerEvent.State.CANCELLED)
        self.assertIn("superseded", event.last_error)
        self.assertEqual(result["cancelled"], 1)
        send.assert_called_once()

    def test_no_send_materializes_without_consuming_an_attempt(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        result = reconcile_order_customer_events(order_id=self.order.pk, send=False)
        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED)

        self.assertEqual(result["created"], 1)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.PENDING)
        self.assertEqual(event.attempts, 0)

    def test_expired_processing_lease_becomes_ambiguous_without_resend(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events
        from django.utils import timezone

        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        reconcile_order_customer_events(order_id=self.order.pk, send=False)
        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED)
        event.state = IgOrderCustomerEvent.State.PROCESSING
        event.lease_token = "abandoned"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.save(update_fields=["state", "lease_token", "lease_expires_at"])

        with patch("management.services.instagram_bot.send_text") as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event.refresh_from_db()
        self.assertEqual(event.state, IgOrderCustomerEvent.State.AMBIGUOUS)
        self.assertEqual(result["ambiguous"], 1)
        send.assert_not_called()

    def test_global_stop_prevents_customer_delivery(self):
        from management.services.ig_order_fulfillment import reconcile_order_customer_events

        InstagramBotSettings.objects.filter(pk=1).update(is_enabled=False)
        link_order_to_client(self.order, client=self.ig_client, actor=self.manager)
        with patch("management.services.instagram_bot.send_text") as send:
            result = reconcile_order_customer_events(order_id=self.order.pk, send=True)

        event = IgOrderCustomerEvent.objects.get(kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED)
        self.assertEqual(event.state, IgOrderCustomerEvent.State.PENDING)
        self.assertEqual(result["paused"], 1)
        send.assert_not_called()

    def test_order_transition_wakes_after_commit_but_creation_does_not(self):
        from orders.models import Order

        with patch(
            "management.services.ig_order_fulfillment.kick_order_fulfillment"
        ) as kick:
            Order.objects.create(
                full_name="Unassigned website buyer",
                phone="380509998877",
                total_sum=Decimal("790.00"),
            )
            self.assertEqual(kick.call_count, 0)

            self.order.shipment_status = "in_transit"
            with self.captureOnCommitCallbacks(execute=True):
                self.order.save(update_fields=["shipment_status"])

        kick.assert_called_once_with(self.order.pk)

    def test_manual_order_context_links_without_creating_attribution(self):
        token = signing.dumps({"client_id": self.ig_client.pk}, salt="storefront.manual-order.ig-client")
        response = self.client.post(
            reverse("manual_order_create"),
            data={
                "full_name": "Manual Instagram buyer",
                "phone": "0501112233",
                "delivery_method": "manual",
                "city": "Київ",
                "np_office": "Відділення 1",
                "payment_preset": "cod",
                "sale_source": "Instagram",
                "items": [{"kind": "custom", "title": "Футболка", "unit_price": "790", "qty": 1, "size": "M", "color_name": "Чорний"}],
                "ig_client_id": str(self.ig_client.pk),
                "ig_client_token": token,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        from management.ig_bot_models import IgOrderAssignment, IgOrderAttribution
        from orders.models import Order

        created = Order.objects.get(order_number=response.json()["order_number"])
        assignment = IgOrderAssignment.objects.get(order=created)
        self.assertEqual(assignment.client_id, self.ig_client.pk)
        self.assertEqual(assignment.source, IgOrderAssignment.Source.MANAGER_CREATED)
        self.assertEqual(created.items.count(), 1)
        self.assertFalse(IgOrderAttribution.objects.filter(order=created).exists())
        self.assertEqual(created.payment_status, "unpaid")
