"""Hardened ephemeral storage and two-phase deletion for IG customer media."""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone


ACTIVE = "active"
DELETE_PENDING = "delete_pending"
DELETING = "deleting"
DELETE_FAILED = "delete_failed"
DELETED = "deleted"
DELETE_CLAIM_SECONDS = 300
DELETE_RETRY_SECONDS = 60
USE_LEASE_MAX_SECONDS = 300
_debug_root: Path | None = None


def _require_secure_fd_primitives() -> None:
    """Fail readiness when the host cannot harden paths without following links."""
    missing = []
    for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"):
        if not getattr(os, name, 0):
            missing.append(name)
    for name in ("fstat", "fchmod", "geteuid"):
        if not callable(getattr(os, name, None)):
            missing.append(f"os.{name}")
    supports_dir_fd = getattr(os, "supports_dir_fd", set())
    for function in (os.open, os.mkdir, os.unlink):
        if function not in supports_dir_fd:
            missing.append(f"{function.__name__}(dir_fd=...)")
    if missing:
        raise ImproperlyConfigured(
            "IG private media requires secure fd primitives: "
            + ", ".join(missing)
        )


def _verify_and_harden_fd(
    descriptor: int,
    *,
    directory: bool,
    label: str,
) -> os.stat_result:
    """Validate type/ownership and apply the canonical private mode by fd."""
    info = os.fstat(descriptor)
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode):
        raise PermissionError(f"unsafe private media {label} type")
    if info.st_uid != os.geteuid():
        raise PermissionError(f"unsafe private media {label} ownership")
    expected_mode = 0o700 if directory else 0o600
    os.fchmod(descriptor, expected_mode)
    hardened = os.fstat(descriptor)
    if stat.S_IMODE(hardened.st_mode) != expected_mode:
        raise PermissionError(f"unsafe private media {label} mode")
    return hardened


