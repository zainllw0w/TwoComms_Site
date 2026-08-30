#!/usr/bin/env python3
"""Kill/retry proof for Analysis V2 0183 on a guarded disposable MariaDB DB."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(r"^test_twocomms_[A-Za-z0-9_]+$")
KILL_EXIT_CODE = 97
TARGET = ("management", "0183_analysis_v2_result_proposals")
BEFORE = ("management", "0182_analysis_materiality_ledger")
PROPOSAL_TABLE = "management_iganalysisproposal"


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--phase", choices=("orchestrate", "kill"), default="orchestrate")
    return parser.parse_args()


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError("DJANGO_SETTINGS_MODULE must be test_settings_mariadb")
    import django

    django.setup()
    from django.db import connection

    database = str(connection.settings_dict.get("NAME") or "")
    if connection.vendor != "mysql" or not DISPOSABLE_NAME_RE.fullmatch(database):
        raise RuntimeError("refusing non-disposable or non-MariaDB database")
    return connection, database


def _kill_phase(args):
    connection, _database = _setup(args)
    from django.db.migrations.executor import MigrationExecutor

    schema_editor_class = connection.SchemaEditorClass
    original = schema_editor_class.create_model

    def kill_after_result(self, model):
        result = original(self, model)
        if model._meta.db_table == "management_igconversationanalysisresult":
            os._exit(KILL_EXIT_CODE)
        return result

    schema_editor_class.create_model = kill_after_result
    MigrationExecutor(connection).migrate([TARGET])
    raise RuntimeError("kill phase reached the end without interruption")


def _orchestrate(args):
    connection, database = _setup(args)
    from django.db import close_old_connections
    from django.db.migrations.executor import MigrationExecutor

    MigrationExecutor(connection).migrate([BEFORE])
    child = subprocess.run(
        [
            sys.executable,
            os.path.abspath(__file__),
            "--confirm-disposable",
            "--phase",
            "kill",
        ],
        env=os.environ.copy(),
        check=False,
        timeout=180,
    )
    if child.returncode != KILL_EXIT_CODE:
        raise RuntimeError(
            f"kill phase returned {child.returncode}, expected {KILL_EXIT_CODE}"
        )
    close_old_connections()
    from django.db import connection as resumed_connection

    MigrationExecutor(resumed_connection).migrate([TARGET])
    tables = (
        "management_igconversationanalysisresult",
        "management_iganalysisproposal",
    )
    with resumed_connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s)"
            % ", ".join(["%s"] * len(tables)),
            list(tables),
        )
        engines = {
            str(table): str(engine).upper()
            for table, engine in cursor.fetchall()
        }
        cursor.execute(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME IN (%s, %s, %s, %s)",
            [
                "ig_anres_no_update", "ig_anres_no_delete",
                "ig_anprop_no_delete", "ig_anprop_identity_update",
            ],
        )
        triggers = sorted(str(row[0]) for row in cursor.fetchall())
    if set(engines) != set(tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected Analysis V2 engines: {engines}")
    if triggers != sorted([
        "ig_anres_no_update", "ig_anres_no_delete", "ig_anprop_no_delete",
        "ig_anprop_identity_update",
    ]):
        raise RuntimeError(f"unexpected Analysis V2 triggers: {triggers}")
    from django.db import DatabaseError
    from django.utils import timezone
    from management.models import (
        IgAnalysisProposal,
        IgClient,
        IgConversationAnalysisResult,
        IgConversationAnalysisSnapshot,
    )

    client = IgClient.objects.create(igsid="analysis-v2-0183-mariadb-proof")
    snapshot = IgConversationAnalysisSnapshot.objects.create(
        client=client,
        dedupe_key="analysis-v2-0183-mariadb-proof:snapshot",
        score_band=IgConversationAnalysisSnapshot.Band.COLD,
    )
    result = IgConversationAnalysisResult.objects.create(
        result_key="analysis-v2:" + hashlib.sha256(b"mariadb-proof-result").hexdigest(),
        legacy_snapshot=snapshot,
        client=client,
        watermark_message_id=1,
        job_revision=1,
        materiality_event_highwater=1,
        materiality_digest="a" * 64,
        state_correlation="b" * 64,
        result_schema_version="analysis-v2.1",
        normalizer_version="analysis-v2-normalizer.1",
        score_band=IgConversationAnalysisSnapshot.Band.COLD,
        result_digest="c" * 64,
        analyzed_at=timezone.now(),
    )
    proposal = IgAnalysisProposal.objects.create(
        proposal_key=(
            "analysis-proposal:"
            + hashlib.sha256(b"mariadb-proof-proposal").hexdigest()
        ),
        analysis_result=result,
        ordinal=1,
        client=client,
        proposal_type=IgAnalysisProposal.ProposalType.REQUEST_CLARIFICATION,
        target_scope=IgAnalysisProposal.TargetScope.CLIENT,
        typed_value={"reason_codes": ["product_conflict"]},
        evidence_message_ids=[1],
        confidence="1.0000",
        source_result_digest=result.result_digest,
        expected_materiality_digest=result.materiality_digest,
        expected_state_correlation=result.state_correlation,
    )
    decided_at = timezone.now()
    with resumed_connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {PROPOSAL_TABLE} "
            "SET status=%s, decision_code=%s, projector_version=%s, "
            "decided_at=%s, updated_at=%s WHERE id=%s",
            [
                "shadow_validated", "shadow_valid",
                "analysis-v2-projector.1", decided_at, decided_at, proposal.pk,
            ],
        )
    proposal.refresh_from_db()
    mutable_update_ok = (
        proposal.status == "shadow_validated"
        and proposal.decision_code == "shadow_valid"
        and proposal.projector_version == "analysis-v2-projector.1"
    )
    identity_update_rejected = False
    try:
        with resumed_connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {PROPOSAL_TABLE} SET typed_value=%s WHERE id=%s",
                [json.dumps({"reason_codes": ["recipient_conflict"]}), proposal.pk],
            )
    except DatabaseError:
        identity_update_rejected = True
    if not mutable_update_ok or not identity_update_rejected:
        raise RuntimeError(
            "proposal trigger behavior mismatch: "
            f"mutable={mutable_update_ok}, identity_rejected={identity_update_rejected}"
        )
    print("IG_ANALYSIS_V2_0183_MARIADB_RETRY=" + json.dumps({
        "database": database,
        "kill_exit_code": child.returncode,
        "engines": engines,
        "triggers": triggers,
        "proposal_mutable_update": mutable_update_ok,
        "proposal_identity_update_rejected": identity_update_rejected,
    }, sort_keys=True))


def main():
    args = _arguments()
    if args.phase == "kill":
        _kill_phase(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
