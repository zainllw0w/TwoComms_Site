"""Adopt the catalog schema after an explicit maintenance preflight."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from product_catalog.schema_adoption import (
    CURRENT_APP_LABEL,
    SchemaAdoption,
    SchemaAdoptionError,
    write_snapshot,
)


LOCK_NAME = "twocomms:product-catalog-schema-adoption"
WRITE_CONFIRMATION = "ADOPT_PRODUCT_CATALOG"
MAINTENANCE_CONFIRMATION = "STOP_TRAFFIC"
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def current_git_sha(cwd=None) -> str:
    """Return the exact commit deployed in the current checkout."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd or settings.BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CommandError("could not determine the deployed Git SHA") from exc
    return result.stdout.strip().lower()


@contextmanager
def _advisory_lock(connection):
    """Serialize production adopters; SQLite has no server advisory locks."""

    if connection.vendor != "mysql":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 30)", [LOCK_NAME])
        acquired = cursor.fetchone()[0]
    if acquired != 1:
        raise CommandError("could not acquire the schema-adoption advisory lock")
    try:
        yield
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [LOCK_NAME])
        except Exception as exc:  # pragma: no cover - only reached during DB failure
            raise CommandError("schema-adoption advisory lock could not be released") from exc


def _read_snapshot(path: Path) -> dict:
    if not path.is_file():
        raise CommandError(f"snapshot does not exist: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise CommandError("snapshot must be private (mode 0600 or stricter)")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"invalid schema-adoption snapshot: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("adoption"), dict):
        raise CommandError("snapshot is missing its adoption configuration")
    return payload


