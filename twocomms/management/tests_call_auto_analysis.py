import os
import stat
import json
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.db import transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from management.models import InstagramBotSettings
from management.services.call_auto_analysis import (
    MARKER_BYTES,
    marker_path,
    publish_call_auto_analysis_marker,
    read_call_auto_analysis_state,
    remove_call_auto_analysis_marker,
    set_call_auto_analysis_enabled,
)


HOST = "management.twocomms.shop"


class CallAutoAnalysisContractPresenceTests(SimpleTestCase):
    def test_model_exposes_provider_neutral_field_on_legacy_column(self):
        field_names = {field.name for field in InstagramBotSettings._meta.fields}

        self.assertIn("call_auto_analysis_enabled", field_names)
        field = InstagramBotSettings._meta.get_field("call_auto_analysis_enabled")
        self.assertEqual(field.db_column, "binotel_ai_enabled")
        self.assertFalse(field.default)

    def test_canonical_state_service_exists(self):
        self.assertIsNotNone(
            find_spec("management.services.call_auto_analysis")
        )


class CallAutoAnalysisStateTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)
        self.settings_override = override_settings(BASE_DIR=self.base_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _save_configured(self, enabled):
        return InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=enabled
        )

    def _write_marker(self, content=MARKER_BYTES, mode=0o600):
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)
        return path

    def test_missing_singleton_is_off_and_read_does_not_create_it(self):
        state = read_call_auto_analysis_state()

        self.assertFalse(state.configured_enabled)
        self.assertFalse(state.marker_enabled)
        self.assertFalse(state.effective_enabled)
        self.assertFalse(state.degraded)
        self.assertEqual(state.code, "disabled")
        self.assertFalse(InstagramBotSettings.objects.exists())

    def test_database_error_fails_closed_without_exception_details(self):
        with patch(
            "management.services.call_auto_analysis.InstagramBotSettings.objects.filter",
            side_effect=DatabaseError("secret database detail"),
        ):
            state = read_call_auto_analysis_state()

        self.assertFalse(state.configured_enabled)
        self.assertFalse(state.effective_enabled)
        self.assertTrue(state.degraded)
        self.assertEqual(state.code, "database_unavailable")
        self.assertNotIn("secret", state.reason.lower())

    def test_valid_private_marker_and_database_flag_enable_effective_state(self):
        self._save_configured(True)
        self._write_marker()

        state = read_call_auto_analysis_state()

        self.assertTrue(state.configured_enabled)
        self.assertTrue(state.marker_enabled)
        self.assertTrue(state.effective_enabled)
        self.assertFalse(state.degraded)
        self.assertEqual(state.code, "enabled")

    def test_enabled_database_flag_without_marker_is_degraded_off(self):
        self._save_configured(True)

        state = read_call_auto_analysis_state()

        self.assertTrue(state.configured_enabled)
        self.assertFalse(state.effective_enabled)
        self.assertTrue(state.degraded)
        self.assertEqual(state.code, "marker_missing")

    def test_marker_without_database_configuration_is_degraded_off(self):
        self._write_marker()

        state = read_call_auto_analysis_state()

        self.assertFalse(state.configured_enabled)
        self.assertTrue(state.marker_enabled)
        self.assertFalse(state.effective_enabled)
        self.assertTrue(state.degraded)
        self.assertEqual(state.code, "marker_without_configuration")

    def test_empty_or_corrupt_marker_is_invalid(self):
        self._save_configured(True)
        for content in (b"", b"call-auto-analysis-enabled-v1", MARKER_BYTES + b"extra"):
            with self.subTest(content=content):
                self._write_marker(content)
                state = read_call_auto_analysis_state()
                self.assertFalse(state.effective_enabled)
                self.assertTrue(state.degraded)
                self.assertEqual(state.code, "marker_invalid")

    def test_directory_fifo_and_symlink_are_not_valid_markers(self):
        self._save_configured(True)
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        path.mkdir()
        state = read_call_auto_analysis_state()
        self.assertEqual(state.code, "marker_not_regular")
        path.rmdir()

        os.mkfifo(path, 0o600)
        state = read_call_auto_analysis_state()
        self.assertEqual(state.code, "marker_not_regular")
        path.unlink()

        target = self.base_dir / "outside"
        target.write_bytes(MARKER_BYTES)
        target.chmod(0o600)
        path.symlink_to(target)
        state = read_call_auto_analysis_state()
        self.assertEqual(state.code, "marker_not_regular")
        self.assertFalse(state.effective_enabled)

    def test_non_private_marker_permissions_fail_closed(self):
        self._save_configured(True)
        self._write_marker(mode=0o644)

        state = read_call_auto_analysis_state()

        self.assertFalse(state.effective_enabled)
        self.assertEqual(state.code, "marker_insecure_permissions")

    def test_unreadable_marker_fails_closed(self):
        self._save_configured(True)
        self._write_marker()
        with patch(
            "management.services.call_auto_analysis.os.open",
            side_effect=PermissionError("private path"),
        ):
            state = read_call_auto_analysis_state()

        self.assertFalse(state.effective_enabled)
        self.assertEqual(state.code, "marker_unreadable")
        self.assertNotIn("private path", state.reason)