def _open_owned_directory(path, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path, flags, dir_fd=dir_fd)
    try:
        _verify_and_harden_fd(descriptor, directory=True, label="directory")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_canonical_root(path: Path) -> int:
    """Open an absolute root one component at a time without following symlinks."""
    if not path.is_absolute():
        raise ImproperlyConfigured("IG_PRIVATE_MEDIA_ROOT must be absolute")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current_fd = os.open(os.sep, flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            try:
                if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                    raise PermissionError("unsafe private media root path type")
            except Exception:
                os.close(next_fd)
                raise
            os.close(current_fd)
            current_fd = next_fd
        _verify_and_harden_fd(current_fd, directory=True, label="root")
    except Exception:
        os.close(current_fd)
        raise
    return current_fd


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _configured_root() -> Path:
    _require_secure_fd_primitives()
    raw = str(getattr(settings, "IG_PRIVATE_MEDIA_ROOT", "") or "").strip()
    if not raw:
        if not bool(getattr(settings, "DEBUG", False)):
            raise ImproperlyConfigured(
                "IG_PRIVATE_MEDIA_ROOT is required when DEBUG=False"
            )
        global _debug_root
        if _debug_root is None:
            _debug_root = Path(
                tempfile.mkdtemp(prefix=f"twocomms-private-media-{os.getpid()}-")
            )
            descriptor = _open_canonical_root(_debug_root.resolve(strict=True))
            os.close(descriptor)
        return _debug_root
    configured = Path(raw).expanduser()
    if not configured.is_absolute():
        raise ImproperlyConfigured("IG_PRIVATE_MEDIA_ROOT must be absolute")
    return configured


def validate_private_root(*, require_exists: bool = True) -> Path:
    configured = _configured_root()
    # Reject a symlink at any existing path component before canonicalizing.
    cursor = configured
    while True:
        if cursor.exists() and cursor.is_symlink():
            raise ImproperlyConfigured("IG private media path cannot contain symlinks")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if require_exists and not configured.exists():
        raise ImproperlyConfigured("IG_PRIVATE_MEDIA_ROOT must be pre-created")
    canonical = configured.resolve(strict=require_exists)
    if require_exists and not canonical.is_dir():
        raise ImproperlyConfigured("IG_PRIVATE_MEDIA_ROOT must be a directory")

    forbidden = []
    media_root = str(getattr(settings, "MEDIA_ROOT", "") or "").strip()
    if media_root:
        forbidden.append(Path(media_root).expanduser().resolve())
    base_dir = Path(settings.BASE_DIR).resolve()
    forbidden.extend((base_dir, base_dir.parent))
    if any(_inside(canonical, root) for root in forbidden):
        raise ImproperlyConfigured(
            "IG_PRIVATE_MEDIA_ROOT must be outside MEDIA_ROOT and the checkout"
        )
    if require_exists:
        info = canonical.stat()
        if info.st_uid != os.geteuid():
            raise ImproperlyConfigured("IG private media root must be owned by the worker euid")
        if stat.S_IMODE(info.st_mode) != 0o700:
            raise ImproperlyConfigured("IG private media root mode must be 0700")
        descriptor = _open_canonical_root(canonical)
        os.close(descriptor)
    return canonical


class HardenedPrivateMediaStorage(FileSystemStorage):
    def __init__(self):
        root = validate_private_root(require_exists=True)
        super().__init__(
            location=str(root),
            base_url=None,
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )
        self._canonical_root = root

    def url(self, name):
        raise ValueError("private Instagram media never has a public URL")

    def _open(self, name, mode="rb"):
        from django.core.files import File

        if mode not in {"rb", "r"}:
            raise ValueError("private media storage is read-only through open()")
        parent_fd, leaf = self._open_parent(name, create=False)
        try:
            descriptor = os.open(
                leaf,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | getattr(os, "O_BINARY", 0),
                dir_fd=parent_fd,
            )
        finally:
            os.close(parent_fd)
        stream = None
        try:
            _verify_and_harden_fd(descriptor, directory=False, label="file")
            stream = os.fdopen(descriptor, mode)
            return File(stream, name)
        except Exception:
            if stream is not None:
                stream.close()
            else:
                os.close(descriptor)
            raise

    @staticmethod
    def _name_parts(name: str) -> tuple[str, ...]:
        normalized = str(name).replace("\\", "/")
        raw_parts = normalized.split("/")
        candidate = PurePosixPath(normalized)
        if (
            not normalized
            or candidate.is_absolute()
            or any(part in {"", ".", ".."} for part in raw_parts)
            or not candidate.name
        ):
            raise SuspiciousFileOperation("unsafe private media storage name")
        return candidate.parts

    def _open_parent(self, name: str, *, create: bool) -> tuple[int, str]:
        parts = self._name_parts(name)
        current_fd = _open_canonical_root(self._canonical_root)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                next_fd = _open_owned_directory(part, dir_fd=current_fd)
                os.close(current_fd)
                current_fd = next_fd
        except Exception:
            os.close(current_fd)
            raise
        return current_fd, parts[-1]

    def _save(self, name, content):
        from django.core.files import locks

        while True:
            parent_fd, leaf = self._open_parent(name, create=True)
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | os.O_NOFOLLOW
            )
            try:
                descriptor = os.open(leaf, flags, 0o600, dir_fd=parent_fd)
            except FileExistsError:
                os.close(parent_fd)
                name = self.get_available_name(name)
                continue
            except Exception:
                os.close(parent_fd)
                raise
            stream = None
            locked = False
            succeeded = False
            try:
                _verify_and_harden_fd(descriptor, directory=False, label="file")
                locks.lock(descriptor, locks.LOCK_EX)
                locked = True
                for chunk in content.chunks():
                    if stream is None:
                        stream = os.fdopen(
                            descriptor,
                            "wb" if isinstance(chunk, bytes) else "wt",
                        )
                    stream.write(chunk)
                if stream is not None:
                    stream.flush()
                _verify_and_harden_fd(descriptor, directory=False, label="file")
                succeeded = True
            finally:
                cleanup_failed = False
                try:
                    try:
                        if locked:
                            locks.unlock(descriptor)
                    except Exception:
                        cleanup_failed = True
                        raise
                finally:
                    try:
                        try:
                            if stream is not None:
                                stream.close()
                            else:
                                os.close(descriptor)
                        except Exception:
                            cleanup_failed = True
                            raise
                    finally:
                        try:
                            if not succeeded or cleanup_failed:
                                try:
                                    os.unlink(leaf, dir_fd=parent_fd)
                                except FileNotFoundError:
                                    pass
                        finally:
                            os.close(parent_fd)
            return str(PurePosixPath(*self._name_parts(name)))


