"""Disposable MariaDB lifecycle acceptance suite."""

import hashlib
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from threading import Event, Lock, Thread
from unittest.mock import patch

from django.core.management import call_command
from django.db import close_old_connections, connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from management.models import (
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgLifecycleEvent,
    IgOrderAttribution,
    IgPaymentProjection,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from management.services.ig_lifecycle import (
    _lifecycle_message_key,
    _project_order_channel,
    dispatch_lifecycle_event,
    ensure_lifecycle_event,
)
from management.services.ig_order_assignments import link_order_to_client
from orders.models import Order, PaymentAttempt


class InstagramMariaDbLifecycleTests(SimpleTestCase):
    databases = {"default"}

    def test_database_is_mariadb_and_schema_is_disposable(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_twocomms_ig_"))
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), @@version_comment")
            version, version_comment = cursor.fetchone()
        self.assertIn("mariadb", f"{version} {version_comment}".lower())
        self.assertRegex(version, r"^11\.4(?:\.|-)")

    def test_database_connection_uses_utf8mb4(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@character_set_connection, @@collation_connection")
            charset, collation = cursor.fetchone()
        self.assertEqual(charset.lower(), "utf8mb4")
        self.assertIn("utf8mb4", collation.lower())


class InstagramMariaDbLifecycleConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def _fixture_teardown(self):
        # MariaDB append-only journals reject Django's default DELETE flush.
        for db_name in self._databases_names(include_mirrors=False):
            inhibit_post_migrate = (
                self.available_apps is not None
                or (
                    self.serialized_rollback
                    and hasattr(
                        connections[db_name],
                        "_test_serialized_contents",
                    )
                )
            )
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=db_name,
                reset_sequences=True,
                allow_cascade=self.available_apps is not None,
                inhibit_post_migrate=inhibit_post_migrate,
            )

    def setUp(self):
        self.client = IgClient.get_or_create_for_sender(
            "ig-mariadb-lifecycle",
            defaults={"language": "uk"},
        )
        self.client.last_message_at = timezone.now()
        self.client.save(update_fields=["last_message_at", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            amount=Decimal("950.00"),
        )
        ensure_episode_for_deal(self.deal)
        self.order = Order.objects.create(
            full_name="MariaDB Buyer",
            phone="+380501112233",
            email="mariadb@example.com",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        self.attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"ig-mariadb-lifecycle").hexdigest(),
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
        proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=self.order.total_sum,
            quoted_total=self.order.total_sum,
            requested_payment_amount=self.order.total_sum,
            items_digest="a" * 64,
        )
        proposal.payment_attempt = self.attempt
        proposal.save(update_fields=["payment_attempt", "updated_at"])
        IgOrderAttribution.objects.create(
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
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.save(update_fields=["is_enabled", "updated_at"])
        link_order_to_client(self.order, client=self.client)
        self.event, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={"attempt_id": self.attempt.pk, "amount": "950.00"},
        )
        self.assertTrue(created)

    @staticmethod
    @contextmanager
    def _permit(*_args, **_kwargs):
        yield True

    def _provider_patches(self, provider_http):
        return (
            patch(
                "management.services.ig_reply_boundary.reply_execution_boundary",
                side_effect=self._permit,
            ),
            patch(
                "management.services.ig_reply_boundary.customer_send_boundary",
                side_effect=self._permit,
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
        )

    def test_competing_dispatchers_emit_one_provider_request(self):
        http_entered = Event()
        release_http = Event()
        second_finished = Event()
        result_lock = Lock()
        results = []
        errors = []
        provider_calls = 0

        def provider_http(*_args, **_kwargs):
            nonlocal provider_calls
            with result_lock:
                provider_calls += 1
            http_entered.set()
            self.assertTrue(release_http.wait(timeout=10))
            return 200, '{"message_id":"mid-mariadb-once"}'

        def dispatch(name):
            close_old_connections()
            try:
                state = dispatch_lifecycle_event(self.event.pk)
                with result_lock:
                    results.append((name, state))
            except BaseException as exc:
                with result_lock:
                    errors.append(exc)
            finally:
                if name == "second":
                    second_finished.set()
                close_old_connections()

        patches = self._provider_patches(provider_http)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            first = Thread(target=dispatch, args=("first",))
            first.start()
            self.assertTrue(http_entered.wait(timeout=10))
            second = Thread(target=dispatch, args=("second",))
            second.start()
            try:
                self.assertFalse(second_finished.wait(timeout=0.25))
            finally:
                release_http.set()
            first.join(timeout=10)
            second.join(timeout=10)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(provider_calls, 1)
        self.assertIn(
            sorted(state for _name, state in results),
            (
                [IgLifecycleEvent.State.PROCESSING, IgLifecycleEvent.State.SENT],
                [IgLifecycleEvent.State.SENT, IgLifecycleEvent.State.SENT],
            ),
        )

        self.event.refresh_from_db()
        message = InstagramBotMessage.objects.get(
            synthetic_event_key=_lifecycle_message_key(self.event.event_key)
        )
        self.assertEqual(self.event.state, IgLifecycleEvent.State.SENT)
        self.assertEqual(self.event.provider_message_id, "mid-mariadb-once")
        self.assertEqual(message.provider_message_id, "mid-mariadb-once")
        self.assertEqual(
            message.delivery_provider_message_ids,
            ["mid-mariadb-once"],
        )

    def test_payment_reversal_waits_for_provider_truth_boundary(self):
        http_entered = Event()
        release_http = Event()
        reversal_finished = Event()
        errors = []

        def provider_http(*_args, **_kwargs):
            http_entered.set()
            self.assertTrue(release_http.wait(timeout=10))
            return 200, '{"message_id":"mid-before-reversal"}'

        def reverse_payment():
            close_old_connections()
            try:
                with transaction.atomic():
                    projection = IgPaymentProjection.objects.select_for_update().get(
                        pk=self.payment_projection.pk
                    )
                    projection.truth = IgDeal.PaymentTruth.REVERSED
                    projection.save(update_fields=["truth", "updated_at"])
            except BaseException as exc:
                errors.append(exc)
            finally:
                reversal_finished.set()
                close_old_connections()

        patches = self._provider_patches(provider_http)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            dispatcher = Thread(
                target=lambda: dispatch_lifecycle_event(self.event.pk)
            )
            dispatcher.start()
            self.assertTrue(http_entered.wait(timeout=10))
            reversal = Thread(target=reverse_payment)
            reversal.start()
            self.assertFalse(reversal_finished.wait(timeout=0.25))
            release_http.set()
            dispatcher.join(timeout=10)
            reversal.join(timeout=10)

        self.assertFalse(dispatcher.is_alive())
        self.assertFalse(reversal.is_alive())
        self.assertEqual(errors, [])
        self.event.refresh_from_db()
        self.payment_projection.refresh_from_db()
        self.assertEqual(self.event.state, IgLifecycleEvent.State.SENT)
        self.assertEqual(self.event.provider_message_id, "mid-before-reversal")
        self.assertEqual(
            self.payment_projection.truth,
            IgDeal.PaymentTruth.REVERSED,
        )

    @patch("management.services.instagram_bot.notify_manager")
    @patch("management.services.instagram_bot.send_text")
    def test_stale_worker_cannot_finalize_reclaimed_lease(
        self,
        send_text,
        _notify_manager,
    ):
        def reclaim_before_finalize(*_args, **_kwargs):
            IgLifecycleEvent.objects.filter(pk=self.event.pk).update(
                state=IgLifecycleEvent.State.PROCESSING,
                lease_token="replacement-worker",
                lease_expires_at=timezone.now() + timedelta(minutes=5),
                last_error="replacement owns lease",
                updated_at=timezone.now(),
            )
            return True, "", "", "mid-old-worker"

        send_text.side_effect = reclaim_before_finalize

        state = dispatch_lifecycle_event(self.event.pk)

        self.event.refresh_from_db()
        self.assertEqual(state, IgLifecycleEvent.State.PROCESSING)
        self.assertEqual(self.event.lease_token, "replacement-worker")
        self.assertEqual(self.event.last_error, "replacement owns lease")
        self.assertFalse(self.event.provider_message_id)

    def test_partial_multi_chunk_receipt_persists_all_accepted_ids(self):
        outcomes = iter(
            (
                (200, '{"message_id":"mid-mariadb-1"}'),
                (200, '{"message_id":"mid-mariadb-2"}'),
                (503, '{"error":{"message":"temporary"}}'),
            )
        )

        patches = self._provider_patches(lambda *_args, **_kwargs: next(outcomes))
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patch(
                "management.services.ig_lifecycle._message",
                return_value="a" * 1901,
            ),
        ):
            state = dispatch_lifecycle_event(self.event.pk)

        self.event.refresh_from_db()
        message = InstagramBotMessage.objects.get(
            synthetic_event_key=_lifecycle_message_key(self.event.event_key)
        )
        self.assertEqual(state, IgLifecycleEvent.State.AMBIGUOUS)
        self.assertEqual(
            message.delivery_provider_message_ids,
            ["mid-mariadb-1", "mid-mariadb-2"],
        )
        self.assertEqual(message.delivery_planned_chunk_count, 3)
        self.assertEqual(message.delivery_delivered_chunk_count, 2)
        self.assertEqual(message.delivery_failure_boundary, "chunk:3:unknown")

    def test_stale_delivered_order_snapshot_cannot_materialize_after_lock(self):
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
                order_id=self.order.pk,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).exists()
        )

    def test_older_lifecycle_event_cannot_clobber_newer_json_projection(self):
        self.order.tracking_number = "20450000000009"
        self.order.save(update_fields=["tracking_number"])
        newer, created = ensure_lifecycle_event(
            self.order,
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": self.order.tracking_number},
        )
        self.assertTrue(created)
        newer.state = IgLifecycleEvent.State.SENT
        newer.provider_message_id = "mid-mariadb-newer"
        newer.save(update_fields=["state", "provider_message_id", "updated_at"])
        self.event.state = IgLifecycleEvent.State.CANCELLED
        self.event.last_error = "payment_not_verified"
        self.event.save(update_fields=["state", "last_error", "updated_at"])

        _project_order_channel(newer)
        _project_order_channel(self.event)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"][
            "instagram_lifecycle"
        ]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(channel["lifecycle_event_id"], newer.pk)
        self.assertEqual(channel["kind"], newer.kind)
        self.assertEqual(channel["provider_message_id"], "mid-mariadb-newer")

    def test_stale_same_event_snapshot_cannot_clobber_sent_json_projection(self):
        stale = IgLifecycleEvent.objects.get(pk=self.event.pk)
        self.event.state = IgLifecycleEvent.State.SENT
        self.event.provider_message_id = "mid-mariadb-same-event"
        self.event.save(
            update_fields=["state", "provider_message_id", "updated_at"]
        )

        _project_order_channel(self.event)
        _project_order_channel(stale)

        self.order.refresh_from_db()
        channel = self.order.payment_payload["post_payment_channels"][
            "instagram_lifecycle"
        ]
        self.assertEqual(channel["state"], "sent")
        self.assertEqual(
            channel["provider_message_id"],
            "mid-mariadb-same-event",
        )
        self.assertEqual(channel["lifecycle_event_id"], self.event.pk)
        self.assertEqual(
            channel["lifecycle_event_updated_at"],
            self.event.updated_at.isoformat(),
        )