class CallAutoAnalysisMarkerMutationTests(SimpleTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)
        self.settings_override = override_settings(BASE_DIR=self.base_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_publish_writes_exact_private_file_and_cleans_temporary_file(self):
        with patch("management.services.call_auto_analysis.os.fsync", wraps=os.fsync) as fsync:
            publish_call_auto_analysis_marker()

        path = marker_path()
        self.assertEqual(path.read_bytes(), MARKER_BYTES)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse(path.is_symlink())
        self.assertEqual([item.name for item in path.parent.iterdir()], [path.name])
        fsync.assert_called()

    def test_publish_atomically_replaces_symlink_without_touching_target(self):
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        outside = self.base_dir / "outside"
        outside.write_bytes(b"keep")
        path.symlink_to(outside)

        publish_call_auto_analysis_marker()

        self.assertFalse(path.is_symlink())
        self.assertEqual(path.read_bytes(), MARKER_BYTES)
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_publish_failure_cleans_temporary_file(self):
        path = marker_path()
        with patch(
            "management.services.call_auto_analysis.os.replace",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(OSError):
                publish_call_auto_analysis_marker()

        self.assertFalse(path.exists())
        self.assertEqual(list(path.parent.iterdir()), [])

    def test_remove_is_idempotent_and_does_not_follow_symlink(self):
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        outside = self.base_dir / "outside"
        outside.write_bytes(b"keep")
        path.symlink_to(outside)

        remove_call_auto_analysis_marker()
        remove_call_auto_analysis_marker()

        self.assertFalse(path.exists())
        self.assertEqual(outside.read_bytes(), b"keep")


class CallAutoAnalysisTransitionTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_override = override_settings(BASE_DIR=Path(self.tmp.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_enable_publishes_only_after_the_database_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = set_call_auto_analysis_enabled(True)
            self.assertFalse(marker_path().exists())

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertTrue(result.configured_enabled)
        committed_state = read_call_auto_analysis_state()
        self.assertTrue(committed_state.effective_enabled)
        self.assertFalse(committed_state.degraded)
        self.assertEqual(committed_state.code, "enabled")
        self.assertEqual(marker_path().read_bytes(), MARKER_BYTES)

    def test_outer_rollback_discards_marker_publication(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            with transaction.atomic():
                set_call_auto_analysis_enabled(True)
                transaction.set_rollback(True)

        self.assertEqual(callbacks, [])
        self.assertFalse(marker_path().exists())
        self.assertFalse(InstagramBotSettings.objects.exists())

    def test_delayed_enable_callback_cannot_override_later_disable(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            set_call_auto_analysis_enabled(True)

        self.assertEqual(len(callbacks), 1)
        disabled = set_call_auto_analysis_enabled(False)
        callbacks[0]()

        configured = InstagramBotSettings.objects.get(pk=1)
        self.assertFalse(configured.call_auto_analysis_enabled)
        self.assertFalse(marker_path().exists())
        self.assertFalse(disabled.effective_enabled)
        self.assertFalse(read_call_auto_analysis_state().effective_enabled)

    def test_publish_failure_compensates_database_to_disabled(self):
        with patch(
            "management.services.call_auto_analysis.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ), patch(
            "management.services.call_auto_analysis.publish_call_auto_analysis_marker",
            side_effect=OSError("private failure detail"),
        ):
            result = set_call_auto_analysis_enabled(True)

        saved = InstagramBotSettings.objects.get(pk=1)
        self.assertFalse(saved.call_auto_analysis_enabled)
        self.assertFalse(marker_path().exists())
        self.assertFalse(result.configured_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertTrue(result.degraded)
        self.assertEqual(result.code, "marker_publish_failed")
        self.assertNotIn("private failure detail", result.reason)

    def test_enable_removes_marker_if_projection_transaction_exit_fails(self):
        real_atomic = transaction.atomic

        class RaiseAfterSuccessfulExit:
            def __init__(self, context):
                self.context = context

            def __enter__(self):
                return self.context.__enter__()

            def __exit__(self, exc_type, exc_value, traceback):
                self.context.__exit__(exc_type, exc_value, traceback)
                raise DatabaseError("private transaction exit detail")

        atomic_contexts = [
            real_atomic(),
            RaiseAfterSuccessfulExit(real_atomic()),
        ]
        with patch(
            "management.services.call_auto_analysis.transaction.atomic",
            side_effect=atomic_contexts,
        ), patch(
            "management.services.call_auto_analysis.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ):
            result = set_call_auto_analysis_enabled(True)

        saved = InstagramBotSettings.objects.get(pk=1)
        self.assertTrue(saved.call_auto_analysis_enabled)
        self.assertFalse(marker_path().exists())
        self.assertTrue(result.configured_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertTrue(result.degraded)
        self.assertEqual(result.code, "database_write_failed")
        self.assertNotIn("private transaction exit detail", result.reason)

    def test_disable_removes_marker_before_database_write_failure(self):
        configured = InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        original_save = InstagramBotSettings.save

        def failing_save(instance, *args, **kwargs):
            self.assertFalse(marker_path().exists())
            if instance.pk == configured.pk:
                raise DatabaseError("private database detail")
            return original_save(instance, *args, **kwargs)

        with patch.object(InstagramBotSettings, "save", new=failing_save):
            result = set_call_auto_analysis_enabled(False)

        configured.refresh_from_db()
        self.assertTrue(configured.call_auto_analysis_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertTrue(result.degraded)
        self.assertEqual(result.code, "database_write_failed")
        self.assertNotIn("private database detail", result.reason)

    def test_disable_persists_off_and_retries_marker_removal_after_first_oserror(self):
        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        real_remove = remove_call_auto_analysis_marker
        attempts = 0

        def flaky_remove():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("private unlink detail")
            real_remove()

        with patch(
            "management.services.call_auto_analysis.remove_call_auto_analysis_marker",
            side_effect=flaky_remove,
        ):
            result = set_call_auto_analysis_enabled(False)

        configured = InstagramBotSettings.objects.get(pk=1)
        self.assertEqual(attempts, 2)
        self.assertFalse(configured.call_auto_analysis_enabled)
        self.assertFalse(marker_path().exists())
        self.assertFalse(result.configured_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertTrue(result.degraded)
        self.assertEqual(result.code, "marker_remove_failed")
        self.assertNotIn("private unlink detail", result.reason)

    def test_disable_rolls_back_database_when_final_marker_removal_fails(self):
        configured = InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        remove_attempts = 0

        def failed_remove():
            nonlocal remove_attempts
            remove_attempts += 1
            raise OSError("private unlink detail")

        with patch(
            "management.services.call_auto_analysis.remove_call_auto_analysis_marker",
            side_effect=failed_remove,
        ):
            result = set_call_auto_analysis_enabled(False)

        configured.refresh_from_db()
        self.assertEqual(remove_attempts, 2)
        self.assertTrue(configured.call_auto_analysis_enabled)
        self.assertEqual(marker_path().read_bytes(), MARKER_BYTES)
        self.assertTrue(result.configured_enabled)
        self.assertTrue(result.marker_enabled)
        self.assertTrue(result.effective_enabled)
        self.assertTrue(result.degraded)
        self.assertEqual(result.code, "marker_remove_failed")
        self.assertNotIn("private unlink detail", result.reason)

    def test_disable_removes_marker_published_after_first_successful_unlink(self):
        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        real_remove = remove_call_auto_analysis_marker
        remove_attempts = 0

        def remove_then_publish_racing_marker():
            nonlocal remove_attempts
            remove_attempts += 1
            real_remove()
            if remove_attempts == 1:
                publish_call_auto_analysis_marker()

        with patch(
            "management.services.call_auto_analysis.remove_call_auto_analysis_marker",
            side_effect=remove_then_publish_racing_marker,
        ):
            result = set_call_auto_analysis_enabled(False)

        configured = InstagramBotSettings.objects.get(pk=1)
        self.assertEqual(remove_attempts, 2)
        self.assertFalse(configured.call_auto_analysis_enabled)
        self.assertFalse(marker_path().exists())
        self.assertFalse(result.configured_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertFalse(result.degraded)
        self.assertEqual(result.code, "disabled")

    def test_disable_preserves_existing_queue_and_call_data(self):
        from management.models import CallRecord

        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        record = CallRecord.objects.create(
            provider="binotel",
            external_call_id="preserve-on-disable",
            ai_status=CallRecord.AiStatus.PENDING,
        )

        result = set_call_auto_analysis_enabled(False)

        record.refresh_from_db()
        self.assertEqual(record.ai_status, CallRecord.AiStatus.PENDING)
        self.assertFalse(result.configured_enabled)
        self.assertFalse(result.effective_enabled)
        self.assertFalse(result.degraded)
        self.assertEqual(result.code, "disabled")


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class CallAutoAnalysisApiTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_override = override_settings(BASE_DIR=Path(self.tmp.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="call-auto-analysis-staff", password="x", is_staff=True
        )
        self.regular = user_model.objects.create_user(
            username="call-auto-analysis-regular", password="x"
        )
        self.url = reverse("management_binotel_ai_toggle")

    def _client_for(self, user, *, csrf=False):
        client = Client(enforce_csrf_checks=csrf)
        client.force_login(user)
        return client

    def test_get_is_staff_only_and_does_not_create_singleton(self):
        regular_response = self._client_for(self.regular).get(
            self.url, HTTP_HOST=HOST, secure=True
        )
        self.assertEqual(regular_response.status_code, 403)

        with patch(
            "management.binotel_views.BinotelClient.from_settings",
            side_effect=AssertionError("state endpoint must not call telephony"),
        ):
            response = self._client_for(self.staff).get(
                self.url, HTTP_HOST=HOST, secure=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "configured": False,
                "effective": False,
                "degraded": False,
                "code": "disabled",
                "reason": "",
            },
        )
        self.assertFalse(InstagramBotSettings.objects.exists())

    def test_post_requires_normal_csrf(self):
        response = self._client_for(self.staff, csrf=True).post(
            self.url,
            data=json.dumps({"enabled": True}),
            content_type="application/json",
            HTTP_HOST=HOST,
            secure=True,
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(InstagramBotSettings.objects.exists())

    def test_get_reports_degraded_state_without_turning_diagnostics_into_error(self):
        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )

        response = self._client_for(self.staff).get(
            self.url, HTTP_HOST=HOST, secure=True
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["configured"])
        self.assertFalse(payload["effective"])
        self.assertTrue(payload["degraded"])
        self.assertEqual(payload["code"], "marker_missing")
        self.assertTrue(payload["reason"])

    def test_post_rejects_non_json_malformed_non_object_and_non_boolean_values(self):
        client = self._client_for(self.staff)
        cases = (
            ({"enabled": "true"}, "application/x-www-form-urlencoded"),
            ("{", "application/json"),
            ([], "application/json"),
            ({}, "application/json"),
            ({"enabled": 1}, "application/json"),
            ({"enabled": "true"}, "application/json"),
            ({"enabled": None}, "application/json"),
        )

        for payload, content_type in cases:
            with self.subTest(payload=payload, content_type=content_type):
                body = payload if isinstance(payload, str) else json.dumps(payload)
                response = client.post(
                    self.url,
                    data=body,
                    content_type=content_type,
                    HTTP_HOST=HOST,
                    secure=True,
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()["success"])

        self.assertFalse(InstagramBotSettings.objects.exists())

    def test_post_enable_returns_structured_effective_state(self):
        client = self._client_for(self.staff)
        with patch(
            "management.services.call_auto_analysis.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ):
            response = client.post(
                self.url,
                data=json.dumps({"enabled": True}),
                content_type="application/json",
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "configured": True,
                "effective": True,
                "degraded": False,
                "code": "enabled",
                "reason": "",
            },
        )

    def test_post_projection_failure_is_safe_conflict(self):
        client = self._client_for(self.staff)
        with patch(
            "management.services.call_auto_analysis.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ), patch(
            "management.services.call_auto_analysis.publish_call_auto_analysis_marker",
            side_effect=OSError("secret filesystem detail"),
        ):
            response = client.post(
                self.url,
                data=json.dumps({"enabled": True}),
                content_type="application/json",
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertFalse(payload["configured"])
        self.assertFalse(payload["effective"])
        self.assertTrue(payload["degraded"])
        self.assertEqual(payload["code"], "marker_publish_failed")
        self.assertNotIn("secret filesystem detail", payload["reason"])

    def test_post_disable_marker_failure_reports_truthful_enabled_conflict(self):
        InstagramBotSettings.objects.create(
            pk=1, call_auto_analysis_enabled=True
        )
        publish_call_auto_analysis_marker()
        client = self._client_for(self.staff)

        with patch(
            "management.services.call_auto_analysis.remove_call_auto_analysis_marker",
            side_effect=OSError("secret filesystem detail"),
        ):
            response = client.post(
                self.url,
                data=json.dumps({"enabled": False}),
                content_type="application/json",
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertTrue(payload["configured"])
        self.assertTrue(payload["effective"])
        self.assertTrue(payload["degraded"])
        self.assertEqual(payload["code"], "marker_remove_failed")
        self.assertNotIn("secret filesystem detail", payload["reason"])


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class CallAutoAnalysisUiTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="call-auto-analysis-ui", password="x", is_staff=True
        )
        self.client.force_login(self.staff)

    def test_card_uses_provider_neutral_copy_and_explicit_status(self):
        response = self.client.get(
            reverse("management_binotel_test"), HTTP_HOST=HOST, secure=True
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        start = html.index('id="call-auto-analysis-card"')
        end = html.index("</section>", start)
        card = html[start:end]
        self.assertIn("Автоаналіз дзвінків", card)
        self.assertIn("Увімкнути автоаналіз дзвінків", card)
        self.assertIn("Вимкнено", card)
        for forbidden in ("Binotel", "Gemini", "ШІ"):
            self.assertNotIn(forbidden, card)

    def test_toggle_javascript_messages_are_provider_neutral(self):
        template_path = (
            Path(__file__).parent
            / "templates"
            / "management"
            / "binotel_test_js.html"
        )
        source = template_path.read_text(encoding="utf-8")
        start = source.index("// call-auto-analysis:start")
        end = source.index("// call-auto-analysis:end")
        toggle_source = source[start:end]

        self.assertIn("Автоаналіз дзвінків увімкнено.", toggle_source)
        self.assertIn("Автоаналіз дзвінків вимкнено.", toggle_source)
        self.assertIn("data.reason", toggle_source)
        for forbidden in ("Binotel", "Gemini", "ШІ"):
            self.assertNotIn(forbidden, toggle_source)

    def test_toggle_applies_structured_effective_state_before_showing_error(self):
        template_path = (
            Path(__file__).parent
            / "templates"
            / "management"
            / "binotel_test_js.html"
        )
        source = template_path.read_text(encoding="utf-8")
        start = source.index("// call-auto-analysis:start")
        end = source.index("// call-auto-analysis:end")
        toggle_source = source[start:end]

        apply_effective = "input.checked=Boolean(data.effective);"
        reject_error = "if(!data.success) throw new Error(data.reason||errText(data));"
        self.assertIn(apply_effective, toggle_source)
        self.assertIn(reject_error, toggle_source)
        self.assertIn("if(!hasEffectiveState){", toggle_source)
        self.assertLess(
            toggle_source.index(apply_effective),
            toggle_source.index(reject_error),
        )
