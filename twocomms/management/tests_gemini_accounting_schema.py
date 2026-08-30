import importlib
from unittest.mock import Mock

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import (
    GeminiModelQuotaUsage,
    GeminiQuotaProfile,
    GeminiQuotaState,
    GeminiRequest,
    GeminiRequestAttempt,
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
        request = GeminiRequest.objects.create(
            request_id="schema-request-1",
            lane="live",
            task_class="complex_live",
            candidate_plan=[{
                "candidate_index": 1,
                "project_identity": "project-1",
                "model": profile.model,
            }],
            candidate_plan_digest="a" * 64,
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


class GeminiAccountingMigrationContractTests(SimpleTestCase):
    def test_schema_migration_is_exactly_after_routing_and_seeds_profiles_last(self):
        migration = importlib.import_module(
            "management.migrations.0178_geminirequestattempt_accounting_mode_and_more"
        )
        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0177_gemini_adaptive_routing")],
        )
        create_profile_index = next(
            index
            for index, operation in enumerate(migration.Migration.operations)
            if operation.__class__.__name__ == "CreateModel"
            and operation.name == "GeminiQuotaProfile"
        )
        seed_index = next(
            index
            for index, operation in enumerate(migration.Migration.operations)
            if operation.__class__.__name__ == "RunPython"
            and operation.code is migration.seed_owner_observed_profiles
        )
        self.assertLess(create_profile_index, seed_index)
        self.assertEqual(len(migration.PROFILE_MODELS), 4)
        self.assertNotIn("key", migration.PROFILE_VERSION.casefold())

    def test_engine_migration_is_separate_non_atomic_and_complete(self):
        migration = importlib.import_module(
            "management.migrations.0179_gemini_accounting_v2_innodb"
        )
        self.assertFalse(migration.Migration.atomic)
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
            "management.migrations.0179_gemini_accounting_v2_innodb"
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
            "management.migrations.0179_gemini_accounting_v2_innodb"
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