class Command(BaseCommand):
    help = "Safely adopt the existing catalog schema under the canonical application identity."

    def add_arguments(self, parser):
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("--check", action="store_true", help="Run a read-only preflight.")
        modes.add_argument("--apply", action="store_true", help="Apply the guarded adoption.")
        modes.add_argument(
            "--resume-snapshot",
            metavar="PATH",
            help="Resume an interrupted adoption from its original private snapshot.",
        )
        modes.add_argument("--rollback-snapshot", metavar="PATH", help="Rollback from a private snapshot.")
        parser.add_argument("--legacy-app-label")
        parser.add_argument("--legacy-table-prefix")
        parser.add_argument(
            "--legacy-last-migration",
            default="0011_refine_brigade_taxonomy",
            help="Exact last migration recorded by the legacy catalog app (defaults to 0011).",
        )
        parser.add_argument("--expected-database")
        parser.add_argument("--media-root")
        parser.add_argument("--snapshot-path")
        parser.add_argument("--expected-sha", default="")
        parser.add_argument("--confirm-app-label")
        parser.add_argument("--confirm-database")
        parser.add_argument("--confirm-write")
        parser.add_argument("--confirm-maintenance")

    def _validate_database(self, options):
        expected = options.get("expected_database")
        if not expected:
            raise CommandError("--expected-database is required")
        actual = str(settings.DATABASES["default"].get("NAME") or "")
        if actual != expected:
            raise CommandError(f"database mismatch: expected {expected!r}, connected to {actual!r}")

    def _validate_sha(self, options):
        expected = str(options.get("expected_sha") or "").strip().lower()
        required = bool(options.get("apply"))
        if not expected:
            if required:
                raise CommandError("--expected-sha is required for write operations")
            return ""
        if not _FULL_SHA_RE.fullmatch(expected):
            raise CommandError("--expected-sha must be a full 40-character commit SHA")
        actual = current_git_sha()
        if actual != expected:
            raise CommandError(f"deployed SHA mismatch: expected {expected}, found {actual}")
        return actual

    def _build_adopter(self, options, *, config=None):
        values = config or options
        legacy_label = values.get("legacy_app_label")
        legacy_prefix = values.get("legacy_table_prefix")
        if not legacy_label or not legacy_prefix:
            raise CommandError("--legacy-app-label and --legacy-table-prefix are required")
        legacy_last_migration = values.get("legacy_last_migration") or "0011_refine_brigade_taxonomy"
        media_root = values.get("media_root") or getattr(settings, "MEDIA_ROOT", None)
        try:
            return SchemaAdoption(
                legacy_app_label=legacy_label,
                legacy_table_prefix=legacy_prefix,
                media_root=media_root,
                adoption_last_migration=legacy_last_migration,
            )
        except SchemaAdoptionError as exc:
            raise CommandError(str(exc)) from exc

    def _write_snapshot(self, path: str | None, payload: dict, *, must_not_exist=False):
        if not path:
            raise CommandError("--snapshot-path is required for --apply")
        if must_not_exist and Path(path).exists():
            raise CommandError(f"snapshot already exists: {path}")
        try:
            write_snapshot(path, payload)
        except OSError as exc:
            raise CommandError(f"could not write adoption snapshot: {path}") from exc

    def _confirm_write(self, options, *, config=None):
        expected = config or options
        if options.get("confirm_write") != WRITE_CONFIRMATION:
            raise CommandError(f"--confirm-write must equal {WRITE_CONFIRMATION}")
        if options.get("confirm_maintenance") != MAINTENANCE_CONFIRMATION:
            raise CommandError(f"--confirm-maintenance must equal {MAINTENANCE_CONFIRMATION}")
        if options.get("confirm_app_label") != expected.get("legacy_app_label"):
            raise CommandError("--confirm-app-label must exactly match --legacy-app-label")
        if options.get("confirm_database") != expected.get("expected_database"):
            raise CommandError("--confirm-database must exactly match --expected-database")

    def handle(self, *args, **options):
        if options.get("rollback_snapshot"):
            return self._rollback(options)
        if options.get("resume_snapshot"):
            return self._resume(options)

        self._validate_database(options)
        self._validate_sha(options)
        adopter = self._build_adopter(options)
        try:
            with _advisory_lock(adopter.connection):
                preflight = adopter.preflight(last_migration=options["legacy_last_migration"])
                payload = {
                    "adoption": {
                        "legacy_app_label": options["legacy_app_label"],
                        "legacy_table_prefix": options["legacy_table_prefix"],
                        "legacy_last_migration": options["legacy_last_migration"],
                        "expected_database": options["expected_database"],
                        "media_root": str(adopter.media_root) if adopter.media_root else None,
                        "expected_sha": options.get("expected_sha", ""),
                    },
                    "phase": "preflight-complete",
                    "preflight": preflight,
                }
                if options["check"]:
                    self.stdout.write(json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True, default=str))
                    return

                self._confirm_write(options)
                if (
                    preflight.get("state") != "legacy"
                    or preflight.get("metadata_state") != "legacy"
                ):
                    raise CommandError(
                        "a new adoption requires the complete legacy state; "
                        "resume an interrupted run with --resume-snapshot"
                    )
                self._write_snapshot(
                    options.get("snapshot_path"), payload, must_not_exist=True
                )

                def checkpoint(progress):
                    payload["progress"] = progress
                    payload["phase"] = progress.get("phase", "in-progress")
                    self._write_snapshot(options.get("snapshot_path"), payload)

                try:
                    result = adopter.apply(
                        last_migration=options["legacy_last_migration"],
                        checkpoint=checkpoint,
                        initial_preflight=preflight,
                    )
                except Exception as exc:
                    payload["phase"] = "failed"
                    payload["error"] = str(exc)
                    self._write_snapshot(options.get("snapshot_path"), payload)
                    raise CommandError(str(exc)) from exc
                payload["phase"] = result.get("phase", "complete")
                payload["result"] = result
                self._write_snapshot(options.get("snapshot_path"), payload)
                self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        except SchemaAdoptionError as exc:
            raise CommandError(str(exc)) from exc

    def _resume(self, options):
        path = Path(options["resume_snapshot"])
        payload = _read_snapshot(path)
        phase = str(payload.get("phase") or "")
        if payload.get("rollback_progress") is not None or phase.startswith("rollback"):
            raise CommandError(
                "snapshot rollback has already started; continue with "
                "--rollback-snapshot"
            )
        if payload.get("phase") in {"complete", "rolled-back"}:
            raise CommandError(
                "snapshot is already complete; use --rollback-snapshot to reverse it"
            )
        config = payload["adoption"]
        expected = config.get("expected_database")
        if not expected:
            raise CommandError("snapshot has no expected database")
        actual = str(settings.DATABASES["default"].get("NAME") or "")
        if actual != expected:
            raise CommandError(
                f"database mismatch: expected {expected!r}, connected to {actual!r}"
            )
        self._validate_sha(
            {"apply": True, "expected_sha": config.get("expected_sha")}
        )
        self._confirm_write(options, config=config)
        adopter = self._build_adopter(options, config=config)
        preflight = payload.get("preflight")
        if not isinstance(preflight, dict):
            raise CommandError("snapshot is missing its original preflight")
        saved_progress = payload.get("progress")
        if saved_progress is not None and not isinstance(saved_progress, dict):
            raise CommandError("snapshot contains invalid adoption progress")

        def checkpoint(progress):
            payload["progress"] = progress
            payload["phase"] = progress.get("phase", "in-progress")
            self._write_snapshot(str(path), payload)

        try:
            with _advisory_lock(adopter.connection):
                result = adopter.apply(
                    last_migration=config["legacy_last_migration"],
                    checkpoint=checkpoint,
                    initial_preflight=preflight,
                    saved_progress=saved_progress,
                )
        except Exception as exc:
            payload["phase"] = "failed"
            payload["error"] = str(exc)
            self._write_snapshot(str(path), payload)
            raise CommandError(str(exc)) from exc
        payload.pop("error", None)
        payload["phase"] = result.get("phase", "complete")
        payload["result"] = result
        self._write_snapshot(str(path), payload)
        self.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        )

    def _rollback(self, options):
        path = Path(options["rollback_snapshot"])
        payload = _read_snapshot(path)
        config = payload["adoption"]
        expected = config.get("expected_database")
        if not expected:
            raise CommandError("snapshot has no expected database")
        actual = str(settings.DATABASES["default"].get("NAME") or "")
        if actual != expected:
            raise CommandError(f"database mismatch: expected {expected!r}, connected to {actual!r}")
        self._validate_sha({"apply": True, "expected_sha": config.get("expected_sha")})
        adopter = self._build_adopter(options, config=config)
        self._confirm_write(options, config=config)
        try:
            with _advisory_lock(adopter.connection):
                preflight = payload.get("preflight") or {}
                saved = payload.get("result") or payload.get("progress") or {}

                def checkpoint(progress):
                    payload["rollback_progress"] = progress
                    payload["phase"] = progress.get("phase", "rollback-in-progress")
                    self._write_snapshot(str(path), payload)

                result = adopter.rollback(
                    last_migration=config["legacy_last_migration"],
                    identifier_renames=preflight.get("identifier_renames"),
                    data_media_manifest_state=saved.get(
                        "data_media_manifest_state"
                    ),
                    data_changes=saved.get("data_changes"),
                    media_changes=saved.get("media_changes"),
                    migrations=preflight.get("legacy_migrations"),
                    content_types=preflight.get("legacy_content_types"),
                    permissions=preflight.get("legacy_permissions"),
                    checkpoint=checkpoint,
                    initial_preflight=preflight,
                    saved_progress=payload.get("rollback_progress"),
                )
        except Exception as exc:
            payload["phase"] = "rollback-failed"
            payload["error"] = str(exc)
            self._write_snapshot(str(path), payload)
            raise CommandError(str(exc)) from exc
        payload.pop("error", None)
        payload["phase"] = result.get("phase", "rolled-back")
        payload["rollback_result"] = result
        self._write_snapshot(str(path), payload)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
