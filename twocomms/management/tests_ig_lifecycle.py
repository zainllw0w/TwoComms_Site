import hashlib
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import (
    IgLifecycleEvent,
    IgOrderAssignment,
    IgOrderAssignmentEvent,
    IgPaymentProjection,
)
from management.models import (
    IgBotNotification,
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgOrderAttribution,
    InstagramBotSettings,
    InstagramBotMessage,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from management.services.ig_lifecycle import (
    PAYMENT_NOT_VERIFIED_ERROR,
    PROVIDER_BOUNDARY_CLAIM_MARKER,
    STALE_ASSIGNMENT_ERROR,
    _lifecycle_message_key,
    _message,
    dispatch_due_lifecycle_events,
    dispatch_lifecycle_event,
    ensure_lifecycle_event,
)
from management.services.ig_order_assignments import (
    link_order_to_client,
    unlink_order_from_client,
)
from orders.models import Order, PaymentAttempt


class InstagramLifecycleTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender(
            "ig-lifecycle-test",
            defaults={"language": "uk"},
        )
        self.client.language = "uk"
        self.client.last_message_at = timezone.now()
        self.client.save(update_fields=["language", "last_message_at", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("950.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        self.order = Order.objects.create(
            full_name="Іван Іванов",
            phone="+380501112233",
            email="buyer@example.com",
            city="Київ",
            np_office="Відділення №1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        self.attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"ig-lifecycle-attempt").hexdigest(),
            full_name=self.order.full_name,
            phone=self.order.phone,
            email=self.order.email,
            city=self.order.city,
            np_office=self.order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "items": []},
            gross_amount=self.order.total_sum,
            payable_amount=self.order.total_sum,
            payment_amount=self.order.total_sum,
            order=self.order,
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=self.order.total_sum,
            quoted_total=self.order.total_sum,
            requested_payment_amount=self.order.total_sum,
            items_digest="a" * 64,
        )
        self.proposal.payment_attempt = self.attempt
        self.proposal.save(update_fields=["payment_attempt", "updated_at"])
        self.attribution = IgOrderAttribution.objects.create(
            order=self.order,
            client=self.client,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        self.payment_projection = IgPaymentProjection.objects.create(
            deal=self.deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=self.order.total_sum,
            paid_at=self.deal.paid_at,
        )
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled", "updated_at"])

    def _event(self, kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED, payload=None):
        link_order_to_client(self.order, client=self.client)
        event, created = ensure_lifecycle_event(
            self.order,
            kind,
            payload=payload or {"attempt_id": self.attempt.pk, "amount": "950.00"},
        )
        self.assertTrue(created)
        return event

    def test_provider_io_boundary_uses_existing_lifecycle_message_fields(self):
        self.assertNotIn(
            "provider_io_started_at",
            {field.name for field in IgLifecycleEvent._meta.fields},
        )

    def _dispatch_real_provider_outcome(self, event, *provider_outcomes):
        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        with (
            patch(
                "management.services.ig_reply_boundary.reply_execution_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.ig_reply_boundary.customer_send_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.instagram_bot._provider_account_id",
                return_value="ig-account",
            ),
            patch(
                "management.services.instagram_bot.get_page_token",
                return_value="page-token",
            ),
            patch(
                "management.services.instagram_bot._provider_http",
                side_effect=list(provider_outcomes),
            ) as provider_http,
            patch("management.services.instagram_bot.notify_manager"),
        ):
            first_state = dispatch_lifecycle_event(event.pk)
            second_state = dispatch_lifecycle_event(event.pk)

        return first_state, second_state, provider_http.call_count

    def test_payment_copy_contains_phone_city_office_and_order_number(self):
        event = self._event()
        message = _message(event)

        for value in (
            self.order.full_name,
            self.order.phone,
            self.order.city,
            self.order.np_office,
            self.order.order_number,
        ):
            self.assertIn(value, message)

    def test_message_snapshot_survives_order_edits_after_materialization(self):
        event = self._event()
        original = _message(event)

        self.order.full_name = "Змінений Одержувач"
        self.order.phone = "+380000000000"
        self.order.city = "Львів"
        self.order.np_office = "Відділення №99"
        self.order.save(
            update_fields=["full_name", "phone", "city", "np_office"]
        )
        event = IgLifecycleEvent.objects.select_related("order").get(pk=event.pk)

        self.assertEqual(_message(event), original)
        self.assertIn("Іван Іванов", original)
        self.assertNotIn("Змінений Одержувач", _message(event))

    def test_verified_payment_producer_freezes_message_snapshot(self):
        from management.services.ig_checkout_payment import bind_verified_payment

        event = bind_verified_payment(self.attempt.pk, self.order)

        self.assertIn("message_snapshot", event.payload)
        original = _message(event)
        self.order.full_name = "Змінений Одержувач"
        self.order.phone = "+380000000000"
        self.order.city = "Львів"
        self.order.np_office = "Відділення №99"
        self.order.save(
            update_fields=["full_name", "phone", "city", "np_office"]
        )
        event = IgLifecycleEvent.objects.select_related("order").get(pk=event.pk)

        self.assertEqual(_message(event), original)
        self.assertIn("Іван Іванов", original)
        self.assertNotIn("Змінений Одержувач", _message(event))

    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-wrong-recipient"),
    )
    def test_reassigned_order_cancels_event_before_provider_call(self, send_text):
        assignment = link_order_to_client(self.order, client=self.client)
        event = self._event()
        cleared = unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Order belongs to another Instagram customer.",
        )
        other_client = IgClient.get_or_create_for_sender("ig-lifecycle-other")
        link_order_to_client(
            self.order,
            client=other_client,
            expected_version=cleared.version,
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(
            event.last_error,
            "order assignment no longer belongs to lifecycle client",
        )
        send_text.assert_not_called()

    def test_materialization_skips_order_assigned_to_another_client(self):
        assignment = link_order_to_client(self.order, client=self.client)
        cleared = unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Order belongs to another Instagram customer.",
        )
        other_client = IgClient.get_or_create_for_sender(
            "ig-lifecycle-materialization-other"
        )
        link_order_to_client(
            self.order,
            client=other_client,
            expected_version=cleared.version,
        )

        event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )

        self.assertIsNone(event)
        self.assertFalse(created)

    def test_materialization_fails_closed_when_assignment_history_lost_projection(
        self,
    ):
        IgOrderAssignmentEvent.objects.create(
            assignment_id=987654321,
            order=self.order,
            kind=IgOrderAssignmentEvent.Kind.LINKED,
            to_client=self.client,
            actor_source=IgOrderAssignmentEvent.ActorSource.AUTOMATION,
            assignment_source=IgOrderAssignment.Source.PROVIDER_AUTO,
            assignment_version=1,
            snapshot={"client_id": self.client.pk},
        )

        event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )

        self.assertIsNone(event)
        self.assertFalse(created)

    def test_materialization_fails_closed_without_assignment_or_history(self):
        event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )

        self.assertIsNone(event)
        self.assertFalse(created)

    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-missing-owner"),
    )
    def test_dispatch_fails_closed_without_assignment_or_history(self, send_text):
        event = self._event()
        assignment = IgOrderAssignment.objects.get(order=self.order)
        unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Assignment was intentionally cleared for this regression.",
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, STALE_ASSIGNMENT_ERROR)
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-raced-recipient"),
    )
    def test_assignment_is_revalidated_immediately_before_provider_send(
        self,
        send_text,
        reply_execution_boundary,
        customer_send_boundary,
    ):
        assignment = link_order_to_client(self.order, client=self.client)
        event = self._event()
        other_client = IgClient.get_or_create_for_sender("ig-lifecycle-raced-other")

        @contextmanager
        def reassign_after_claim(*_args, **_kwargs):
            cleared = unlink_order_from_client(
                self.order,
                client=self.client,
                expected_version=assignment.version,
                reason_code="manager_correction",
                reason="Order belongs to another Instagram customer.",
            )
            link_order_to_client(
                self.order,
                client=other_client,
                expected_version=cleared.version,
            )
            yield True

        @contextmanager
        def permit_customer_send(*_args, **_kwargs):
            yield True

        reply_execution_boundary.side_effect = reassign_after_claim
        customer_send_boundary.side_effect = permit_customer_send

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, STALE_ASSIGNMENT_ERROR)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_relinked_same_client_cannot_reactivate_old_assignment_generation(
        self,
        send_text,
    ):
        event = self._event()
        assignment = IgOrderAssignment.objects.get(order=self.order)
        self.assertEqual(event.payload["assignment_id"], assignment.pk)
        self.assertEqual(event.payload["assignment_version"], assignment.version)

        cleared = unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Rebuild assignment generation.",
        )
        relinked = link_order_to_client(
            self.order,
            client=self.client,
            expected_version=cleared.version,
        )
        self.assertGreater(relinked.version, assignment.version)

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, STALE_ASSIGNMENT_ERROR)
        send_text.assert_not_called()

    def test_cancelled_event_gets_a_new_generation_after_truth_is_restored(self):
        event = self._event()
        event.state = IgLifecycleEvent.State.CANCELLED
        event.last_error = "payment_not_verified"
        event.save(update_fields=["state", "last_error", "updated_at"])

        replacement, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )

        self.assertTrue(created)
        self.assertNotEqual(replacement.pk, event.pk)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertTrue(replacement.event_key.startswith(f"{event.event_key}:retry:"))

    def test_permanent_opt_out_cancellation_never_creates_retry_generation(self):
        event = self._event()
        self.client.opted_out_at = timezone.now()
        self.client.save(update_fields=["opted_out_at", "updated_at"])

        self.assertEqual(
            dispatch_lifecycle_event(event.pk),
            IgLifecycleEvent.State.CANCELLED,
        )
        same_event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )

        event.refresh_from_db()
        self.assertEqual(event.last_error, "opt_out")
        self.assertFalse(created)
        self.assertEqual(same_event.pk, event.pk)
        self.assertFalse(
            IgLifecycleEvent.objects.filter(
                event_key__startswith=f"{event.event_key}:retry:"
            ).exists()
        )

    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-reversed-payment"),
    )
    def test_payment_truth_is_revalidated_immediately_before_provider_send(
        self,
        send_text,
        reply_execution_boundary,
        customer_send_boundary,
    ):
        event = self._event()

        @contextmanager
        def reverse_payment_after_claim(*_args, **_kwargs):
            self.payment_projection.truth = IgDeal.PaymentTruth.REVERSED
            self.payment_projection.save(update_fields=["truth", "updated_at"])
            yield True

        @contextmanager
        def permit_customer_send(*_args, **_kwargs):
            yield True

        reply_execution_boundary.side_effect = reverse_payment_after_claim
        customer_send_boundary.side_effect = permit_customer_send

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "payment_not_verified")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_every_lifecycle_kind_requires_verified_payment_truth(self, send_text):
        cases = (
            (
                IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
                {"attempt_id": self.attempt.pk, "amount": "950.00"},
            ),
            (
                IgLifecycleEvent.Kind.TTN_CREATED,
                {"tracking_number": "20450000000009"},
            ),
            (
                IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
                {"status_code": "9", "status": "delivered"},
            ),
        )

        for kind, payload in cases:
            with self.subTest(kind=kind):
                self.payment_projection.truth = IgDeal.PaymentTruth.CONFIRMED
                self.payment_projection.save(update_fields=["truth", "updated_at"])
                if kind != IgLifecycleEvent.Kind.PAYMENT_VERIFIED:
                    self.order.tracking_number = "20450000000009"
                if kind == IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED:
                    self.order.status = "done"
                    self.order.tracking_status_code = 9
                    self.order.tracking_terminal_at = timezone.now()
                self.order.save()
                event = self._event(kind, payload=payload)

                self.payment_projection.truth = IgDeal.PaymentTruth.REVERSED
                self.payment_projection.save(update_fields=["truth", "updated_at"])

                self.assertEqual(
                    dispatch_lifecycle_event(event.pk),
                    IgLifecycleEvent.State.CANCELLED,
                )
                event.refresh_from_db()
                self.assertEqual(event.last_error, "payment_not_verified")

        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(
            False,
            "cancelled",
            "permission epoch changed before Meta request",
            "",
        ),
    )
    def test_permission_epoch_change_is_deferred_without_spending_attempt(
        self,
        send_text,
        notify_manager,
    ):
        event = self._event()

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.WAITING_WINDOW)
        self.assertEqual(event.state, IgLifecycleEvent.State.WAITING_WINDOW)
        self.assertEqual(event.last_error, "permission_epoch_changed")
        self.assertEqual(event.attempts, 0)
        send_text.assert_called_once()
        notify_manager.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_opted_out_client_cancels_event_before_provider_call(self, send_text):
        self.client.opted_out_at = timezone.now()
        self.client.save(update_fields=["opted_out_at", "updated_at"])
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.CANCELLED)
        send_text.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(event.last_error, "opt_out")
        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "disabled")
        self.assertEqual(channel["error"], "opt_out")

    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot.send_text")
    def test_permission_transition_pending_is_deferred_before_provider_call(
        self,
        send_text,
        reply_execution_boundary,
    ):
        from management.services.ig_reply_boundary import ReplyPermission

        event = self._event()

        @contextmanager
        def transition_pending(*_args, **_kwargs):
            yield ReplyPermission(
                settings_id=self.settings.pk,
                settings_epoch=0,
                client_id=self.client.pk,
                client_epoch=0,
                allowed=False,
                reason="permission_transition_pending",
            )

        reply_execution_boundary.side_effect = transition_pending

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.WAITING_WINDOW)
        self.assertEqual(event.last_error, "permission_transition_pending")
        self.assertEqual(event.attempts, 0)
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch("management.services.instagram_bot._provider_http")
    def test_global_pause_after_capture_is_deferred_before_marker_and_http(
        self,
        provider_http,
        _page_token,
        _account_id,
        customer_send_boundary,
        reply_execution_boundary,
    ):
        from management.services.ig_reply_boundary import ReplyPermission

        event = self._event()

        @contextmanager
        def initially_allowed(*_args, **_kwargs):
            yield ReplyPermission(
                settings_id=self.settings.pk,
                settings_epoch=0,
                client_id=self.client.pk,
                client_epoch=0,
                allowed=True,
            )

        @contextmanager
        def paused_at_send(*_args, **_kwargs):
            yield ReplyPermission(
                settings_id=self.settings.pk,
                settings_epoch=1,
                client_id=self.client.pk,
                client_epoch=0,
                allowed=False,
                reason="global_reply_paused",
            )

        reply_execution_boundary.side_effect = initially_allowed
        customer_send_boundary.side_effect = paused_at_send

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.WAITING_WINDOW)
        self.assertEqual(event.last_error, "global_reply_paused")
        self.assertEqual(event.attempts, 0)
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                synthetic_event_key__startswith="ig-lifecycle:"
            ).exists()
        )
        provider_http.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_client_pause_is_deferred_without_spending_attempt(self, send_text):
        self.client.bot_paused = True
        self.client.save(update_fields=["bot_paused", "updated_at"])
        event = self._event()

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.WAITING_WINDOW)
        self.assertEqual(event.last_error, "client_paused")
        self.assertEqual(event.attempts, 0)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_permission_deferral_escalates_after_twelve_hours(
        self,
        send_text,
        notify_manager,
    ):
        self.settings.is_enabled = False
        self.settings.save(update_fields=["is_enabled"])
        event = self._event()
        IgLifecycleEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(hours=13)
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.MANAGER_REVIEW)
        self.assertEqual(event.state, IgLifecycleEvent.State.MANAGER_REVIEW)
        self.assertEqual(event.last_error, "global_reply_paused")
        self.assertEqual(event.attempts, 0)
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
                reason=f"ig_lifecycle:{event.event_key}",
            ).count(),
            1,
        )
        send_text.assert_not_called()
        notify_manager.assert_called_once()
        self.assertEqual(
            notify_manager.call_args.kwargs["dedupe_key"],
            f"ig-lifecycle:permission:{event.event_key}",
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_closed_window_is_terminal_manager_review_without_replay(
        self,
        send_text,
        notify_manager,
    ):
        self.client.last_message_at = None
        self.client.save(update_fields=["last_message_at", "updated_at"])
        event = self._event()

        self.assertEqual(
            dispatch_lifecycle_event(event.pk),
            IgLifecycleEvent.State.MANAGER_REVIEW,
        )
        task = IgFollowUpTask.objects.get(
            client=self.client,
            deal=self.deal,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason=f"ig_lifecycle:{event.event_key}",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.PENDING)
        self.assertIn(self.order.order_number, task.message_text)
        self.assertEqual(IgFollowUpTask.objects.filter(reason=task.reason).count(), 1)
        send_text.assert_not_called()
        notify_manager.assert_called_once()
        self.assertEqual(
            notify_manager.call_args.kwargs["dedupe_key"],
            f"ig-lifecycle:window:{event.event_key}",
        )
        self.assertIn("потребує відповіді менеджера", notify_manager.call_args.args[0])
        alert = notify_manager.call_args.args[0]
        self.assertNotIn(self.order.order_number, alert)
        self.assertIn(str(self.client.pk), alert)
        self.assertIn(str(self.deal.pk), alert)
        self.assertIn(str(event.pk), alert)
        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "pending")
        self.assertEqual(channel["error"], "standard_response_window_closed")

        self.client.last_message_at = timezone.now()
        self.client.save(update_fields=["last_message_at", "updated_at"])
        event.refresh_from_db()
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.save(update_fields=["due_at", "updated_at"])

        self.assertEqual(dispatch_due_lifecycle_events(limit=1), 0)
        self.assertEqual(
            dispatch_lifecycle_event(event.pk),
            IgLifecycleEvent.State.MANAGER_REVIEW,
        )
        self.assertEqual(IgFollowUpTask.objects.filter(reason=task.reason).count(), 1)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_pre_provider_exception_is_retryable_without_ambiguity(
        self,
        notify_manager,
    ):
        event = self._event()

        with patch(
            "management.models.InstagramBotSettings.load",
            side_effect=RuntimeError("settings unavailable before provider boundary"),
        ):
            state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PENDING)
        self.assertEqual(event.state, IgLifecycleEvent.State.PENDING)
        self.assertEqual(event.attempts, 1)
        self.assertIn("retryable:RuntimeError", event.last_error)
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                synthetic_event_key=_lifecycle_message_key(event.event_key)
            ).exists()
        )
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        notify_manager.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    def test_final_provider_boundary_reloads_response_window_before_first_http(
        self,
        notify_manager,
    ):
        event = self._event()

        @contextmanager
        def expire_window_after_initial_snapshot(*_args, **_kwargs):
            IgClient.objects.filter(pk=self.client.pk).update(
                last_message_at=timezone.now() - timedelta(hours=24),
                updated_at=timezone.now(),
            )
            yield True

        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        with self.captureOnCommitCallbacks(execute=True):
            with (
                patch(
                    "management.services.ig_reply_boundary.reply_execution_boundary",
                    side_effect=expire_window_after_initial_snapshot,
                ),
                patch(
                    "management.services.ig_reply_boundary.customer_send_boundary",
                    side_effect=permit,
                ),
                patch(
                    "management.services.instagram_bot._provider_account_id",
                    return_value="ig-account",
                ),
                patch(
                    "management.services.instagram_bot.get_page_token",
                    return_value="page-token",
                ),
                patch(
                    "management.services.instagram_bot._provider_http"
                ) as provider_http,
            ):
                state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.MANAGER_REVIEW)
        self.assertEqual(event.state, IgLifecycleEvent.State.MANAGER_REVIEW)
        self.assertEqual(event.last_error, "standard_response_window_closed")
        provider_http.assert_not_called()
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                synthetic_event_key=_lifecycle_message_key(event.event_key)
            ).exists()
        )
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).count(),
            1,
        )
        notify_manager.assert_called_once()

    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-reclaimed-before-provider-io"),
    )
    def test_expired_processing_lease_with_new_claim_marker_is_reclaimed(
        self,
        send_text,
    ):
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "dead-worker"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.attempts = 1
        event.last_error = PROVIDER_BOUNDARY_CLAIM_MARKER
        event.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "due_at",
                "attempts",
                "last_error",
                "updated_at",
            ]
        )

        result = dispatch_due_lifecycle_events(limit=1)
        event.refresh_from_db()
        self.assertEqual(result, 1)
        self.assertEqual(event.state, IgLifecycleEvent.State.SENT)
        self.assertEqual(
            event.provider_message_id,
            "meta-reclaimed-before-provider-io",
        )
        self.assertEqual(event.attempts, 2)
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        send_text.assert_called_once()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_legacy_expired_processing_without_claim_marker_is_ambiguous(
        self,
        send_text,
        notify_manager,
    ):
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "legacy-dead-worker"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.attempts = 1
        event.last_error = ""
        event.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "due_at",
                "attempts",
                "last_error",
                "updated_at",
            ]
        )

        result = dispatch_due_lifecycle_events(limit=1)

        event.refresh_from_db()
        self.assertEqual(result, 0)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertIn("legacy processing lease", event.last_error)
        send_text.assert_not_called()
        notify_manager.assert_called_once()

    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot.send_text")
    def test_stale_preflight_cannot_cancel_reclaimed_lease(
        self,
        send_text,
        reply_execution_boundary,
    ):
        event = self._event()
        preflight_calls = 0

        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        def preflight_with_reclaim(current_event):
            nonlocal preflight_calls
            preflight_calls += 1
            if preflight_calls == 2:
                IgLifecycleEvent.objects.filter(pk=current_event.pk).update(
                    state=IgLifecycleEvent.State.PROCESSING,
                    lease_token="replacement-worker",
                    lease_expires_at=timezone.now() + timedelta(minutes=5),
                    last_error="replacement worker owns the event",
                    updated_at=timezone.now(),
                )
                return "payment_not_verified"
            return ""

        reply_execution_boundary.side_effect = permit
        with patch(
            "management.services.ig_lifecycle._preflight_cancellation_reason",
            side_effect=preflight_with_reclaim,
        ):
            state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "replacement-worker")
        self.assertEqual(event.last_error, "replacement worker owns the event")
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot.send_text")
    def test_global_pause_returns_current_state_when_lease_is_reclaimed(
        self,
        send_text,
        reply_execution_boundary,
    ):
        from management.services.ig_reply_boundary import ReplyPermission

        event = self._event()

        @contextmanager
        def pause_after_claim(*_args, **_kwargs):
            IgLifecycleEvent.objects.filter(pk=event.pk).update(
                state=IgLifecycleEvent.State.PROCESSING,
                lease_token="replacement-worker",
                lease_expires_at=timezone.now() + timedelta(minutes=5),
                last_error="replacement worker owns the event",
                updated_at=timezone.now(),
            )
            yield ReplyPermission(
                settings_id=self.settings.pk,
                settings_epoch=0,
                client_id=self.client.pk,
                client_epoch=0,
                allowed=False,
                reason="global_reply_paused",
            )

        reply_execution_boundary.side_effect = pause_after_claim

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "replacement-worker")
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot.send_text")
    def test_permission_denial_cannot_cancel_reclaimed_lease(
        self,
        send_text,
        reply_execution_boundary,
    ):
        from management.services.ig_reply_boundary import ReplyPermission

        event = self._event()

        @contextmanager
        def deny_after_claim(*_args, **_kwargs):
            IgLifecycleEvent.objects.filter(pk=event.pk).update(
                state=IgLifecycleEvent.State.PROCESSING,
                lease_token="replacement-worker",
                lease_expires_at=timezone.now() + timedelta(minutes=5),
                last_error="replacement worker owns the event",
                updated_at=timezone.now(),
            )
            yield ReplyPermission(
                settings_id=self.settings.pk,
                settings_epoch=0,
                client_id=self.client.pk,
                client_epoch=0,
                allowed=False,
                reason="client_paused",
            )

        reply_execution_boundary.side_effect = deny_after_claim

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "replacement-worker")
        self.assertEqual(event.last_error, "replacement worker owns the event")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_stale_marker_check_cannot_ambiguate_reclaimed_lease(self, send_text):
        event = self._event()
        marker_checks = 0

        def marker_after_reclaim(_message):
            nonlocal marker_checks
            marker_checks += 1
            if marker_checks == 2:
                IgLifecycleEvent.objects.filter(pk=event.pk).update(
                    state=IgLifecycleEvent.State.PROCESSING,
                    lease_token="replacement-worker",
                    lease_expires_at=timezone.now() + timedelta(minutes=5),
                    last_error="replacement worker owns the event",
                    updated_at=timezone.now(),
                )
                return True
            return False

        with patch(
            "management.services.ig_lifecycle._lifecycle_message_has_provider_io",
            side_effect=marker_after_reclaim,
        ):
            state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "replacement-worker")
        self.assertEqual(event.last_error, "replacement worker owns the event")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_expired_processing_lease_with_provider_marker_is_ambiguous_without_resend(
        self,
        send_text,
        notify_manager,
    ):
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "dead-worker-after-provider-boundary"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "due_at",
                "updated_at",
            ]
        )
        InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text=_message(event),
            status=InstagramBotMessage.Status.PROCESSING,
            source="lifecycle",
            synthetic_event_key=_lifecycle_message_key(event.event_key),
            send_state="sending",
            send_started_at=timezone.now() - timedelta(minutes=2),
        )

        result = dispatch_due_lifecycle_events(limit=1)

        event.refresh_from_db()
        self.assertEqual(result, 0)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(
            event.last_error,
            "processing lease expired after provider I/O started; delivery outcome requires manager review",
        )
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(lifecycle_message.send_state, "unknown")
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        notify_manager.assert_called_once()
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot._provider_http")
    @patch("management.services.instagram_bot.send_text")
    def test_provider_marker_callback_race_escalates_without_meta_http(
        self,
        send_text,
        provider_http,
        notify_manager,
    ):
        event = self._event()

        def send_text_after_marker(*_args, **kwargs):
            InstagramBotMessage.objects.create(
                sender_id=self.client.igsid,
                client=self.client,
                role=InstagramBotMessage.Role.MODEL,
                text=_message(event),
                status=InstagramBotMessage.Status.PROCESSING,
                source="lifecycle",
                synthetic_event_key=_lifecycle_message_key(event.event_key),
                send_state="sending",
                send_started_at=timezone.now(),
            )
            self.assertFalse(kwargs["provider_io_started_callback"]())
            return False, "cancelled", "provider marker already exists", ""

        send_text.side_effect = send_text_after_marker

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                reason=f"ig_lifecycle:{event.event_key}",
            ).count(),
            1,
        )
        notify_manager.assert_called_once()
        provider_http.assert_not_called()
        send_text.assert_called_once()

    def test_reassignment_after_marker_blocks_provider_http(self):
        from management.services import ig_lifecycle

        event = self._event()
        start_provider_io = ig_lifecycle._start_lifecycle_provider_io

        def mark_then_reassign(*args, **kwargs):
            self.assertTrue(start_provider_io(*args, **kwargs))
            assignment = IgOrderAssignment.objects.get(order=self.order)
            table = connection.ops.quote_name(IgOrderAssignment._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} "
                    "SET unassigned_at = %s, version = version + 1, updated_at = %s "
                    "WHERE id = %s",
                    [timezone.now(), timezone.now(), assignment.pk],
                )
            return True

        with patch(
            "management.services.ig_lifecycle._start_lifecycle_provider_io",
            side_effect=mark_then_reassign,
        ):
            first, second, http_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"must-not-send"}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(second, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, STALE_ASSIGNMENT_ERROR)
        self.assertEqual(http_calls, 0)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(lifecycle_message.send_state, "cancelled")
        self.assertFalse(lifecycle_message.provider_message_id)

    def test_payment_reversal_after_marker_blocks_provider_http(self):
        from management.services import ig_lifecycle

        event = self._event()
        start_provider_io = ig_lifecycle._start_lifecycle_provider_io

        def mark_then_reverse_payment(*args, **kwargs):
            self.assertTrue(start_provider_io(*args, **kwargs))
            IgPaymentProjection.objects.filter(pk=self.payment_projection.pk).update(
                truth=IgDeal.PaymentTruth.REVERSED,
                updated_at=timezone.now(),
            )
            return True

        with patch(
            "management.services.ig_lifecycle._start_lifecycle_provider_io",
            side_effect=mark_then_reverse_payment,
        ):
            first, second, http_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"must-not-send"}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(second, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, PAYMENT_NOT_VERIFIED_ERROR)
        self.assertEqual(http_calls, 0)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(lifecycle_message.send_state, "cancelled")
        self.assertFalse(lifecycle_message.provider_message_id)

    def test_truth_change_between_chunks_preserves_partial_receipt(self):
        event = self._event()
        provider_calls = 0

        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        def provider_http(*_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            self.assertEqual(provider_calls, 1)
            IgPaymentProjection.objects.filter(pk=self.payment_projection.pk).update(
                truth=IgDeal.PaymentTruth.REVERSED,
                updated_at=timezone.now(),
            )
            return 200, '{"message_id":"mid-before-truth-change"}'

        with (
            patch(
                "management.services.ig_reply_boundary.reply_execution_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.ig_reply_boundary.customer_send_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.instagram_bot._provider_account_id",
                return_value="ig-account",
            ),
            patch(
                "management.services.instagram_bot.get_page_token",
                return_value="page-token",
            ),
            patch(
                "management.services.instagram_bot._provider_http",
                side_effect=provider_http,
            ),
            patch("management.services.instagram_bot.notify_manager"),
            patch(
                "management.services.ig_lifecycle._message",
                return_value="a" * 951,
            ),
        ):
            first = dispatch_lifecycle_event(event.pk)
            second = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(provider_calls, 1)
        self.assertEqual(event.provider_message_id, "mid-before-truth-change")
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-before-truth-change"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 1)
        self.assertEqual(
            lifecycle_message.delivery_failure_boundary,
            "chunk:2:provider_request_rejected",
        )

    def test_response_window_closing_between_chunks_preserves_partial_receipt(self):
        event = self._event()
        provider_calls = 0

        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        def provider_http(*_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            if provider_calls != 1:
                self.fail("response-window recheck must block the second HTTP call")
            IgClient.objects.filter(pk=self.client.pk).update(
                last_message_at=timezone.now() - timedelta(hours=24),
                updated_at=timezone.now(),
            )
            return 200, '{"message_id":"mid-before-window-close"}'

        with (
            patch(
                "management.services.ig_reply_boundary.reply_execution_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.ig_reply_boundary.customer_send_boundary",
                side_effect=permit,
            ),
            patch(
                "management.services.instagram_bot._provider_account_id",
                return_value="ig-account",
            ),
            patch(
                "management.services.instagram_bot.get_page_token",
                return_value="page-token",
            ),
            patch(
                "management.services.instagram_bot._provider_http",
                side_effect=provider_http,
            ),
            patch("management.services.instagram_bot.notify_manager"),
            patch(
                "management.services.ig_lifecycle._message",
                return_value="a" * 951,
            ),
        ):
            state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(provider_calls, 1)
        self.assertEqual(event.provider_message_id, "mid-before-window-close")
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-before-window-close"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 1)
        self.assertEqual(
            lifecycle_message.delivery_failure_boundary,
            "chunk:2:provider_request_rejected",
        )

    def test_provider_exception_after_confirmed_chunk_preserves_durable_receipt(self):
        event = self._event()

        with patch(
            "management.services.ig_lifecycle._message",
            return_value="a" * 951,
        ):
            first, second, provider_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"mid-exception-1"}'),
                RuntimeError("provider exploded"),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(provider_calls, 2)
        self.assertEqual(event.provider_message_id, "mid-exception-1")
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-exception-1"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 1)
        self.assertEqual(
            lifecycle_message.delivery_failure_boundary,
            "chunk:2:provider_exception",
        )

    def test_lifecycle_receipt_checkpoint_failure_is_ambiguous_without_replay(self):
        from management.services import ig_lifecycle

        event = self._event()

        with (
            patch(
                "management.services.ig_lifecycle._checkpoint_lifecycle_provider_receipt",
                side_effect=RuntimeError("checkpoint unavailable"),
                create=True,
            ),
            patch(
                "management.services.ig_lifecycle._message",
                return_value="a" * 951,
            ),
        ):
            first, second, provider_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"mid-checkpoint-1"}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(provider_calls, 1)
        self.assertEqual(event.provider_message_id, "mid-checkpoint-1")
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-checkpoint-1"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 1)
        self.assertEqual(
            lifecycle_message.delivery_failure_boundary,
            "chunk:1:receipt_checkpoint_failed",
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_non_string_provider_receipt_cannot_mark_lifecycle_sent(
        self,
        send_text,
        _notify_manager,
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        event = self._event()
        send_text.return_value = ProviderDeliveryReceipt(
            ok=True,
            kind="",
            provider_message_id=123,
            provider_message_ids=(123,),
            planned_chunk_count=1,
            delivered_chunk_count=1,
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(event.provider_message_id, "")
        self.assertIn("provider_message_id_missing", event.last_error)

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_overlong_provider_receipt_cannot_mark_lifecycle_sent(
        self,
        send_text,
        _notify_manager,
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        event = self._event()
        overlong_id = "m" * 256
        send_text.return_value = ProviderDeliveryReceipt(
            ok=True,
            kind="",
            provider_message_id=overlong_id,
            provider_message_ids=(overlong_id,),
            planned_chunk_count=1,
            delivered_chunk_count=1,
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(event.provider_message_id, "")
        self.assertIn("provider_message_id_missing", event.last_error)

    def test_exception_after_receipt_checkpoint_does_not_erase_evidence(self):
        event = self._event()

        with (
            patch(
                "management.services.ig_lifecycle._message",
                return_value="a" * 951,
            ),
            patch(
                "management.services.instagram_bot._register_outgoing_message",
                side_effect=RuntimeError("outgoing registry unavailable"),
            ),
        ):
            first, second, provider_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"mid-checkpointed-before-error"}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(provider_calls, 1)
        self.assertEqual(
            event.provider_message_id,
            "mid-checkpointed-before-error",
        )
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-checkpointed-before-error"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 1)
        self.assertEqual(
            lifecycle_message.delivery_failure_boundary,
            "chunk:2:provider_exception",
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_stale_worker_finalization_does_not_touch_reclaimed_lease(
        self,
        send_text,
        notify_manager,
    ):
        event = self._event()
        takeover_at = timezone.now() - timedelta(minutes=1)

        def reclaim_before_old_worker_finalizes(*_args, **_kwargs):
            IgLifecycleEvent.objects.filter(pk=event.pk).update(
                state=IgLifecycleEvent.State.PROCESSING,
                lease_token="replacement-worker",
                lease_expires_at=timezone.now() + timedelta(minutes=5),
                last_error="replacement worker owns the event",
                updated_at=takeover_at,
            )
            return False, "cancelled", "old worker lost its lease", ""

        send_text.side_effect = reclaim_before_old_worker_finalizes

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "replacement-worker")
        self.assertEqual(event.last_error, "replacement worker owns the event")
        self.assertEqual(event.updated_at, takeover_at)
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        notify_manager.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_legacy_processing_without_lease_is_ambiguous_without_resend(
        self,
        send_text,
    ):
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "legacy-worker-without-expiry"
        event.lease_expires_at = None
        event.due_at = timezone.now() - timedelta(minutes=1)
        event.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "due_at",
                "updated_at",
            ]
        )

        result = dispatch_due_lifecycle_events(limit=1)

        event.refresh_from_db()
        self.assertEqual(result, 0)
        self.assertEqual(event.state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(
            event.last_error,
            "processing lease has no expiry; delivery outcome requires manager review",
        )
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                deal=self.deal,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_expired_processing_lease_without_marker_cancels_after_reassignment(
        self,
        send_text,
    ):
        assignment = link_order_to_client(self.order, client=self.client)
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "unknown-delivery-worker"
        event.lease_expires_at = timezone.now() - timedelta(minutes=1)
        event.last_error = PROVIDER_BOUNDARY_CLAIM_MARKER
        event.save(
            update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "last_error",
                "updated_at",
            ]
        )
        cleared = unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Order belongs to another Instagram customer.",
        )
        other_client = IgClient.get_or_create_for_sender(
            "ig-lifecycle-expired-other"
        )
        link_order_to_client(
            self.order,
            client=other_client,
            expected_version=cleared.version,
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, STALE_ASSIGNMENT_ERROR)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_live_processing_lease_is_not_cancelled_after_reassignment(
        self,
        send_text,
    ):
        assignment = link_order_to_client(self.order, client=self.client)
        event = self._event()
        event.state = IgLifecycleEvent.State.PROCESSING
        event.lease_token = "active-delivery-worker"
        event.lease_expires_at = timezone.now() + timedelta(minutes=1)
        event.save(
            update_fields=["state", "lease_token", "lease_expires_at", "updated_at"]
        )
        cleared = unlink_order_from_client(
            self.order,
            client=self.client,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Order belongs to another Instagram customer.",
        )
        other_client = IgClient.get_or_create_for_sender("ig-lifecycle-live-other")
        link_order_to_client(
            self.order,
            client=other_client,
            expected_version=cleared.version,
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(event.lease_token, "active-delivery-worker")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", "", "meta-channel-1"))
    def test_direct_delivery_updates_independent_order_channel_state(self, send_text):
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.SENT)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"]["instagram_lifecycle"]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["provider_message_id"], "meta-channel-1")
        send_text.assert_called_once()

    def test_older_event_cannot_overwrite_newer_lifecycle_projection(self):
        from management.services.ig_lifecycle import _project_order_channel

        older = self._event()
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        newer = self._event(
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": self.order.tracking_number},
        )
        newer.state = IgLifecycleEvent.State.SENT
        newer.provider_message_id = "meta-newer"
        newer.save(
            update_fields=["state", "provider_message_id", "updated_at"]
        )
        older.state = IgLifecycleEvent.State.CANCELLED
        older.last_error = PAYMENT_NOT_VERIFIED_ERROR
        older.save(update_fields=["state", "last_error", "updated_at"])

        _project_order_channel(newer)
        _project_order_channel(older)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"][
            "instagram_lifecycle"
        ]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["provider_message_id"], "meta-newer")
        self.assertEqual(channel["lifecycle_event_id"], newer.pk)
        self.assertEqual(channel["kind"], newer.kind)
        self.assertEqual(channel["event_key"], newer.event_key)

    def test_stale_same_event_snapshot_cannot_overwrite_sent_projection(self):
        from management.services.ig_lifecycle import _project_order_channel

        event = self._event()
        stale = IgLifecycleEvent.objects.get(pk=event.pk)
        event.state = IgLifecycleEvent.State.SENT
        event.provider_message_id = "meta-same-event-sent"
        event.save(update_fields=["state", "provider_message_id", "updated_at"])

        _project_order_channel(event)
        _project_order_channel(stale)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"][
            "instagram_lifecycle"
        ]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["provider_message_id"], "meta-same-event-sent")
        self.assertEqual(channel["lifecycle_event_id"], event.pk)
        self.assertEqual(
            channel["lifecycle_event_updated_at"],
            event.updated_at.isoformat(),
        )

    @patch("storefront.views.utils._record_post_payment_channel")
    def test_sync_projection_passes_lifecycle_event_revision(self, record_channel):
        from storefront.views.utils import _sync_instagram_lifecycle_channel

        event = self._event()
        event.state = IgLifecycleEvent.State.SENT
        event.provider_message_id = "meta-sync-revision"
        event.save(update_fields=["state", "provider_message_id", "updated_at"])

        _sync_instagram_lifecycle_channel(self.order.pk)

        record_channel.assert_called_once()
        metadata = record_channel.call_args.kwargs["metadata"]
        self.assertEqual(
            metadata["lifecycle_event_updated_at"],
            event.updated_at.isoformat(),
        )
        self.assertEqual(
            record_channel.call_args.kwargs["monotonic_revision_key"],
            "lifecycle_event_updated_at",
        )

    def test_late_payment_materialization_cannot_clobber_delivered_projection(self):
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )
        delivered = self._event(
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )
        delivered.state = IgLifecycleEvent.State.SENT
        delivered.provider_message_id = "meta-delivered"
        delivered.save(
            update_fields=["state", "provider_message_id", "updated_at"]
        )
        late_payment = self._event()
        late_payment.state = IgLifecycleEvent.State.SENT
        late_payment.provider_message_id = "meta-payment-late"
        late_payment.save(
            update_fields=["state", "provider_message_id", "updated_at"]
        )

        from management.services.ig_lifecycle import _project_order_channel

        _project_order_channel(delivered)
        _project_order_channel(late_payment)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"][
            "instagram_lifecycle"
        ]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["lifecycle_event_id"], delivered.pk)
        self.assertEqual(channel["kind"], delivered.kind)
        self.assertEqual(channel["provider_message_id"], "meta-delivered")

    def test_delivered_review_copy_does_not_promise_unissued_discount(self):
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )
        event = self._event(
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )

        message = _message(event)

        self.assertNotIn("10%", message)
        self.assertNotIn("знижк", message.lower())
        self.assertIn("@twocomms", message)

    def test_delivery_status_progression_materializes_one_order_event(self):
        link_order_to_client(self.order, client=self.client)
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )

        first, first_created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )
        second, second_created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "10", "status": "received"},
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(
            IgLifecycleEvent.objects.filter(
                order=self.order,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).count(),
            1,
        )

    def test_manual_done_without_carrier_delivery_does_not_create_delivery_event(self):
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 7
        self.order.save(
            update_fields=["status", "tracking_number", "tracking_status_code"]
        )

        event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "done", "status": "manual done"},
        )

        self.assertIsNone(event)
        self.assertFalse(created)

    def test_delivered_materialization_reloads_locked_order_before_truth_check(self):
        link_order_to_client(self.order, client=self.client)
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )
        stale_order = Order.objects.get(pk=self.order.pk)
        Order.objects.filter(pk=self.order.pk).update(
            status="ship",
            tracking_status_code=7,
            tracking_terminal_at=None,
        )

        event, created = ensure_lifecycle_event(
            stale_order,
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )

        self.assertIsNone(event)
        self.assertFalse(created)
        self.assertFalse(
            IgLifecycleEvent.objects.filter(
                order=self.order,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).exists()
        )

    @patch("management.services.instagram_bot.send_text")
    def test_ttn_event_is_cancelled_when_tracking_number_changes_after_materialization(
        self,
        send_text,
    ):
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        event = self._event(
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": "20450000000009"},
        )
        self.assertEqual(event.payload["tracking_number"], "20450000000009")

        self.order.tracking_number = "20450000000010"
        self.order.save(update_fields=["tracking_number"])

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "tracking_number_changed")
        self.assertEqual(event.payload["tracking_number"], "20450000000009")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_ttn_event_is_cancelled_when_tracking_number_is_cleared_after_materialization(
        self,
        send_text,
    ):
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        event = self._event(
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": "20450000000009"},
        )

        self.order.tracking_number = ""
        self.order.save(update_fields=["tracking_number"])

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "tracking_number_changed")
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch(
        "management.services.instagram_bot.send_text",
        return_value=(True, "", "", "meta-stale-ttn"),
    )
    def test_ttn_is_revalidated_immediately_before_provider_send(
        self,
        send_text,
        reply_execution_boundary,
        customer_send_boundary,
    ):
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        event = self._event(
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": "20450000000009"},
        )

        @contextmanager
        def replace_tracking_after_claim(*_args, **_kwargs):
            self.order.tracking_number = "20450000000010"
            self.order.save(update_fields=["tracking_number"])
            yield True

        @contextmanager
        def permit_customer_send(*_args, **_kwargs):
            yield True

        reply_execution_boundary.side_effect = replace_tracking_after_claim
        customer_send_boundary.side_effect = permit_customer_send

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "tracking_number_changed")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_text")
    def test_delivery_event_is_cancelled_when_carrier_truth_is_no_longer_current(
        self,
        send_text,
    ):
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )
        event = self._event(
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )
        self.order.tracking_status_code = 7
        self.order.tracking_terminal_at = None
        self.order.save(
            update_fields=["tracking_status_code", "tracking_terminal_at"]
        )

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "carrier delivery not confirmed")
        send_text.assert_not_called()

    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot.send_text")
    def test_delivery_truth_is_revalidated_immediately_before_provider_send(
        self,
        send_text,
        reply_execution_boundary,
        customer_send_boundary,
    ):
        self.order.status = "done"
        self.order.tracking_number = "20450000000009"
        self.order.tracking_status_code = 9
        self.order.tracking_terminal_at = timezone.now()
        self.order.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_status_code",
                "tracking_terminal_at",
            ]
        )
        event = self._event(
            IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            payload={"status_code": "9", "status": "delivered"},
        )

        @contextmanager
        def invalidate_after_claim(*_args, **_kwargs):
            self.order.tracking_status_code = 7
            self.order.tracking_terminal_at = None
            self.order.save(
                update_fields=["tracking_status_code", "tracking_terminal_at"]
            )
            yield True

        @contextmanager
        def permit_customer_send(*_args, **_kwargs):
            yield True

        reply_execution_boundary.side_effect = invalidate_after_claim
        customer_send_boundary.side_effect = permit_customer_send

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.state, IgLifecycleEvent.State.CANCELLED)
        self.assertEqual(event.last_error, "carrier delivery not confirmed")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text", return_value=(False, "permanent", "blocked"))
    def test_permanent_failure_is_operator_only_and_not_replayed(self, send_text, notify_manager):
        event = self._event()

        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.FAILED)
        self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.FAILED)
        self.assertEqual(send_text.call_count, 1)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )
        self.assertEqual(
            notify_manager.call_args.kwargs["dedupe_key"],
            f"ig-lifecycle:delivery:{event.event_key}",
        )
        self.assertIn("не вдалося доставити lifecycle-подію", notify_manager.call_args.args[0])
        alert = notify_manager.call_args.args[0]
        self.assertNotIn(self.order.order_number, alert)
        self.assertIn(str(self.client.pk), alert)
        self.assertIn(str(self.deal.pk), alert)
        self.assertIn(str(event.pk), alert)

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_text", return_value=(False, "permanent", "blocked"))
    def test_window_and_delivery_reviews_have_distinct_durable_keys(self, _send_text, _deliver):
        self.client.last_message_at = None
        self.client.save(update_fields=["last_message_at", "updated_at"])
        event = self._event()

        self.assertEqual(
            dispatch_lifecycle_event(event.pk),
            IgLifecycleEvent.State.MANAGER_REVIEW,
        )
        self.client.last_message_at = timezone.now()
        self.client.save(update_fields=["last_message_at", "updated_at"])
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        delivery_event = self._event(
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": self.order.tracking_number},
        )

        self.assertEqual(
            dispatch_lifecycle_event(delivery_event.pk),
            IgLifecycleEvent.State.FAILED,
        )
        self.assertEqual(
            set(IgBotNotification.objects.filter(client=self.client).values_list("dedupe_key", flat=True)),
            {
                f"ig-lifecycle:window:{event.event_key}",
                f"ig-lifecycle:delivery:{delivery_event.event_key}",
            },
        )

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch("management.services.instagram_bot._provider_http")
    def test_send_text_callback_rejection_prevents_provider_http(
        self,
        provider_http,
        _page_token,
        _account_id,
    ):
        from management.services.instagram_bot import send_text

        callback_calls = []

        def reject_provider_io():
            callback_calls.append("marker")
            return False

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "Тестове повідомлення",
            provider_io_started_callback=reject_provider_io,
            return_receipt=True,
        )

        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.kind, "cancelled")
        self.assertEqual(
            receipt.failure_boundary,
            "chunk:1:provider_io_not_started",
        )
        self.assertEqual(callback_calls, ["marker"])
        provider_http.assert_not_called()

    def test_send_text_preflight_failures_never_mark_or_call_provider(self):
        from management.services.instagram_bot import send_text

        cases = (
            {
                "name": "missing_account",
                "account_id": "",
                "page_token": "page-token",
                "text": "Тестове повідомлення",
                "link_circuit_active": False,
                "failure_boundary": "preflight:missing_provider_account_id",
            },
            {
                "name": "missing_token",
                "account_id": "ig-account",
                "page_token": "",
                "text": "Тестове повідомлення",
                "link_circuit_active": False,
                "failure_boundary": "preflight:missing_provider_token",
            },
            {
                "name": "empty_reply",
                "account_id": "ig-account",
                "page_token": "page-token",
                "text": "",
                "link_circuit_active": False,
                "failure_boundary": "preflight:empty_reply",
            },
            {
                "name": "empty_linkless_fallback",
                "account_id": "ig-account",
                "page_token": "page-token",
                "text": "https://twocomms.shop/order/1",
                "link_circuit_active": True,
                "failure_boundary": "preflight:empty_linkless_fallback",
            },
        )

        for case in cases:
            with self.subTest(case=case["name"]):
                callback_calls = []
                with (
                    patch(
                        "management.services.instagram_bot._provider_account_id",
                        return_value=case["account_id"],
                    ),
                    patch(
                        "management.services.instagram_bot.get_page_token",
                        return_value=case["page_token"],
                    ),
                    patch(
                        "management.services.instagram_bot._link_circuit_active",
                        return_value=case["link_circuit_active"],
                    ),
                    patch(
                        "management.services.instagram_bot._provider_http"
                    ) as provider_http,
                ):
                    receipt = send_text(
                        self.settings,
                        self.client.igsid,
                        case["text"],
                        provider_io_started_callback=lambda: callback_calls.append(
                            "marker"
                        )
                        or True,
                        allow_url_fallback=True,
                        return_receipt=True,
                    )

                self.assertFalse(receipt.ok)
                self.assertEqual(receipt.failure_boundary, case["failure_boundary"])
                self.assertEqual(callback_calls, [])
                provider_http.assert_not_called()

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch("management.services.instagram_bot._provider_http")
    def test_first_permission_denial_prevents_marker_and_provider_http(
        self,
        provider_http,
        _page_token,
        _account_id,
    ):
        from management.services.instagram_bot import send_text

        callback_calls = []

        @contextmanager
        def deny_permission():
            yield False

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "Тестове повідомлення",
            permission_boundary_factory=deny_permission,
            provider_io_started_callback=lambda: callback_calls.append("marker")
            or True,
            return_receipt=True,
        )

        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.kind, "cancelled")
        self.assertEqual(
            receipt.failure_boundary,
            "chunk:1:permission_epoch_changed",
        )
        self.assertEqual(callback_calls, [])
        provider_http.assert_not_called()

    def test_provider_timeout_after_marker_is_terminally_ambiguous(self):
        event = self._event()

        first, second, http_calls = self._dispatch_real_provider_outcome(
            event,
            TimeoutError("provider timeout"),
        )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(http_calls, 1)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertIsNotNone(lifecycle_message.send_started_at)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )

    def test_provider_rate_limit_after_marker_is_terminally_ambiguous(self):
        event = self._event()

        first, second, http_calls = self._dispatch_real_provider_outcome(
            event,
            (429, '{"error":{"message":"rate limited","code":4}}'),
        )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(http_calls, 1)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertIsNotNone(lifecycle_message.send_started_at)
        self.assertNotEqual(event.state, IgLifecycleEvent.State.PENDING)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )

    def test_provider_5xx_after_marker_is_terminally_ambiguous(self):
        event = self._event()

        first, second, http_calls = self._dispatch_real_provider_outcome(
            event,
            (503, '{"error":{"message":"provider unavailable","code":2}}'),
        )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(http_calls, 1)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertIsNotNone(lifecycle_message.send_started_at)
        self.assertNotEqual(event.state, IgLifecycleEvent.State.PENDING)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ig_lifecycle:{event.event_key}",
            ).exists()
        )

    def test_partial_multi_chunk_send_keeps_receipt_and_is_not_replayed(self):
        event = self._event()

        with patch(
            "management.services.ig_lifecycle._message",
            return_value="a" * 1901,
        ):
            first, second, http_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"mid-partial-1"}'),
                (200, '{"message_id":"mid-partial-2"}'),
                (503, '{"error":{"message":"provider unavailable","code":2}}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(second, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(http_calls, 3)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertIsNotNone(lifecycle_message.send_started_at)
        self.assertEqual(event.provider_message_id, "mid-partial-1")
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-partial-1", "mid-partial-2"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 3)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_failure_boundary, "chunk:3:unknown")

    def test_successful_multi_chunk_send_persists_complete_receipt(self):
        event = self._event()

        with patch(
            "management.services.ig_lifecycle._message",
            return_value="a" * 951,
        ):
            first, second, http_calls = self._dispatch_real_provider_outcome(
                event,
                (200, '{"message_id":"mid-success-1"}'),
                (200, '{"message_id":"mid-success-2"}'),
            )

        event.refresh_from_db()
        self.assertEqual(first, IgLifecycleEvent.State.SENT)
        self.assertEqual(second, IgLifecycleEvent.State.SENT)
        self.assertEqual(http_calls, 2)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertEqual(event.provider_message_id, "mid-success-1")
        self.assertEqual(
            lifecycle_message.delivery_provider_message_ids,
            ["mid-success-1", "mid-success-2"],
        )
        self.assertEqual(lifecycle_message.delivery_planned_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_delivered_chunk_count, 2)
        self.assertEqual(lifecycle_message.delivery_failure_boundary, "")

    @patch("management.services.instagram_bot._activate_link_send_circuit")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch(
        "management.services.instagram_bot._provider_http",
        side_effect=[
            (
                400,
                '{"error":{"message":"link restricted","code":508,"error_subcode":2534122}}',
            ),
            (200, '{"message_id":"mid-linkless"}'),
        ],
    )
    def test_url_fallback_reuses_one_provider_marker(
        self,
        provider_http,
        _page_token,
        _account_id,
        _activate_circuit,
    ):
        from management.services.instagram_bot import send_text

        callback_calls = []

        def mark_provider_io():
            callback_calls.append("marker")
            return True

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "Перевірте https://twocomms.shop/order/1",
            provider_io_started_callback=mark_provider_io,
            allow_url_fallback=True,
            alert_link_restriction=False,
            return_receipt=True,
        )

        self.assertTrue(receipt.ok)
        self.assertEqual(receipt.kind, "degraded_link_restriction")
        self.assertEqual(receipt.provider_message_id, "mid-linkless")
        self.assertEqual(callback_calls, ["marker"])
        self.assertEqual(provider_http.call_count, 2)

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(200, '{"recipient_id":"ig-lifecycle-test","message_id":"mid-123"}'),
    )
    def test_send_text_can_return_structured_provider_receipt(
        self, provider_http, _page_token, _account_id
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt, send_text

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "Тестове повідомлення",
            return_receipt=True,
        )

        self.assertIsInstance(receipt, ProviderDeliveryReceipt)
        self.assertTrue(receipt.ok)
        self.assertEqual(receipt.provider_message_id, "mid-123")
        self.assertEqual(receipt.as_legacy_tuple(), (True, "", ""))
        provider_http.assert_called_once()

    @patch("management.services.instagram_bot._register_outgoing_message")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch("management.services.instagram_bot._provider_http")
    def test_send_text_rejects_malformed_provider_receipt_ids(
        self,
        provider_http,
        _page_token,
        _account_id,
        register_outgoing,
    ):
        from management.services.instagram_bot import send_text

        cases = (
            '{"message_id":123}',
            '{"message_id":"' + ("m" * 256) + '"}',
        )
        for response_body in cases:
            with self.subTest(response_body=response_body[:40]):
                callback_ids = []
                provider_http.return_value = (200, response_body)
                register_outgoing.reset_mock()

                receipt = send_text(
                    self.settings,
                    self.client.igsid,
                    "Тестове повідомлення",
                    provider_message_callback=callback_ids.append,
                    return_receipt=True,
                )

                self.assertFalse(receipt.ok)
                self.assertEqual(receipt.kind, "unknown")
                self.assertEqual(receipt.provider_message_id, "")
                self.assertEqual(receipt.provider_message_ids, ())
                self.assertEqual(callback_ids, [])
                register_outgoing.assert_not_called()

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch(
        "management.services.instagram_bot._provider_http",
        side_effect=[
            (200, '{"recipient_id":"ig-lifecycle-test","message_id":"mid-1"}'),
            (200, '{"recipient_id":"ig-lifecycle-test","message_id":"mid-2"}'),
        ],
    )
    def test_send_text_marks_provider_io_once_before_first_http(
        self,
        provider_http,
        _page_token,
        _account_id,
    ):
        from management.services.instagram_bot import send_text

        order = []

        def mark_provider_io():
            order.append("marker")
            return True

        original_http = list(provider_http.side_effect)

        def record_http(*args, **kwargs):
            order.append("http")
            return original_http.pop(0)

        provider_http.side_effect = record_http

        receipt = send_text(
            self.settings,
            self.client.igsid,
            "a" * 951,
            provider_io_started_callback=mark_provider_io,
            return_receipt=True,
        )

        self.assertTrue(receipt.ok)
        self.assertEqual(order, ["marker", "http", "http"])
        self.assertEqual(provider_http.call_count, 2)

    @patch("management.services.ig_reply_boundary.customer_send_boundary")
    @patch("management.services.ig_reply_boundary.reply_execution_boundary")
    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch("management.services.instagram_bot._provider_http")
    def test_lifecycle_commits_marker_and_holds_truth_boundary_during_http(
        self,
        provider_http,
        _page_token,
        _account_id,
        reply_execution_boundary,
        customer_send_boundary,
    ):
        event = self._event()
        baseline_atomic_depth = len(connection.atomic_blocks)

        @contextmanager
        def permit(*_args, **_kwargs):
            yield True

        def observe_provider_boundary(*_args, **_kwargs):
            persisted = IgLifecycleEvent.objects.get(pk=event.pk)
            lifecycle_message = InstagramBotMessage.objects.get(
                synthetic_event_key__startswith="ig-lifecycle:"
            )
            self.assertIsNotNone(lifecycle_message.send_started_at)
            self.assertEqual(
                len(connection.atomic_blocks),
                baseline_atomic_depth + 1,
            )
            return 200, '{"message_id":"mid-provider-boundary"}'

        reply_execution_boundary.side_effect = permit
        customer_send_boundary.side_effect = permit
        provider_http.side_effect = observe_provider_boundary

        state = dispatch_lifecycle_event(event.pk)

        event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.SENT)
        lifecycle_message = InstagramBotMessage.objects.get(
            synthetic_event_key__startswith="ig-lifecycle:"
        )
        self.assertIsNotNone(lifecycle_message.send_started_at)
        self.assertEqual(event.provider_message_id, "mid-provider-boundary")