# Imported lazily above to keep the module-level validation side-effect free.
from django.core.exceptions import SuspiciousFileOperation  # noqa: E402


def private_media_storage() -> HardenedPrivateMediaStorage:
    return HardenedPrivateMediaStorage()


@dataclass(frozen=True)
class DeleteClaim:
    message_id: int
    token: str
    storage_names: tuple[str, ...]


def acquire_blob_use(message_id: int, *, seconds: int = 120) -> str:
    from management.models import InstagramBotMessage

    now = timezone.now()
    seconds = max(10, min(int(seconds or 0), USE_LEASE_MAX_SECONDS))
    with transaction.atomic():
        row = InstagramBotMessage.objects.select_for_update().filter(pk=message_id).first()
        if row is None or row.private_media_state in {
            DELETE_PENDING, DELETING, DELETED,
        }:
            return ""
        if row.private_media_use_until and row.private_media_use_until > now:
            return ""
        token = secrets.token_hex(16)
        row.private_media_use_token = token
        row.private_media_use_until = now + timedelta(seconds=seconds)
        row.save(update_fields=[
            "private_media_use_token", "private_media_use_until",
        ])
        return token


def release_blob_use(message_id: int, token: str) -> None:
    if not message_id or not token:
        return
    from management.models import InstagramBotMessage

    InstagramBotMessage.objects.filter(
        pk=message_id,
        private_media_use_token=token,
    ).update(private_media_use_token="", private_media_use_until=None)


@contextlib.contextmanager
def blob_use_lease(message_id: int, *, seconds: int = 120):
    token = acquire_blob_use(message_id, seconds=seconds)
    try:
        yield bool(token)
    finally:
        release_blob_use(message_id, token)


def request_deletion(message_ids, *, now=None, immediate: bool = False) -> int:
    from management.models import InstagramBotMessage

    now = now or timezone.now()
    requested = 0
    for message_id in dict.fromkeys(int(value) for value in message_ids if value):
        with transaction.atomic():
            row = InstagramBotMessage.objects.select_for_update().filter(pk=message_id).first()
            if row is None or row.private_media_state == DELETED:
                continue
            if row.private_media_state == DELETING:
                if immediate:
                    row.private_media_delete_after = now
                    row.save(update_fields=["private_media_delete_after"])
                requested += 1
                continue
            row.private_media_state = DELETE_PENDING
            if immediate or not row.private_media_delete_after:
                row.private_media_delete_after = now
            row.private_media_delete_token = ""
            row.private_media_delete_claimed_at = None
            row.save(update_fields=[
                "private_media_state", "private_media_delete_after",
                "private_media_delete_token", "private_media_delete_claimed_at",
            ])
            requested += 1
    return requested


