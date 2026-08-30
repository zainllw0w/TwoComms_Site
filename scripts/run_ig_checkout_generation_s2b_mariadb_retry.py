#!/usr/bin/env python3
"""Kill/resume and concurrency proof for guarded disposable checkout S2b DB."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from datetime import timedelta
from pathlib import Path


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(
    r"^test_twocomms_checkout_s2b_[A-Za-z0-9_]+$"
)
KILL_EXIT_CODE = 97
TARGET = ("management", "0184_assisted_checkout_generation_v2")
BEFORE = (
    ("management", "0183_analysis_v2_result_proposals"),
    ("orders", "0058_paymentattempt_checkout_series"),
)
PROJECT_ROOT = Path(__file__).resolve().parents[1] / "twocomms"


def _arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--phase", choices=("orchestrate", "kill"), default="orchestrate")
    return parser.parse_args(argv)


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError(f"DJANGO_SETTINGS_MODULE must be {EXPECTED_SETTINGS}")
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    import django

    django.setup()
    from django.db import connection

    database = str(connection.settings_dict.get("NAME") or "")
    if (
        connection.vendor != "mysql"
        or not DISPOSABLE_NAME_RE.fullmatch(database)
        or len(database) > 64
    ):
        raise RuntimeError("refusing non-disposable or non-MariaDB database")
    return connection, database


def _kill_phase(args):
    connection, _database = _setup(args)
    from django.db.migrations.executor import MigrationExecutor

    schema_editor_class = connection.SchemaEditorClass
    original = schema_editor_class.create_model

    def kill_after_generation(self, model):
        result = original(self, model)
        if model._meta.db_table == "management_igcheckoutinvoicegeneration":
            os._exit(KILL_EXIT_CODE)
        return result

    schema_editor_class.create_model = kill_after_generation
    MigrationExecutor(connection).migrate([TARGET])
    raise RuntimeError("kill phase reached migration completion")


def _columns(connection, table):
    with connection.cursor() as cursor:
        return {
            row.name
            for row in connection.introspection.get_table_description(cursor, table)
        }


def _race_winner(proposal_id, generation_id, barrier, outcomes):
    from django.db import close_old_connections, transaction
    from management.models import IgCheckoutInvoiceGeneration, IgCheckoutProposal

    close_old_connections()
    barrier.wait()
    with transaction.atomic():
        proposal = IgCheckoutProposal.objects.select_for_update().get(pk=proposal_id)
        generation = IgCheckoutInvoiceGeneration.objects.select_for_update().get(
            pk=generation_id,
            proposal_id=proposal.pk,
        )
        if proposal.winner_invoice_generation_id:
            outcomes.append((generation_id, "loser"))
        else:
            generation.winner_slot = 1
            generation.state = "winner_claimed"
            generation.save(update_fields=["winner_slot", "state", "updated_at"])
            proposal.winner_invoice_generation = generation
            proposal.save(update_fields=["winner_invoice_generation", "updated_at"])
            outcomes.append((generation_id, "winner"))
    close_old_connections()


def _orchestrate(args):
    connection, database = _setup(args)
    from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
    from django.db.migrations.exceptions import IrreversibleError
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
    from django.utils import timezone

    executor = MigrationExecutor(connection)
    if TARGET in MigrationRecorder(connection).applied_migrations():
        raise RuntimeError("0184 already applied; use a fresh disposable DB")
    executor.migrate(list(BEFORE))
    before_apps = MigrationExecutor(connection).loader.project_state(list(BEFORE)).apps
    Client = before_apps.get_model("management", "IgClient")
    Deal = before_apps.get_model("management", "IgDeal")
    Episode = before_apps.get_model("management", "IgCommercialEpisode")
    Proposal = before_apps.get_model("management", "IgCheckoutProposal")
    client = Client.objects.create(igsid="checkout-s2b-mariadb-proof")
    deal = Deal.objects.create(
        client=client,
        amount="900.00",
        requested_payment_amount="900.00",
    )
    episode = Episode.objects.create(
        client=client,
        deal=deal,
        sequence=1,
        open_slot=1,
        materialization_key="checkout-s2b-mariadb-proof:episode",
    )
    legacy_expiry = timezone.now() + timedelta(minutes=25)
    legacy = Proposal.objects.create(
        client=client,
        deal=deal,
        commercial_episode=episode,
        catalog_total="900.00",
        quoted_total="900.00",
        requested_payment_amount="900.00",
        items_digest="a" * 64,
        expires_at=legacy_expiry,
    )
    close_old_connections()
    child = subprocess.run(
        [
            sys.executable,
            os.path.abspath(__file__),
            "--confirm-disposable",
            "--phase",
            "kill",
        ],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
        check=False,
    )
    if child.returncode != KILL_EXIT_CODE:
        raise RuntimeError(
            f"kill phase returned {child.returncode}, expected {KILL_EXIT_CODE}: "
            f"{child.stderr[-2000:]}"
        )
    close_old_connections()
    from django.db import connection as resumed

    recorder = MigrationRecorder(resumed)
    partial_recorded = TARGET in recorder.applied_migrations()
    partial_tables = set(resumed.introspection.table_names())
    if partial_recorded:
        raise RuntimeError("partial 0184 was recorded")
    if "management_igcheckoutinvoicegeneration" not in partial_tables:
        raise RuntimeError("generation table missing at kill point")
    if "management_igcheckoutinvoicegenerationevent" in partial_tables:
        raise RuntimeError("kill point advanced beyond generation table")

    MigrationExecutor(resumed).migrate([TARGET])
    MigrationExecutor(resumed).migrate([TARGET])
    from management.models import (
        IgCheckoutInvoiceGeneration,
        IgCheckoutInvoiceGenerationEvent,
        IgCheckoutProposal,
    )

    legacy_row = IgCheckoutProposal.objects.get(pk=legacy.pk)
    legacy_unchanged = bool(
        not legacy_row.assisted_checkout_v2
        and legacy_row.payment_policy == "legacy"
        and legacy_row.current_invoice_generation_id is None
        and legacy_row.winner_invoice_generation_id is None
        and legacy_row.expires_at == legacy_expiry
    )
    if not legacy_unchanged:
        raise RuntimeError("legacy proposal TTL/state changed during 0184")

    tables = (
        "management_igcheckoutinvoicegeneration",
        "management_igcheckoutinvoicegenerationevent",
    )
    with resumed.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s, %s)",
            list(tables),
        )
        engines = {str(table): str(engine).upper() for table, engine in cursor.fetchall()}
        cursor.execute(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME IN (%s, %s)",
            ["ig_invgevt_no_update", "ig_invgevt_no_delete"],
        )
        triggers = sorted(str(row[0]) for row in cursor.fetchall())
    if set(engines) != set(tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected checkout S2b engines: {engines}")
    if triggers != ["ig_invgevt_no_delete", "ig_invgevt_no_update"]:
        raise RuntimeError(f"unexpected checkout S2b triggers: {triggers}")

    v2 = IgCheckoutProposal.objects.create(
        client_id=legacy_row.client_id,
        deal_id=legacy_row.deal_id,
        commercial_episode_id=legacy_row.commercial_episode_id,
        catalog_total="900.00",
        quoted_total="900.00",
        requested_payment_amount="900.00",
        items_digest="b" * 64,
        assisted_checkout_v2=True,
        payment_policy="full_only",
        expires_at=timezone.now() + timedelta(hours=12),
    )

    def generation(number, **overrides):
        values = {
            "proposal": v2,
            "generation": number,
            "series_key": "c" * 64,
            "proposal_revision": 1,
            "payment_amount": "900.00",
            "provider_call_token": hashlib.sha256(
                f"checkout-s2b:{number}".encode()
            ).hexdigest(),
            "expires_at": timezone.now() + timedelta(minutes=25),
        }
        values.update(overrides)
        return IgCheckoutInvoiceGeneration.objects.create(**values)

    first = generation(1, active_slot=1, provider_invoice_id="s2b-provider-one")
    active_slot_rejected = False
    try:
        with transaction.atomic():
            generation(2, active_slot=1)
    except IntegrityError:
        active_slot_rejected = True
    first.active_slot = None
    first.save(update_fields=["active_slot", "updated_at"])
    second = generation(2)
    provider_id_rejected = False
    try:
        with transaction.atomic():
            generation(3, provider_invoice_id="s2b-provider-one")
    except IntegrityError:
        provider_id_rejected = True
    invalid_checks_rejected = 0
    for number, overrides in enumerate(
        (
            {"generation": 0},
            {"active_slot": 2},
            {"winner_slot": 2},
            {"payment_amount": "0.00"},
        ),
        start=10,
    ):
        try:
            with transaction.atomic():
                generation(number, **overrides)
        except IntegrityError:
            invalid_checks_rejected += 1
    winner_slot_rejected = False
    first.winner_slot = 1
    first.state = "winner_claimed"
    first.save(update_fields=["winner_slot", "state", "updated_at"])
    try:
        with transaction.atomic():
            second.winner_slot = 1
            second.state = "winner_claimed"
            second.save(update_fields=["winner_slot", "state", "updated_at"])
    except IntegrityError:
        winner_slot_rejected = True
    first.winner_slot = None
    first.state = "planned"
    first.save(update_fields=["winner_slot", "state", "updated_at"])
    second.refresh_from_db()

    barrier = threading.Barrier(2)
    outcomes = []
    threads = [
        threading.Thread(
            target=_race_winner,
            args=(v2.pk, generation_id, barrier, outcomes),
        )
        for generation_id in (first.pk, second.pk)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("winner race threads did not finish")
    winner_race_ok = sorted(value for _pk, value in outcomes) == ["loser", "winner"]
    if not winner_race_ok:
        raise RuntimeError(f"winner race mismatch: {outcomes}")

    event = IgCheckoutInvoiceGenerationEvent.objects.create(
        event_key="checkout-s2b-mariadb-proof:event",
        generation=first,
        proposal=v2,
        kind="created",
    )
    event_update_rejected = False
    event_delete_rejected = False
    try:
        with resumed.cursor() as cursor:
            cursor.execute(
                "UPDATE management_igcheckoutinvoicegenerationevent "
                "SET payload=%s WHERE id=%s",
                [json.dumps({"changed": True}), event.pk],
            )
    except DatabaseError:
        event_update_rejected = True
    try:
        with resumed.cursor() as cursor:
            cursor.execute(
                "DELETE FROM management_igcheckoutinvoicegenerationevent WHERE id=%s",
                [event.pk],
            )
    except DatabaseError:
        event_delete_rejected = True

    try:
        MigrationExecutor(resumed).migrate(list(BEFORE))
    except IrreversibleError:
        reverse_refused = True
    else:
        reverse_refused = False
    reverse_schema_preserved = bool(
        "management_igcheckoutinvoicegeneration" in resumed.introspection.table_names()
        and TARGET in MigrationRecorder(resumed).applied_migrations()
    )
    proof = {
        "database": database,
        "kill_exit_code": child.returncode,
        "partial_migration_recorded": partial_recorded,
        "engines": engines,
        "triggers": triggers,
        "legacy_unchanged": legacy_unchanged,
        "active_slot_rejected": active_slot_rejected,
        "provider_id_rejected": provider_id_rejected,
        "winner_slot_rejected": winner_slot_rejected,
        "invalid_checks_rejected": invalid_checks_rejected,
        "winner_race_ok": winner_race_ok,
        "event_update_rejected": event_update_rejected,
        "event_delete_rejected": event_delete_rejected,
        "migration_recorded": TARGET in MigrationRecorder(resumed).applied_migrations(),
        "reverse_refused": reverse_refused,
        "reverse_schema_preserved": reverse_schema_preserved,
        "generation_columns": sorted(_columns(resumed, tables[0])),
        "event_columns": sorted(_columns(resumed, tables[1])),
    }
    if not all(
        proof[key]
        for key in (
            "legacy_unchanged", "active_slot_rejected", "provider_id_rejected",
            "winner_slot_rejected", "winner_race_ok", "event_update_rejected",
            "event_delete_rejected",
            "migration_recorded", "reverse_refused", "reverse_schema_preserved",
        )
    ):
        raise RuntimeError("checkout S2b proof failed: " + json.dumps(proof, sort_keys=True))
    if invalid_checks_rejected != 4:
        raise RuntimeError("checkout S2b CHECK constraints accepted malformed rows")
    print("IG_CHECKOUT_S2B_0184_PROOF=" + json.dumps(proof, sort_keys=True))


def main(argv=None):
    args = _arguments(argv)
    if args.phase == "kill":
        _kill_phase(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
