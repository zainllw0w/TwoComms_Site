import datetime
import importlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from management.models import (
    GeminiModelQuotaUsage,
    GeminiQuotaProfile,
    GeminiQuotaState,
    GeminiRequest,
    GeminiRequestAttempt,
)
from management.services.gemini_accounting_contract import (
    canonical_candidate_plan_digest,
)
from management.services.ig_engine_health import IG_RUNTIME_TABLES


PROFILE_VERSION = "owner-observed-2026-08-29.v1"
EXPECTED_PROFILES = {
    "gemini-3.7-flash": (5, 250_000, 20, 1),
    "gemini-3.6-flash": (5, 250_000, 20, 1),
    "gemini-3.5-flash": (5, 250_000, 20, 1),
    "gemini-3.5-flash-lite": (15, 250_000, 500, 2),
}


class GeminiAccountingSchemaTests(TestCase):
    def test_migration_seeds_only_four_non_secret_profiles(self):
        profiles = {
            row.model: (
                row.rpm_limit,
                row.input_tpm_limit,
                row.rpd_limit,
                row.permit_limit,
            )
            for row in GeminiQuotaProfile.objects.filter(
                profile_version=PROFILE_VERSION
            )
        }

        self.assertEqual(profiles, EXPECTED_PROFILES)
        for row in GeminiQuotaProfile.objects.filter(profile_version=PROFILE_VERSION):
            self.assertEqual(row.source, GeminiQuotaProfile.Source.OWNER_OBSERVED)
            self.assertEqual(row.source_reference, "owner_ai_studio_screenshot")
            self.assertEqual(row.estimator_version, "shadow-calibration-required")

    def test_profile_seed_creates_zero_usage_state_or_request_rows(self):
        """S3a seeds policy only; it cannot claim that any project used quota."""
        self.assertEqual(GeminiQuotaProfile.objects.count(), 4)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)
        self.assertEqual(GeminiRequest.objects.count(), 0)
        self.assertEqual(GeminiRequestAttempt.objects.count(), 0)
        self.assertEqual(GeminiModelQuotaUsage.objects.count(), 0)

    def test_request_attempt_graph_and_winner_fk_are_additive(self):
        profile = GeminiQuotaProfile.objects.get(
            profile_version=PROFILE_VERSION,
            model="gemini-3.7-flash",
        )
        candidate_plan = [{
            "candidate_index": 1,
            "project_identity": "project-1",
            "model": profile.model,
        }]
        request = GeminiRequest.objects.create(
            request_id="schema-request-1",
            lane="live",
            task_class="complex_live",
            candidate_plan=candidate_plan,
            candidate_plan_digest=canonical_candidate_plan_digest(candidate_plan),
        )
        attempt = GeminiRequestAttempt.objects.create(
            request_id=request.request_id,
            request_graph=request,
            role="chat",
            key_name="",
            project_identity="project-1",
            model=profile.model,
            outcome="planned",
            fsm_state=GeminiRequestAttempt.FsmState.PLANNED,
            quota_profile=profile,
            attempt_index=1,
            candidate_index=1,
        )
        request.winner_attempt = attempt
        request.save(update_fields=["winner_attempt", "updated_at"])

        request.refresh_from_db()
        self.assertEqual(request.winner_attempt_id, attempt.pk)
        self.assertEqual(list(request.attempts.values_list("pk", flat=True)), [attempt.pk])

    def test_attempt_index_is_unique_inside_one_v2_request(self):
        request = GeminiRequest.objects.create(request_id="schema-request-unique")
        GeminiRequestAttempt.objects.create(
            request_id=request.request_id,
            request_graph=request,
            role="chat",
            key_name="",
            model="gemini-3.5-flash-lite",
            outcome="planned",
            attempt_index=1,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeminiRequestAttempt.objects.create(
                request_id=request.request_id,
                request_graph=request,
                role="chat",
                key_name="",
                model="gemini-3.5-flash-lite",
                outcome="planned",
                attempt_index=1,
            )

    def test_provider_started_attempt_requires_original_dispatch_day(self):
        request = GeminiRequest.objects.create(request_id="schema-request-day")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeminiRequestAttempt.objects.create(
                request_id=request.request_id,
                request_graph=request,
                role="chat",
                key_name="",
                model="gemini-3.5-flash-lite",
                outcome="started",
                fsm_state=GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
                attempt_index=1,
                provider_started_at=timezone.now(),
            )

    def test_profile_and_state_pair_constraints_are_real(self):
        profile = GeminiQuotaProfile.objects.get(
            profile_version=PROFILE_VERSION,
            model="gemini-3.6-flash",
        )
        GeminiQuotaState.objects.create(
            project_identity="project-1",
            model=profile.model,
            quota_profile=profile,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeminiQuotaState.objects.create(
                project_identity="project-1",
                model=profile.model,
                quota_profile=profile,
            )

    def test_profile_effective_window_must_move_forward(self):
        instant = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeminiQuotaProfile.objects.create(
                profile_version="invalid-window.v1",
                model="gemini-test",
                rpm_limit=1,
                input_tpm_limit=1,
                rpd_limit=1,
                permit_limit=1,
                estimator_version="test",
                source=GeminiQuotaProfile.Source.ADMIN,
                observed_at=instant,
                effective_from=instant,
                effective_until=instant,
            )

    def test_quota_profile_is_append_only_through_model_and_queryset_paths(self):
        profile = GeminiQuotaProfile.objects.get(
            profile_version=PROFILE_VERSION,
            model="gemini-3.7-flash",
        )
        profile.rpd_limit = 21
        with self.assertRaisesMessage(ValidationError, "append-only"):
            profile.save(update_fields=["rpd_limit"])
        with self.assertRaisesMessage(ValidationError, "append-only"):
            GeminiQuotaProfile.objects.filter(pk=profile.pk).update(rpd_limit=21)
        with self.assertRaisesMessage(ValidationError, "append-only"):
            GeminiQuotaProfile.objects.bulk_update([profile], ["rpd_limit"])
        with self.assertRaisesMessage(ValidationError, "append-only"):
            GeminiQuotaProfile.objects.bulk_create(
                [profile],
                update_conflicts=True,
                update_fields=["rpd_limit"],
                unique_fields=["id"],
            )
        with self.assertRaisesMessage(ValidationError, "append-only"):
            profile.delete()
        with self.assertRaisesMessage(ValidationError, "append-only"):
            GeminiQuotaProfile.objects.filter(pk=profile.pk).delete()

        profile.refresh_from_db()
        self.assertEqual(profile.rpd_limit, 20)

    def test_attempt_request_id_must_match_parent_graph(self):
        request = GeminiRequest.objects.create(request_id="graph-request-id")
        with self.assertRaisesMessage(ValidationError, "does not match"):
            GeminiRequestAttempt.objects.create(
                request_id="different-request-id",
                request_graph=request,
                role="chat",
                key_name="",
                model="gemini-3.5-flash-lite",
                outcome="planned",
                attempt_index=1,
            )

    def test_attempt_and_state_model_must_match_profile(self):
        profile = GeminiQuotaProfile.objects.get(
            profile_version=PROFILE_VERSION,
            model="gemini-3.6-flash",
        )
        request = GeminiRequest.objects.create(request_id="profile-mismatch-request")
        with self.assertRaisesMessage(ValidationError, "does not match"):
            GeminiRequestAttempt.objects.create(
                request_id=request.request_id,
                request_graph=request,
                role="chat",
                key_name="",
                model="gemini-3.7-flash",
                quota_profile=profile,
                outcome="planned",
                attempt_index=1,
            )
        with self.assertRaisesMessage(ValidationError, "does not match"):
            GeminiQuotaState.objects.create(
                project_identity="project-mismatch",
                model="gemini-3.7-flash",
                quota_profile=profile,
            )

    def test_winner_must_belong_to_the_same_request_graph(self):
        first = GeminiRequest.objects.create(request_id="winner-graph-first")
        second = GeminiRequest.objects.create(request_id="winner-graph-second")
        second_attempt = GeminiRequestAttempt.objects.create(
            request_id=second.request_id,
            request_graph=second,
            role="chat",
            key_name="",
            model="gemini-3.5-flash-lite",
            outcome="succeeded",
            attempt_index=1,
        )
        first.winner_attempt = second_attempt

        with self.assertRaisesMessage(ValidationError, "another request graph"):
            first.save(update_fields=["winner_attempt", "updated_at"])

    def test_candidate_plan_digest_is_correct_and_immutable(self):
        bad_plan = [{"candidate_index": 1, "model": "gemini-3.5-flash-lite"}]
        with self.assertRaisesMessage(ValidationError, "does not match"):
            GeminiRequest.objects.create(
                request_id="candidate-bad-digest",
                candidate_plan=bad_plan,
                candidate_plan_digest="0" * 64,
            )

        plan = [{
            "candidate_index": 1,
            "project_identity": "project-1",
            "model": "gemini-3.5-flash-lite",
        }]
        request = GeminiRequest.objects.create(
            request_id="candidate-immutable",
            candidate_plan=plan,
            candidate_plan_digest=canonical_candidate_plan_digest(plan),
        )
        changed = [*plan, {
            "candidate_index": 2,
            "project_identity": "project-2",
            "model": "gemini-3.5-flash-lite",
        }]
        request.candidate_plan = changed
        request.candidate_plan_digest = canonical_candidate_plan_digest(changed)
        with self.assertRaisesMessage(ValidationError, "immutable"):
            request.save(update_fields=["candidate_plan", "candidate_plan_digest"])
        with self.assertRaisesMessage(ValidationError, "contract boundary"):
            GeminiRequest.objects.filter(pk=request.pk).update(
                candidate_plan=changed,
                candidate_plan_digest=canonical_candidate_plan_digest(changed),
            )

        request.refresh_from_db()
        self.assertEqual(request.candidate_plan, plan)


class GeminiAccountingMigrationContractTests(TestCase):
    def test_engine_prerequisite_precedes_every_v2_fk_ddl(self):
        prerequisite = importlib.import_module(
            "management.migrations.0178_gemini_accounting_prerequisite_innodb"
        )
        schema = importlib.import_module(
            "management.migrations.0179_gemini_accounting_v2_schema"
        )
        self.assertEqual(
            prerequisite.Migration.dependencies,
            [("management", "0177_gemini_adaptive_routing")],
        )
        self.assertFalse(prerequisite.Migration.atomic)
        self.assertEqual(
            prerequisite.PREREQUISITE_TABLES,
            (
                "management_geminirequestattempt",
                "management_geminimodelquotausage",
            ),
        )
        self.assertEqual(
            schema.Migration.dependencies,
            [("management", "0178_gemini_accounting_prerequisite_innodb")],
        )
        self.assertFalse(any(
            operation.__class__.__name__ == "RunPython"
            for operation in schema.Migration.operations
        ))

    def test_prerequisite_conversion_is_retry_idempotent_after_partial_progress(self):
        migration = importlib.import_module(
            "management.migrations.0178_gemini_accounting_prerequisite_innodb"
        )
        first_cursor = Mock()
        first_cursor.__enter__ = Mock(return_value=first_cursor)
        first_cursor.__exit__ = Mock(return_value=False)
        first_cursor.fetchone.side_effect = [("MyISAM",), RuntimeError("interrupted")]
        first_editor = Mock()
        first_editor.connection.vendor = "mysql"
        first_editor.connection.cursor.return_value = first_cursor
        first_editor.quote_name.side_effect = lambda value: f"`{value}`"

        with self.assertRaisesMessage(RuntimeError, "interrupted"):
            migration.ensure_prerequisite_tables_innodb(None, first_editor)
        first_editor.execute.assert_called_once_with(
            "ALTER TABLE `management_geminirequestattempt` ENGINE=InnoDB"
        )

        retry_cursor = Mock()
        retry_cursor.__enter__ = Mock(return_value=retry_cursor)
        retry_cursor.__exit__ = Mock(return_value=False)
        retry_cursor.fetchone.side_effect = [("InnoDB",), ("InnoDB",)]
        retry_editor = Mock()
        retry_editor.connection.vendor = "mysql"
        retry_editor.connection.cursor.return_value = retry_cursor

        migration.ensure_prerequisite_tables_innodb(None, retry_editor)
        retry_editor.execute.assert_not_called()

    def test_profile_seed_is_separate_retry_idempotent_and_drift_detecting(self):
        migration = importlib.import_module(
            "management.migrations.0180_seed_gemini_quota_profiles"
        )
        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0179_gemini_accounting_v2_schema")],
        )
        self.assertEqual(len(migration.PROFILE_MODELS), 4)
        self.assertNotIn("key", migration.PROFILE_VERSION.casefold())

        before = GeminiQuotaProfile.objects.count()
        migration.seed_owner_observed_profiles(django_apps, None)
        self.assertEqual(GeminiQuotaProfile.objects.count(), before)

        expected_time = datetime.datetime(
            2026, 8, 29, 17, 18, 56, tzinfo=datetime.timezone.utc
        )
        drifted = SimpleNamespace(
            rpm_limit=99,
            input_tpm_limit=250_000,
            rpd_limit=20,
            permit_limit=1,
            estimator_version="shadow-calibration-required",
            source="owner_observed",
            source_reference="owner_ai_studio_screenshot",
            observed_at=expected_time,
            effective_from=expected_time,
            effective_until=None,
        )
        historical_model = Mock()
        historical_model.objects.get_or_create.return_value = (drifted, False)
        historical_apps = Mock()
        historical_apps.get_model.return_value = historical_model

        with self.assertRaisesMessage(RuntimeError, "profile drift"):
            migration.seed_owner_observed_profiles(historical_apps, None)

    def test_engine_migration_is_separate_non_atomic_and_complete(self):
        migration = importlib.import_module(
            "management.migrations.0181_gemini_accounting_v2_innodb"
        )
        self.assertFalse(migration.Migration.atomic)
        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0180_seed_gemini_quota_profiles")],
        )
        self.assertEqual(
            set(migration.GEMINI_ACCOUNTING_TABLES),
            {
                "management_geminiquotaprofile",
                "management_geminiquotastate",
                "management_geminirequest",
                "management_geminirequestattempt",
                "management_geminimodelquotausage",
            },
        )

    def test_engine_conversion_changes_only_non_innodb_tables(self):
        migration = importlib.import_module(
            "management.migrations.0181_gemini_accounting_v2_innodb"
        )
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.side_effect = [
            ("InnoDB",),
            ("MyISAM",),
            ("InnoDB",),
            ("InnoDB",),
            ("InnoDB",),
        ]
        schema_editor = Mock()
        schema_editor.connection.vendor = "mysql"
        schema_editor.connection.cursor.return_value = cursor
        schema_editor.quote_name.side_effect = lambda value: f"`{value}`"

        migration.ensure_gemini_accounting_tables_innodb(None, schema_editor)

        schema_editor.execute.assert_called_once_with(
            "ALTER TABLE `management_geminiquotastate` ENGINE=InnoDB"
        )

    def test_engine_conversion_fails_if_a_required_table_is_missing(self):
        migration = importlib.import_module(
            "management.migrations.0181_gemini_accounting_v2_innodb"
        )
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = None
        schema_editor = Mock()
        schema_editor.connection.vendor = "mysql"
        schema_editor.connection.cursor.return_value = cursor

        with self.assertRaisesMessage(
            RuntimeError,
            "required Gemini accounting table is missing: "
            "management_geminiquotaprofile",
        ):
            migration.ensure_gemini_accounting_tables_innodb(None, schema_editor)

    def test_engine_registry_declares_every_v2_and_legacy_quota_table(self):
        for table in (
            "management_geminimodelquotausage",
            "management_geminiquotaprofile",
            "management_geminiquotastate",
            "management_geminirequest",
            "management_geminirequestattempt",
        ):
            with self.subTest(table=table):
                self.assertIn(table, IG_RUNTIME_TABLES)

    def test_forward_migration_preserves_legacy_attempt_and_usage(self):
        script = textwrap.dedent(
            """
            import datetime
            import json
            import os
            import sys

            os.environ["DJANGO_SETTINGS_MODULE"] = "twocomms.settings"
            from django.conf import settings
            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sys.argv[1],
            }

            import django
            django.setup()

            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor

            migrate_from = ("management", "0177_gemini_adaptive_routing")
            migrate_to = ("management", "0181_gemini_accounting_v2_innodb")

            executor = MigrationExecutor(connection)
            executor.migrate([migrate_from])
            executor = MigrationExecutor(connection)
            old_apps = executor.loader.project_state([migrate_from]).apps
            Attempt = old_apps.get_model("management", "GeminiRequestAttempt")
            Usage = old_apps.get_model("management", "GeminiModelQuotaUsage")
            attempt = Attempt.objects.create(
                request_id="legacy-request",
                role="chat",
                key_name="GEMINI_API",
                model="gemini-3.7-flash",
                outcome="failed",
                failure_kind="quota_429",
                attempt_index=3,
            )
            usage = Usage.objects.create(
                key_name="GEMINI_API",
                model="gemini-3.7-flash",
                day_date=datetime.date(2026, 8, 29),
                requests=3,
                tokens=321,
            )

            executor = MigrationExecutor(connection)
            executor.migrate([migrate_to])
            executor = MigrationExecutor(connection)
            new_apps = executor.loader.project_state([migrate_to]).apps
            AttemptV2 = new_apps.get_model("management", "GeminiRequestAttempt")
            UsageV1 = new_apps.get_model("management", "GeminiModelQuotaUsage")
            Profile = new_apps.get_model("management", "GeminiQuotaProfile")
            State = new_apps.get_model("management", "GeminiQuotaState")
            Request = new_apps.get_model("management", "GeminiRequest")
            attempt_v2 = AttemptV2.objects.get(pk=attempt.pk)
            usage_v1 = UsageV1.objects.get(pk=usage.pk)

            print("MIGRATION_RESULT=" + json.dumps({
                "attempt": {
                    "request_id": attempt_v2.request_id,
                    "outcome": attempt_v2.outcome,
                    "failure_kind": attempt_v2.failure_kind,
                    "attempt_index": attempt_v2.attempt_index,
                    "fsm_state": attempt_v2.fsm_state,
                    "request_graph_id": attempt_v2.request_graph_id,
                    "project_identity": attempt_v2.project_identity,
                },
                "usage": {
                    "requests": usage_v1.requests,
                    "tokens": usage_v1.tokens,
                },
                "seed": {
                    "profiles": Profile.objects.count(),
                    "states": State.objects.count(),
                    "requests": Request.objects.count(),
                },
            }, sort_keys=True))
            """
        )
        project_root = os.path.dirname(os.path.dirname(__file__))
        env = os.environ.copy()
        for key in (
            "DB_ENGINE",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
            "DB_PORT",
        ):
            env.pop(key, None)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (project_root, env.get("PYTHONPATH", "")))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, "-c", script, os.path.join(temp_dir, "migration.sqlite3")],
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        marker = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("MIGRATION_RESULT=")
        )
        payload = json.loads(marker.removeprefix("MIGRATION_RESULT="))
        self.assertEqual(payload["attempt"], {
            "attempt_index": 3,
            "failure_kind": "quota_429",
            "fsm_state": "legacy",
            "outcome": "failed",
            "project_identity": "",
            "request_graph_id": None,
            "request_id": "legacy-request",
        })
        self.assertEqual(payload["usage"], {"requests": 3, "tokens": 321})
        self.assertEqual(
            payload["seed"],
            {"profiles": 4, "requests": 0, "states": 0},
        )