def claim_deletion(message_id: int, *, now=None) -> DeleteClaim | None:
    from management.models import InstagramBotMessage

    now = now or timezone.now()
    stale_before = now - timedelta(seconds=DELETE_CLAIM_SECONDS)
    with transaction.atomic():
        row = InstagramBotMessage.objects.select_for_update().filter(pk=message_id).first()
        if row is None or row.private_media_state == DELETED:
            return None
        if row.private_media_use_until and row.private_media_use_until > now:
            return None
        due = row.private_media_delete_after and row.private_media_delete_after <= now
        reclaim = (
            row.private_media_state == DELETING
            and row.private_media_delete_claimed_at
            and row.private_media_delete_claimed_at <= stale_before
        )
        if not reclaim and (
            row.private_media_state not in {DELETE_PENDING, DELETE_FAILED, ACTIVE, ""}
            or not due
        ):
            return None
        token = secrets.token_hex(16)
        row.private_media_state = DELETING
        row.private_media_delete_token = token
        row.private_media_delete_claimed_at = now
        row.save(update_fields=[
            "private_media_state", "private_media_delete_token",
            "private_media_delete_claimed_at",
        ])
        names = tuple(
            dict.fromkeys(
                str(item.get("storage_name") or "")
                for item in (row.attachment_media or [])
                if isinstance(item, dict)
                and item.get("private_storage")
                and item.get("storage_name")
            )
        )
        return DeleteClaim(row.pk, token, names)


def _finalize(claim: DeleteClaim, *, error: str = "", now=None) -> bool:
    from management.models import InstagramBotMessage

    now = now or timezone.now()
    with transaction.atomic():
        row = InstagramBotMessage.objects.select_for_update().filter(
            pk=claim.message_id,
            private_media_state=DELETING,
            private_media_delete_token=claim.token,
        ).first()
        if row is None:
            return False
        if error:
            row.private_media_state = DELETE_FAILED
            row.private_media_delete_after = now + timedelta(seconds=DELETE_RETRY_SECONDS)
            row.private_media_delete_token = ""
            row.private_media_delete_claimed_at = None
            row.save(update_fields=[
                "private_media_state", "private_media_delete_after",
                "private_media_delete_token", "private_media_delete_claimed_at",
            ])
            return False
        media = [dict(item) for item in (row.attachment_media or [])]
        for item in media:
            if not isinstance(item, dict) or not item.get("private_storage"):
                continue
            item["status"] = "expired"
            for key in (
                "storage_name", "local_url", "private_storage", "delete_after"
            ):
                item.pop(key, None)
        row.attachment_media = media
        row.private_media_state = DELETED
        row.private_media_delete_after = None
        row.private_media_delete_token = ""
        row.private_media_delete_claimed_at = None
        row.private_media_use_token = ""
        row.private_media_use_until = None
        row.save(update_fields=[
            "attachment_media", "private_media_state", "private_media_delete_after",
            "private_media_delete_token", "private_media_delete_claimed_at",
            "private_media_use_token", "private_media_use_until",
        ])
        return True


def delete_claimed_blob(claim: DeleteClaim, *, now=None) -> bool:
    try:
        storage = private_media_storage()
        for name in claim.storage_names:
            if storage.exists(name):
                storage.delete(name)
    except Exception as exc:
        return _finalize(claim, error=type(exc).__name__, now=now)
    return _finalize(claim, now=now)


def purge_due(*, now=None, limit: int = 100) -> int:
    from management.models import InstagramBotMessage

    now = now or timezone.now()
    ids = list(
        InstagramBotMessage.objects.filter(
            private_media_delete_after__isnull=False,
            private_media_delete_after__lte=now,
        )
        .exclude(private_media_state=DELETED)
        .order_by("private_media_delete_after", "id")
        .values_list("id", flat=True)[: max(1, min(int(limit or 0), 500))]
    )
    deleted = 0
    for message_id in ids:
        claim = claim_deletion(message_id, now=now)
        if claim and delete_claimed_blob(claim, now=now):
            deleted += 1
    return deleted


def delete_immediately(message_ids, *, now=None) -> int:
    now = now or timezone.now()
    ids = list(dict.fromkeys(int(value) for value in message_ids if value))
    request_deletion(ids, now=now, immediate=True)
    deleted = 0
    for message_id in ids:
        claim = claim_deletion(message_id, now=now)
        if claim and delete_claimed_blob(claim, now=now):
            deleted += 1
    return deleted
