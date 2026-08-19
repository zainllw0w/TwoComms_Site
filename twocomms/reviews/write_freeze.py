"""Fail-closed temporary write freeze for the ReviewVote engine canary."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from django.conf import settings


MARKER_BYTES = b"review-write-freeze-v1\n"


def review_write_freeze_marker_path() -> Path:
    configured = getattr(settings, "REVIEW_WRITE_FREEZE_MARKER", None)
    if configured is not None:
        return Path(configured)
    return Path(settings.BASE_DIR) / "tmp" / "review_writes.frozen"


def review_write_freeze_state() -> tuple[bool, bool, str]:
    """Return ``(writes_blocked, marker_verified, reason)``.

    A missing marker is the normal writable state. Once anything exists at the
    marker path, malformed or unreadable state blocks writes but cannot
    authorize the migration.
    """

    path = review_write_freeze_marker_path()
    if not path.is_absolute():
        return True, False, "marker_path_not_absolute"
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError:
        return False, False, "marker_missing"
    except OSError:
        return True, False, "marker_unreadable"

    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        return True, False, "marker_not_regular"
    if stat.S_IMODE(path_stat.st_mode) != 0o600:
        return True, False, "marker_insecure_permissions"
    if path_stat.st_uid != os.geteuid():
        return True, False, "marker_wrong_owner"

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened_stat = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened_stat.st_mode)
                or stat.S_IMODE(opened_stat.st_mode) != 0o600
                or opened_stat.st_uid != os.geteuid()
                or (opened_stat.st_dev, opened_stat.st_ino)
                != (path_stat.st_dev, path_stat.st_ino)
            ):
                return True, False, "marker_changed"
            content = os.read(descriptor, len(MARKER_BYTES) + 1)
        finally:
            os.close(descriptor)
    except OSError:
        return True, False, "marker_unreadable"

    if content != MARKER_BYTES:
        return True, False, "marker_invalid"
    return True, True, "frozen"


def review_writes_frozen() -> bool:
    return review_write_freeze_state()[0]


def review_write_freeze_verified() -> bool:
    return review_write_freeze_state()[1]
