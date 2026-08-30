#!/usr/bin/env python3
"""Guarded runner for the disposable MariaDB S3b concurrency proof."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier


DISPOSABLE_NAME_RE = re.compile(r"^test_twocomms_[A-Za-z0-9_]+$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--focused-existing", action="store_true")
    args = parser.parse_args()
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != "test_settings_mariadb":
        raise RuntimeError("DJANGO_SETTINGS_MODULE must be test_settings_mariadb")
    if not DISPOSABLE_NAME_RE.fullmatch(
        str(os.environ.get("TEST_MARIADB_NAME") or "")
    ):
        raise RuntimeError("TEST_MARIADB_NAME must be an explicit test_twocomms_* database")

    django_root = Path(__file__).resolve().parents[1] / "twocomms"
    sys.path.insert(0, str(django_root))

    import django

    django.setup()
    from django.db import connection
    from django.test.runner import DiscoverRunner

    if connection.vendor != "mysql" or not DISPOSABLE_NAME_RE.fullmatch(
        str(connection.settings_dict.get("NAME") or "")
    ):
        raise RuntimeError("refusing a non-disposable or non-MariaDB database")
    if args.focused_existing:
        _run_focused_existing(connection)
        return
    runner = DiscoverRunner(verbosity=2, interactive=False, keepdb=False)
    failures = runner.run_tests([
        "management.tests_gemini_accounting_shadow_mariadb",
    ])
    if failures:
        raise SystemExit(1)


def _run_focused_existing(connection) -> None:
    """Run S3b against a preseeded disposable DB when unrelated migrations fail."""
    from django.db import close_old_connections
    from django.db.migrations.recorder import MigrationRecorder
    from django.test import override_settings

    if not MigrationRecorder(connection).migration_qs.filter(
        app="management",
        name="0181_gemini_accounting_v2_innodb",
    ).exists():
        raise RuntimeError("management.0181 must be applied before focused S3b proof")

    required_tables = (
        "management_geminiquotaprofile",
        "management_geminiquotastate",
        "management_geminirequest",
        "management_geminirequestattempt",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (%s)"
            % ", ".join(["%s"] * len(required_tables)),
            list(required_tables),
        )
        engines = {
            str(table): str(engine).upper()
            for table, engine in cursor.fetchall()
        }
    if set(engines) != set(required_tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected focused accounting engines: {engines}")

    from management.models import (
        GeminiQuotaProfile,
        GeminiQuotaState,
        GeminiRequest,
        GeminiRequestAttempt,
    )
    from management.services import gemini_accounting_runtime as runtime

    if GeminiQuotaProfile.objects.filter(
        profile_version=runtime.OWNER_PROFILE_VERSION
    ).count() != 4:
        raise RuntimeError("four owner-observed profiles are required")
    # This database is explicitly disposable. Clear only S3b runtime evidence;
    # profiles and every unrelated application table remain untouched.
    GeminiRequest._base_manager.update(winner_attempt_id=None)
    GeminiRequestAttempt._base_manager.all().delete()
    GeminiRequest._base_manager.all().delete()
    GeminiQuotaState._base_manager.all().delete()

    start = Barrier(2)
    dispatched = Barrier(2)
    model = "gemini-3.7-flash"

    def worker(index: int):
        close_old_connections()
        try:
            observer = runtime.begin_request(
                request_id=f"focused-maria-shadow-{index}",
                role="management",
                reasoning_task="customer_intelligence",
                candidate_plan=[{
                    "candidate_index": 1,
                    "key_name": "GEMINI_API",
                    "project_identity": "gemini-project-focused",
                    "identity_status": "known",
                    "model": model,
                    "skip_reason": "",
                }],
                lane="analysis",
            )
            boundary = observer.attempt(
                key_name="GEMINI_API", model=model, candidate_index=1
            )
            start.wait(timeout=10)
            boundary.before_provider(serialized_bytes=128, inline_count=0)
            if boundary.attempt_id is None:
                raise RuntimeError("shadow provider boundary was not persisted")
            dispatched.wait(timeout=10)
            boundary.manual_result(
                succeeded=True,
                http_code=200,
                usage={
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 14,
                },
            )
            return boundary.attempt_id
        finally:
            close_old_connections()

    with override_settings(
        GEMINI_ACCOUNTING_V2_MODE="shadow",
        GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM="2026-08-29T00:00:00-07:00",
        GEMINI_ACCOUNTING_IDENTITY_HMAC_KEY="focused-maria-shadow-key",
        GEMINI_KEY_PROJECT_GROUPS={"GEMINI_API": "gemini-project-focused"},
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            attempt_ids = list(executor.map(worker, (1, 2)))

    rows = GeminiRequestAttempt.objects.filter(pk__in=attempt_ids)
    state = GeminiQuotaState.objects.get(
        project_identity="gemini-project-focused", model=model
    )
    result = {
        "attempts": rows.count(),
        "succeeded": rows.filter(
            fsm_state=GeminiRequestAttempt.FsmState.SUCCEEDED
        ).count(),
        "shadow_permit_denies": rows.filter(
            shadow_decision=GeminiRequestAttempt.ShadowDecision.DENY,
            shadow_deny_reason="permit_exhausted",
        ).count(),
        "rpd_dispatched": state.rpd_dispatched,
        "in_flight": state.in_flight_count,
        "engines": engines,
    }
    expected = {
        "attempts": 2,
        "succeeded": 2,
        "shadow_permit_denies": 1,
        "rpd_dispatched": 2,
        "in_flight": 0,
    }
    if any(result[key] != value for key, value in expected.items()):
        raise RuntimeError(f"focused S3b concurrency mismatch: {result}")
    print("GEMINI_S3B_MARIADB=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
