"""Hardened ephemeral storage and two-phase deletion for IG customer media."""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

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


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _configured_root() -> Path:
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
            os.chmod(_debug_root, 0o700)
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
        path = Path(self.path(name))
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            os.close(descriptor)
            raise PermissionError("unsafe private media file")
        return File(os.fdopen(descriptor, mode), name)

    def _harden_parent(self, name: str) -> None:
        destination = Path(self.path(name))
        parent = destination.parent
        resolved_parent = parent.resolve(strict=True)
        if not _inside(resolved_parent, self._canonical_root):
            raise SuspiciousFileOperation("private media path escaped its root")
        cursor = resolved_parent
        while cursor != self._canonical_root.parent:
            info = cursor.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid():
                raise PermissionError("unsafe private media directory ownership")
            os.chmod(cursor, 0o700, follow_symlinks=False)
            if cursor == self._canonical_root:
                break
            cursor = cursor.parent

    def _save(self, name, content):
        from django.core.files import locks

        full_path = self.path(name)
        parent = Path(full_path).parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._harden_parent(name)
        while True:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                descriptor = os.open(full_path, flags, 0o600)
            except FileExistsError:
                name = self.get_available_name(name)
                full_path = self.path(name)
                self._harden_parent(name)
                continue
            stream = None
            try:
                locks.lock(descriptor, locks.LOCK_EX)
                for chunk in content.chunks():
                    if stream is None:
                        stream = os.fdopen(
                            descriptor,
                            "wb" if isinstance(chunk, bytes) else "wt",
                        )
                    stream.write(chunk)
            finally:
                locks.unlock(descriptor)
                if stream is not None:
                    stream.close()
                else:
                    os.close(descriptor)
            saved = os.path.relpath(full_path, self.location).replace("\\", "/")
            break
        path = Path(self.path(saved))
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise PermissionError("private media destination is not a regular file")
        if info.st_uid != os.geteuid():
            raise PermissionError("private media file has the wrong owner")
        os.chmod(path, 0o600, follow_symlinks=False)
        return saved


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
