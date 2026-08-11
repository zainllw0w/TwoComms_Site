"""Merge a partially dual-written catalog schema under maintenance."""

from __future__ import annotations

from contextlib import contextmanager
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.migrations.recorder import MigrationRecorder

from product_catalog.schema_merge import (
    SCHEMA_MERGE_LOCK_NAME,
    SchemaMerge,
    SchemaMergeError,
)


WRITE_CONFIRMATION = "MERGE_PRODUCT_CATALOG"
DROP_CONFIRMATION = "DROP_LEGACY_CATALOG_TABLES"
MAINTENANCE_CONFIRMATION = "STOP_TRAFFIC"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SNAPSHOT_PHASES = frozenset(
    {
        "preflight",
        "rows-merged",
        "metadata-remapped",
        "migration-metadata-removed",
        "legacy-tables-dropped",
        "failed",
    }
)


@contextmanager
def _advisory_lock(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 30)", [SCHEMA_MERGE_LOCK_NAME])
        acquired = cursor.fetchone()[0]
    if acquired != 1:
        raise CommandError("could not acquire the catalog schema merge lock")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [SCHEMA_MERGE_LOCK_NAME])


def _private_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise CommandError(f"{label} does not exist: {path}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise CommandError(f"{label} must be private (mode 0600 or stricter)")
    if path.stat().st_size <= 0:
        raise CommandError(f"{label} is empty: {path}")


def _verify_backup(
    path: Path,
    *,
    expected_database: str,
    max_age_seconds: int | None = 900,
) -> dict[str, object]:
    _private_file(path, label="backup")
    if path.stat().st_size < 10_240:
        raise CommandError(f"backup is suspiciously small: {path}")
    if not path.name.startswith(f"{expected_database}-"):
        raise CommandError("backup filename is not bound to the expected database")
    age = time.time() - path.stat().st_mtime
    if age < -60 or (max_age_seconds is not None and age > max_age_seconds):
        raise CommandError(
            f"backup must be created during this maintenance run (age {int(age)} seconds)"
        )
    try:
        with gzip.open(path, "rb") as stream:
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
            if not size:
                raise CommandError(f"backup gzip stream is empty: {path}")
    except OSError as exc:
        raise CommandError(f"backup is not a valid gzip stream: {path}") from exc
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part")
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_snapshot(path: Path) -> dict:
    _private_file(path, label="snapshot")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"invalid merge snapshot: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("preflight"), dict):
        raise CommandError("snapshot is missing the preflight manifest")
    return payload


def _validate_snapshot_identity(snapshot: dict, options: dict) -> None:
    phase = str(snapshot.get("phase") or "")
    if phase not in SNAPSHOT_PHASES:
        raise CommandError(f"unsupported merge snapshot phase: {phase!r}")
    legacy_prefix = str(options["legacy_table_prefix"])
    legacy_label = str(options.get("legacy_app_label") or legacy_prefix)
    expected = {
        "expected_database": str(options["expected_database"]),
        "expected_sha": str(options.get("expected_sha") or "").lower(),
        "legacy_table_prefix": legacy_prefix,
        "legacy_app_label": legacy_label,
    }
    for key, value in expected.items():
        if str(snapshot.get(key) or "").lower() != value.lower():
            raise CommandError(f"merge snapshot identity mismatch: {key}")

    preflight = snapshot.get("preflight") or {}
    if preflight.get("current_app_label") != "product_catalog":
        raise CommandError("merge snapshot has an unexpected current app label")
    if preflight.get("legacy_table_prefix") != legacy_prefix:
        raise CommandError("merge snapshot preflight has a different legacy prefix")
    model_tables = {
        model._meta.label: model._meta.db_table
        for model in apps.get_app_config("product_catalog").get_models()
    }
    pair_tables = set()
    pair_models = set()
    pair_legacy_tables = set()
    pairs = list(preflight.get("pairs") or ())
    for pair in pairs:
        model_label = str(pair.get("model_label") or "")
        current_table = str(pair.get("current_table") or "")
        legacy_table = str(pair.get("legacy_table") or "")
        if model_tables.get(model_label) != current_table:
            raise CommandError(f"merge snapshot model/table mismatch: {model_label}")
        current_prefix = "product_catalog_"
        if not current_table.startswith(current_prefix):
            raise CommandError(f"merge snapshot has an unsafe current table: {current_table}")
        expected_legacy = f"{legacy_prefix}_{current_table[len(current_prefix):]}"
        if legacy_table != expected_legacy:
            raise CommandError(f"merge snapshot has an unsafe legacy table: {legacy_table}")
        if model_label in pair_models or current_table in pair_tables or legacy_table in pair_legacy_tables:
            raise CommandError("merge snapshot contains duplicate table pairs")
        pair_models.add(model_label)
        pair_tables.add(current_table)
        pair_legacy_tables.add(legacy_table)
    order = list(preflight.get("order") or ())
    if (
        not pair_tables
        or len(order) != len(pairs)
        or len(set(order)) != len(order)
        or set(order) != pair_tables
    ):
        raise CommandError("merge snapshot table order does not match its manifest")

    effective_phase = phase
    if phase == "failed":
        effective_phase = str((snapshot.get("progress") or {}).get("phase") or "failed")
    late_phases = {
        "metadata-remapped",
        "migration-metadata-removed",
        "legacy-tables-dropped",
    }
    if effective_phase in late_phases:
        post_merge = snapshot.get("post_merge")
        if not isinstance(post_merge, dict):
            raise CommandError("late-phase merge snapshot is missing post_merge evidence")
        post_pairs = list(post_merge.get("pairs") or ())
        if {
            str(item.get("current_table") or "") for item in post_pairs
        } != pair_tables or set(post_merge.get("order") or ()) != pair_tables:
            raise CommandError("post_merge evidence does not match the saved table manifest")
        incomplete = [
            str(item.get("current_table") or "")
            for item in post_pairs
            if (item.get("comparison") or {}).get("missing_ids")
            or (item.get("comparison") or {}).get("update_ids")
            or (item.get("comparison") or {}).get("conflicts")
        ]
        if incomplete:
            raise CommandError(
                "post_merge evidence contains incomplete tables: " + ", ".join(incomplete)
            )
        if not isinstance(snapshot.get("metadata"), dict):
            raise CommandError("late-phase merge snapshot is missing metadata evidence")
    if effective_phase in {"migration-metadata-removed", "legacy-tables-dropped"}:
        if "migration_rows_deleted" not in snapshot:
            raise CommandError("late-phase merge snapshot is missing migration metadata evidence")


def _current_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=settings.BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CommandError("could not determine deployed Git SHA") from exc
    return result.stdout.strip().lower()


class Command(BaseCommand):
    help = "Merge paired catalog tables and remove the retired physical schema after verification."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--check", action="store_true", help="Read-only manifest and conflict check.")
        mode.add_argument("--apply", action="store_true", help="Merge rows and metadata.")
        parser.add_argument("--legacy-table-prefix", required=True)
        parser.add_argument("--legacy-app-label")
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--expected-sha", default="")
        parser.add_argument("--backup-path")
        parser.add_argument("--snapshot-path")
        parser.add_argument("--confirm-write")
        parser.add_argument("--confirm-drop")
        parser.add_argument("--confirm-maintenance")
        parser.add_argument("--drop-legacy", action="store_true")

    def _validate_environment(self, options):
        actual_database = str(settings.DATABASES["default"].get("NAME") or "")
        if actual_database != options["expected_database"]:
            raise CommandError(
                f"database mismatch: expected {options['expected_database']!r}, got {actual_database!r}"
            )
        expected_sha = str(options.get("expected_sha") or "").strip().lower()
        if options.get("apply") and not expected_sha:
            raise CommandError("--expected-sha is required for --apply")
        if expected_sha:
            if not FULL_SHA_RE.fullmatch(expected_sha):
                raise CommandError("--expected-sha must be a full 40-character commit SHA")
            actual_sha = _current_sha()
            if actual_sha != expected_sha:
                raise CommandError(f"deployed SHA mismatch: expected {expected_sha}, got {actual_sha}")

    def handle(self, *args, **options):
        self._validate_environment(options)
        snapshot_path = Path(options["snapshot_path"]) if options.get("snapshot_path") else None
        existing_snapshot = (
            _read_snapshot(snapshot_path)
            if options.get("apply") and snapshot_path and snapshot_path.exists()
            else None
        )
        if existing_snapshot is not None:
            _validate_snapshot_identity(existing_snapshot, options)
        resume_cleanup = bool(
            existing_snapshot
            and existing_snapshot.get("post_merge")
            and (
                existing_snapshot.get("phase") in {
                    "migration-metadata-removed",
                    "legacy-tables-dropped",
                }
                or existing_snapshot.get("progress", {}).get("phase") == "legacy-tables-dropped"
            )
        )
        saved_pairs = (
            existing_snapshot["preflight"]["pairs"]
            if resume_cleanup
            else None
        )
        try:
            merger = SchemaMerge(
                legacy_table_prefix=options["legacy_table_prefix"],
                legacy_app_label=options.get("legacy_app_label") or options["legacy_table_prefix"],
                saved_pairs=saved_pairs,
            )
            preflight = (
                existing_snapshot["preflight"]
                if resume_cleanup
                else merger.preflight()
            )
        except SchemaMergeError as exc:
            raise CommandError(str(exc)) from exc

        if options["check"]:
            self.stdout.write(json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True, default=str))
            return

        if options.get("confirm_write") != WRITE_CONFIRMATION:
            raise CommandError(f"--confirm-write must equal {WRITE_CONFIRMATION}")
        if options.get("confirm_maintenance") != MAINTENANCE_CONFIRMATION:
            raise CommandError(f"--confirm-maintenance must equal {MAINTENANCE_CONFIRMATION}")
        if not options.get("drop_legacy") or options.get("confirm_drop") != DROP_CONFIRMATION:
            raise CommandError(
                f"destructive cleanup requires --drop-legacy and --confirm-drop={DROP_CONFIRMATION}"
            )
        if not options.get("backup_path"):
            raise CommandError("--backup-path is required for --apply")
        backup_manifest = _verify_backup(
            Path(options["backup_path"]),
            expected_database=options["expected_database"],
            max_age_seconds=None if existing_snapshot is not None else 900,
        )
        if existing_snapshot is not None and existing_snapshot.get("backup") != backup_manifest:
            raise CommandError("backup file no longer matches the merge snapshot")
        if snapshot_path is None:
            raise CommandError("--snapshot-path is required for --apply")

        if existing_snapshot is not None:
            snapshot = existing_snapshot
            if snapshot.get("phase") == "complete":
                raise CommandError("merge snapshot is already complete")
            if snapshot.get("phase") == "failed" and not resume_cleanup:
                # MySQL DDL is not transactionally reversible.  Rebuild the
                # manifest and re-run only after the current physical state
                # proves which row/metadata phases actually survived.
                snapshot["phase"] = "preflight"
                snapshot["preflight"] = preflight
                snapshot.pop("progress", None)
            elif not resume_cleanup and snapshot.get("preflight", {}).get("order") != preflight.get("order"):
                raise CommandError("current schema order differs from saved merge snapshot")
        else:
            snapshot = {
                "phase": "preflight",
                "expected_database": options["expected_database"],
                "expected_sha": options.get("expected_sha") or "",
                "legacy_table_prefix": options["legacy_table_prefix"],
                "legacy_app_label": options.get("legacy_app_label") or options["legacy_table_prefix"],
                "backup_path": str(options["backup_path"]),
                "backup": backup_manifest,
                "preflight": preflight,
            }
            _write_snapshot(snapshot_path, snapshot)

        def checkpoint(progress):
            snapshot["progress"] = progress
            snapshot["phase"] = progress.get("phase", "in-progress")
            _write_snapshot(snapshot_path, snapshot)

        try:
            with _advisory_lock(merger.connection), transaction.atomic(using=merger.connection_alias):
                if snapshot.get("phase") in {"preflight", "rows-merged"}:
                    merge_result = merger.merge_rows(preflight, checkpoint=checkpoint)
                    snapshot["merge"] = merge_result
                    post_merge = merger.preflight()
                    incomplete = [
                        item["current_table"]
                        for item in post_merge["pairs"]
                        if item["comparison"]["missing_ids"]
                        or item["comparison"]["update_ids"]
                        or item["comparison"]["conflicts"]
                    ]
                    if incomplete:
                        raise SchemaMergeError(
                            "post-merge row invariants failed: " + ", ".join(incomplete)
                        )
                    snapshot["post_merge"] = post_merge
                    snapshot["phase"] = "rows-merged"
                    _write_snapshot(snapshot_path, snapshot)
                if snapshot.get("phase") in {"rows-merged", "metadata-remapped"}:
                    metadata_result = merger.remap_metadata()
                    snapshot["metadata"] = metadata_result
                    snapshot["phase"] = "metadata-remapped"
                    _write_snapshot(snapshot_path, snapshot)

                # Old recorder rows are metadata, not data.  Delete only after
                # current ContentTypes and permission references are durable.
                legacy_app_label = options.get("legacy_app_label") or options["legacy_table_prefix"]
                recorder = MigrationRecorder(merger.connection)
                deleted, _ = recorder.Migration.objects.using(merger.connection_alias).filter(
                    app=legacy_app_label
                ).delete()
                snapshot["migration_rows_deleted"] = deleted
                snapshot["phase"] = "migration-metadata-removed"
                _write_snapshot(snapshot_path, snapshot)

                if snapshot.get("phase") in {"migration-metadata-removed", "legacy-tables-dropped"}:
                    dropped = merger.drop_legacy_tables(preflight, checkpoint=checkpoint)
                    snapshot["legacy_tables_dropped"] = dropped
                    snapshot["verification"] = merger.verify_cleanup(snapshot["post_merge"])
                    snapshot["phase"] = "complete"
                    _write_snapshot(snapshot_path, snapshot)
        except Exception as exc:
            snapshot["phase"] = "failed"
            snapshot["error"] = str(exc)
            _write_snapshot(snapshot_path, snapshot)
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str))
