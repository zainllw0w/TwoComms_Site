"""Fail-closed administrative and runtime state for call auto-analysis."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, transaction

from management.models import InstagramBotSettings


MARKER_BYTES = b"call-auto-analysis-enabled-v1\n"
_SAFE_REASON = "Стан автоаналізу не вдалося узгодити."


class _MarkerRemovalFailed(Exception):
    """Abort the database transition when the runtime gate remains enabled."""


@dataclass(frozen=True, slots=True)
class CallAutoAnalysisState:
    configured_enabled: bool
    marker_enabled: bool
    effective_enabled: bool
    degraded: bool
    code: str
    reason: str = ""


def marker_path() -> Path:
    return Path(settings.BASE_DIR) / "tmp" / "call_auto_analysis.enabled"


def _marker_state() -> tuple[bool, str]:
    path = marker_path()
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError:
        return False, "marker_missing"
    except OSError:
        return False, "marker_unreadable"

    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        return False, "marker_not_regular"
    if stat.S_IMODE(path_stat.st_mode) != 0o600:
        return False, "marker_insecure_permissions"

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened_stat = os.fstat(descriptor)
            if not stat.S_ISREG(opened_stat.st_mode):
                return False, "marker_not_regular"
            if stat.S_IMODE(opened_stat.st_mode) != 0o600:
                return False, "marker_insecure_permissions"
            content = os.read(descriptor, len(MARKER_BYTES) + 1)
        finally:
            os.close(descriptor)
    except OSError:
        return False, "marker_unreadable"

    if content != MARKER_BYTES:
        return False, "marker_invalid"
    return True, "enabled"


def read_call_auto_analysis_state() -> CallAutoAnalysisState:
    """Read configured and projected state without creating the singleton."""
    try:
        configured = bool(
            InstagramBotSettings.objects.filter(pk=1).values_list(
                "call_auto_analysis_enabled", flat=True
            ).first()
        )
    except DatabaseError:
        return CallAutoAnalysisState(
            configured_enabled=False,
            marker_enabled=False,
            effective_enabled=False,
            degraded=True,
            code="database_unavailable",
            reason=_SAFE_REASON,
        )

    marker_enabled, marker_code = _marker_state()
    if configured and marker_enabled:
        return CallAutoAnalysisState(True, True, True, False, "enabled")
    if not configured and marker_code == "marker_missing":
        return CallAutoAnalysisState(False, False, False, False, "disabled")
    if not configured and marker_enabled:
        return CallAutoAnalysisState(
            False, True, False, True, "marker_without_configuration", _SAFE_REASON
        )
    return CallAutoAnalysisState(
        configured, False, False, True, marker_code, _SAFE_REASON
    )


def is_call_auto_analysis_enabled() -> bool:
    return read_call_auto_analysis_state().effective_enabled


def publish_call_auto_analysis_marker() -> None:
    path = marker_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        written = 0
        while written < len(MARKER_BYTES):
            written += os.write(descriptor, MARKER_BYTES[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def remove_call_auto_analysis_marker() -> None:
    try:
        marker_path().unlink()
    except FileNotFoundError:
        pass


def _write_configured(enabled: bool) -> None:
    with transaction.atomic():
        current = (
            InstagramBotSettings.objects.select_for_update().filter(pk=1).first()
        )
        if current is None:
            InstagramBotSettings.objects.create(
                pk=1, call_auto_analysis_enabled=enabled
            )
            return
        current.call_auto_analysis_enabled = enabled
        current.save(update_fields=["call_auto_analysis_enabled", "updated_at"])


def _transition_error(code: str, state: CallAutoAnalysisState | None = None):
    current = state or read_call_auto_analysis_state()
    return replace(current, degraded=True, code=code, reason=_SAFE_REASON)


def set_call_auto_analysis_enabled(enabled: bool) -> CallAutoAnalysisState:
    """Persist the staff choice and project it to the scheduler marker."""
    if type(enabled) is not bool:
        raise TypeError("enabled must be a boolean")

    if not enabled:
        marker_remove_failed = False
        try:
            remove_call_auto_analysis_marker()
        except OSError:
            marker_remove_failed = True
        try:
            with transaction.atomic():
                current = (
                    InstagramBotSettings.objects.select_for_update()
                    .filter(pk=1)
                    .first()
                )
                if current is None:
                    InstagramBotSettings.objects.create(
                        pk=1, call_auto_analysis_enabled=False
                    )
                else:
                    current.call_auto_analysis_enabled = False
                    current.save(
                        update_fields=["call_auto_analysis_enabled", "updated_at"]
                    )
                try:
                    remove_call_auto_analysis_marker()
                except OSError as exc:
                    raise _MarkerRemovalFailed from exc
        except _MarkerRemovalFailed:
            return _transition_error("marker_remove_failed")
        except DatabaseError:
            state = read_call_auto_analysis_state()
            if not marker_remove_failed:
                state = replace(state, marker_enabled=False, effective_enabled=False)
            return _transition_error("database_write_failed", state)
        if marker_remove_failed:
            state = read_call_auto_analysis_state()
            state = replace(
                state, configured_enabled=False, effective_enabled=False
            )
            return _transition_error("marker_remove_failed", state)
        return read_call_auto_analysis_state()

    callback_state: dict[str, CallAutoAnalysisState] = {}

    def publish_projection() -> None:
        try:
            with transaction.atomic():
                current = (
                    InstagramBotSettings.objects.select_for_update()
                    .filter(pk=1)
                    .first()
                )
                if current is None or not current.call_auto_analysis_enabled:
                    try:
                        remove_call_auto_analysis_marker()
                    except OSError:
                        pass
                    callback_state["state"] = read_call_auto_analysis_state()
                    return
                try:
                    publish_call_auto_analysis_marker()
                except OSError:
                    try:
                        remove_call_auto_analysis_marker()
                    except OSError:
                        pass
                    current.call_auto_analysis_enabled = False
                    current.save(
                        update_fields=["call_auto_analysis_enabled", "updated_at"]
                    )
                    state = CallAutoAnalysisState(
                        configured_enabled=False,
                        marker_enabled=False,
                        effective_enabled=False,
                        degraded=True,
                        code="marker_publish_failed",
                        reason=_SAFE_REASON,
                    )
                    callback_state["state"] = state
                    return
        except DatabaseError:
            try:
                remove_call_auto_analysis_marker()
            except OSError:
                pass
            callback_state["state"] = _transition_error(
                "database_write_failed"
            )
            return
        callback_state["state"] = read_call_auto_analysis_state()

    try:
        with transaction.atomic():
            current = (
                InstagramBotSettings.objects.select_for_update()
                .filter(pk=1)
                .first()
            )
            if current is None:
                InstagramBotSettings.objects.create(
                    pk=1, call_auto_analysis_enabled=True
                )
            else:
                current.call_auto_analysis_enabled = True
                current.save(
                    update_fields=["call_auto_analysis_enabled", "updated_at"]
                )
            transaction.on_commit(publish_projection)
    except DatabaseError:
        return _transition_error("database_write_failed")

    return callback_state.get("state", read_call_auto_analysis_state())
