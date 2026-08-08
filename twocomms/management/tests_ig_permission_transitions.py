"""W1.1 regressions for bounded, durable reply-permission transitions."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgClient,
    IgPermissionTransitionJob,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot
from management.services.ig_permission_transitions import (
    attempt_permission_transition,
    create_permission_transition,
    process_due_permission_transitions,
)
from management.services.ig_reply_boundary import (
    capture_reply_permission,
    customer_send_boundary,
    pause_reply_boundary,
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
User = get_user_model()


class PermissionTransitionWebhookTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.allowed_senders = ""
        self.settings.save(update_fields=["is_enabled", "ai_enabled", "allowed_senders"])
        self.client = IgClient.objects.create(igsid="bounded-opt-out-client")

    def _lock_holder(self, lock_path):
        child_code = """
import sys, time
from management.services.ig_reply_boundary import pause_reply_boundary
with pause_reply_boundary(lock_path=sys.argv[1]):
    print('entered', flush=True)
    time.sleep(3)
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [PROJECT_ROOT, env.get("PYTHONPATH", "")])
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, lock_path],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(child.stdout.readline().strip(), "entered")
        return child

    def _customer_send_lock_holder(self, lock_path):
        child_code = """
import sys, time
import django
django.setup()
from management.services.ig_reply_boundary import customer_send_boundary
with customer_send_boundary(None, None, lock_path=sys.argv[1]):
    print('entered', flush=True)
    time.sleep(3)
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [PROJECT_ROOT, env.get("PYTHONPATH", "")])
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, lock_path],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(child.stdout.readline().strip(), "entered")
        return child

    def test_contended_opt_out_returns_bounded_and_applies_exactly_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "reply.lock")
            child = self._lock_holder(lock_path)

            def test_boundary(**kwargs):
                return pause_reply_boundary(lock_path=lock_path, **kwargs)

            try:
                started = time.monotonic()
                with patch(
                    "management.services.ig_reply_boundary.pause_reply_boundary",
                    side_effect=test_boundary,
                ):
                    created = instagram_bot.enqueue_inbound(
                        self.settings,
                        sender_id=self.client.igsid,
                        text="Не пишите мне",
                        mid="bounded-opt-out-mid",
                        persistence_only=True,
                    )
                elapsed = time.monotonic() - started

                self.assertTrue(created)
                self.assertLess(elapsed, 1.0)
                message = InstagramBotMessage.objects.get(mid="bounded-opt-out-mid")
                job = IgPermissionTransitionJob.objects.get(source_message=message)
                self.assertEqual(job.kind, IgPermissionTransitionJob.Kind.OPT_OUT)
                self.assertEqual(job.status, IgPermissionTransitionJob.Status.PENDING)
                self.assertEqual(job.last_error_kind, "reply_boundary_busy")
                self.assertFalse(capture_reply_permission(self.settings.pk, self.client.pk))
            finally:
                child.terminate()
                child.wait(timeout=5)

            self.assertEqual(
                process_due_permission_transitions(limit=1, lock_path=lock_path),
                1,
            )
            self.client.refresh_from_db()
            job.refresh_from_db()
            epoch = self.client.reply_permission_epoch
            self.assertIsNotNone(self.client.opted_out_at)
            self.assertTrue(self.client.bot_paused)
            self.assertEqual(self.client.paused_reason, "opt_out")
            self.assertEqual(job.status, IgPermissionTransitionJob.Status.APPLIED)
            self.assertEqual(process_due_permission_transitions(limit=1), 0)
            self.client.refresh_from_db()
            self.assertEqual(self.client.reply_permission_epoch, epoch)
            self.assertEqual(
                IgPermissionTransitionJob.objects.filter(source_message=message).count(),
                1,
            )

    def test_real_customer_send_contention_keeps_opt_out_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "reply.lock")
            child = self._customer_send_lock_holder(lock_path)

            def test_boundary(**kwargs):
                return pause_reply_boundary(lock_path=lock_path, **kwargs)

            try:
                started = time.monotonic()
                with patch(
                    "management.services.ig_reply_boundary.pause_reply_boundary",
                    side_effect=test_boundary,
                ):
                    created = instagram_bot.enqueue_inbound(
                        self.settings,
                        sender_id=self.client.igsid,
                        text="STOP",
                        mid="customer-send-contended-opt-out",
                        persistence_only=True,
                    )
                self.assertLess(time.monotonic() - started, 1.0)
                self.assertTrue(created)
                self.assertFalse(capture_reply_permission(self.settings.pk, self.client.pk))
            finally:
                child.terminate()
                child.wait(timeout=5)

            self.assertEqual(
                process_due_permission_transitions(limit=1, lock_path=lock_path),
                1,
            )

    def test_failed_transition_remains_a_fail_closed_permission_guard(self):
        message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="STOP",
            mid="failed-transition-mid",
            status=InstagramBotMessage.Status.DONE,
        )
        IgPermissionTransitionJob.objects.create(
            kind=IgPermissionTransitionJob.Kind.OPT_OUT,
            status=IgPermissionTransitionJob.Status.FAILED,
            client=self.client,
            settings=self.settings,
            source_message=message,
            dedupe_key="permission:opt_out:failed-transition-mid",
            last_error_kind="DatabaseError",
            next_attempt_at=None,
        )

        permission = capture_reply_permission(self.settings.pk, self.client.pk)

        self.assertFalse(permission)
        self.assertEqual(permission.reason, "permission_transition_pending")

    def test_contended_manager_takeover_persists_and_recovers_once(self):
        provider_event_at = timezone.now() - timedelta(minutes=5)
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "reply.lock")
            child = self._lock_holder(lock_path)

            def test_boundary(**kwargs):
                return pause_reply_boundary(lock_path=lock_path, **kwargs)

            try:
                started = time.monotonic()
                with patch(
                    "management.services.ig_reply_boundary.pause_reply_boundary",
                    side_effect=test_boundary,
                ):
                    instagram_bot._handle_echo(
                        self.client.igsid,
                        "Менеджер відповів",
                        mid="bounded-takeover-mid",
                        received_at=provider_event_at,
                        persistence_only=True,
                    )
                self.assertLess(time.monotonic() - started, 1.0)
                message = InstagramBotMessage.objects.get(mid="bounded-takeover-mid")
                job = IgPermissionTransitionJob.objects.get(source_message=message)
                self.assertEqual(job.kind, IgPermissionTransitionJob.Kind.MANAGER_TAKEOVER)
                self.assertEqual(job.status, IgPermissionTransitionJob.Status.PENDING)
                self.assertEqual(job.last_error_kind, "reply_boundary_busy")
                self.assertFalse(capture_reply_permission(self.settings.pk, self.client.pk))
            finally:
                child.terminate()
                child.wait(timeout=5)

            self.assertEqual(
                process_due_permission_transitions(limit=1, lock_path=lock_path),
                1,
            )
            self.client.refresh_from_db()
            job.refresh_from_db()
            epoch = self.client.reply_permission_epoch
            self.assertTrue(self.client.manager_takeover)
            self.assertTrue(self.client.bot_paused)
            self.assertEqual(self.client.paused_reason, "manager_takeover")
            self.assertEqual(self.client.last_manager_message_at, provider_event_at)
            self.assertEqual(self.client.paused_at, provider_event_at)
            self.assertEqual(job.status, IgPermissionTransitionJob.Status.APPLIED)
            self.assertEqual(process_due_permission_transitions(limit=1), 0)
            self.client.refresh_from_db()
            self.assertEqual(self.client.reply_permission_epoch, epoch)

    def test_contended_global_pause_persists_and_recovers_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "reply.lock")
            child = self._lock_holder(lock_path)

            def test_boundary(**kwargs):
                return pause_reply_boundary(lock_path=lock_path, **kwargs)

            try:
                started = time.monotonic()
                with patch(
                    "management.services.ig_reply_boundary.pause_reply_boundary",
                    side_effect=test_boundary,
                ):
                    instagram_bot.stop_bot()
                self.assertLess(time.monotonic() - started, 1.0)
                job = IgPermissionTransitionJob.objects.get(
                    kind=IgPermissionTransitionJob.Kind.GLOBAL_PAUSE
                )
                self.assertEqual(job.status, IgPermissionTransitionJob.Status.PENDING)
                self.assertEqual(job.last_error_kind, "reply_boundary_busy")
                self.assertFalse(capture_reply_permission(self.settings.pk, self.client.pk))
            finally:
                child.terminate()
                child.wait(timeout=5)

            self.assertEqual(
                process_due_permission_transitions(limit=1, lock_path=lock_path),
                1,
            )
            self.settings.refresh_from_db()
            job.refresh_from_db()
            epoch = self.settings.reply_permission_epoch
            self.assertFalse(self.settings.is_enabled)
            self.assertEqual(job.status, IgPermissionTransitionJob.Status.APPLIED)
            self.assertEqual(process_due_permission_transitions(limit=1), 0)
            self.settings.refresh_from_db()
            self.assertEqual(self.settings.reply_permission_epoch, epoch)

    def test_explicit_start_supersedes_a_pending_global_pause(self):
        job = IgPermissionTransitionJob.objects.create(
            kind=IgPermissionTransitionJob.Kind.GLOBAL_PAUSE,
            status=IgPermissionTransitionJob.Status.PENDING,
            settings=self.settings,
            dedupe_key="permission:global_pause:test-pending",
            next_attempt_at=timezone.now(),
        )
        self.assertFalse(capture_reply_permission(self.settings.pk, self.client.pk))

        instagram_bot.start_bot()

        job.refresh_from_db()
        self.settings.refresh_from_db()
        self.assertEqual(job.status, IgPermissionTransitionJob.Status.SUPERSEDED)
        self.assertTrue(self.settings.is_enabled)
        self.assertTrue(capture_reply_permission(self.settings.pk, self.client.pk))

    def test_manager_fallback_dedupe_is_scoped_to_client(self):
        other = IgClient.objects.create(igsid="bounded-manager-other")

        instagram_bot._handle_echo(self.client.igsid, "")
        instagram_bot._handle_echo(other.igsid, "")

        jobs = list(
            IgPermissionTransitionJob.objects.filter(
                kind=IgPermissionTransitionJob.Kind.MANAGER_TAKEOVER
            ).order_by("client_id")
        )
        self.assertEqual(len(jobs), 2)
        self.assertEqual({job.client_id for job in jobs}, {self.client.pk, other.pk})
        self.assertEqual(len({job.dedupe_key for job in jobs}), 2)
        self.assertNotIn(self.client.igsid, jobs[0].dedupe_key)
        self.assertNotIn(other.igsid, jobs[1].dedupe_key)

    def test_status_snapshot_reports_redacted_pause_transition_truth(self):
        secret_text = "customer-secret-text"
        IgPermissionTransitionJob.objects.create(
            kind=IgPermissionTransitionJob.Kind.GLOBAL_PAUSE,
            status=IgPermissionTransitionJob.Status.PENDING,
            settings=self.settings,
            dedupe_key=f"permission:global_pause:{secret_text}",
            next_attempt_at=timezone.now(),
        )

        with (
            patch.object(instagram_bot, "ingress_status", return_value={"healthy": True}),
            patch.object(instagram_bot.cache, "get", return_value={"at": time.time()}),
        ):
            snapshot = instagram_bot.status_snapshot()

        self.assertEqual(snapshot["state"], "pause_pending")
        self.assertTrue(snapshot["pause_pending"])
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["permission_transitions"]["pending"], 1)
        self.assertEqual(snapshot["permission_transitions"]["processing"], 0)
        self.assertEqual(snapshot["permission_transitions"]["failed"], 0)
        self.assertNotIn(secret_text, json.dumps(snapshot, ensure_ascii=False))


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    SECURE_SSL_REDIRECT=False,
)
class ManualClientPauseTransitionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("w11-pause-admin", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.ig_client = IgClient.objects.create(igsid="bounded-manual-pause")

    def test_manual_pause_is_bounded_durable_and_recovers_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "reply.lock")
            child = PermissionTransitionWebhookTests()._lock_holder(lock_path)

            def test_boundary(**kwargs):
                return pause_reply_boundary(lock_path=lock_path, **kwargs)

            try:
                started = time.monotonic()
                with patch(
                    "management.services.ig_reply_boundary.pause_reply_boundary",
                    side_effect=test_boundary,
                ):
                    response = self.client.post(
                        reverse("management_bot_client_pause_api", args=[self.ig_client.pk])
                    )
                self.assertLess(time.monotonic() - started, 1.0)
                self.assertEqual(response.status_code, 200)
                job = IgPermissionTransitionJob.objects.get(
                    kind=IgPermissionTransitionJob.Kind.CLIENT_PAUSE,
                    client=self.ig_client,
                )
                self.assertEqual(job.status, IgPermissionTransitionJob.Status.PENDING)
                self.assertTrue(response.json()["pause_pending"])
                self.assertFalse(
                    capture_reply_permission(self.settings.pk, self.ig_client.pk)
                )
            finally:
                child.terminate()
                child.wait(timeout=5)

            self.assertEqual(
                process_due_permission_transitions(limit=1, lock_path=lock_path),
                1,
            )
            self.ig_client.refresh_from_db()
            job.refresh_from_db()
            epoch = self.ig_client.reply_permission_epoch
            self.assertTrue(self.ig_client.bot_paused)
            self.assertEqual(self.ig_client.paused_reason, "manual")
            self.assertEqual(job.status, IgPermissionTransitionJob.Status.APPLIED)
            self.assertEqual(process_due_permission_transitions(limit=1), 0)
            self.ig_client.refresh_from_db()
            self.assertEqual(self.ig_client.reply_permission_epoch, epoch)


@skipUnlessDBFeature("has_select_for_update_nowait")
class PermissionTransitionNowaitTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled"])
        self.client_row = IgClient.objects.create(igsid="permission-nowait-client")

    def test_http_attempt_returns_bounded_when_client_row_is_locked(self):
        job = create_permission_transition(
            kind=IgPermissionTransitionJob.Kind.CLIENT_PAUSE,
            dedupe_key="permission:client_pause:nowait-client",
            client=self.client_row,
            settings=self.settings,
        )
        locked = threading.Event()
        release = threading.Event()

        def hold_client_row():
            close_old_connections()
            try:
                with transaction.atomic():
                    IgClient.objects.select_for_update().get(pk=self.client_row.pk)
                    locked.set()
                    release.wait(timeout=5)
            finally:
                close_old_connections()

        holder = threading.Thread(target=hold_client_row)
        holder.start()
        self.assertTrue(locked.wait(timeout=2))
        try:
            started = time.monotonic()
            applied = attempt_permission_transition(job.pk)
            elapsed = time.monotonic() - started
        finally:
            release.set()
            holder.join(timeout=5)

        self.assertFalse(applied)
        self.assertLess(elapsed, 1.0)
        job.refresh_from_db()
        self.assertIn(
            job.status,
            {
                IgPermissionTransitionJob.Status.PENDING,
                IgPermissionTransitionJob.Status.PROCESSING,
            },
        )
        self.assertFalse(capture_reply_permission(self.settings.pk, self.client_row.pk))

        self.assertEqual(process_due_permission_transitions(limit=1), 1)
        self.client_row.refresh_from_db()
        epoch = self.client_row.reply_permission_epoch
        self.assertTrue(self.client_row.bot_paused)
        self.assertEqual(process_due_permission_transitions(limit=1), 0)
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.reply_permission_epoch, epoch)
