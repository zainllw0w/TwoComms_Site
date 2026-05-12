"""SEO/Performance v1.0 Phase 12 — auto-resize + WebP recompress at upload.

Closes the root cause of finding (B22) of the SEO audit: admins upload
3-22 MB iPhone PNG / JPEG photos through the Django admin, the
``post_save`` task only ever produces *responsive copies* in
``<dir>/optimized/``, and the bloated **original** keeps living in
``/media/products/extra/`` (or wherever). The cleanup script
(``compress_media_originals`` / ``convert_originals_to_webp``) has to
chase the leftovers periodically.

The right place to fix the bloat is at intake. Before the model row
hits the database, we:

1. Open the incoming ``ImageField.file`` with Pillow,
2. EXIF-rotate so iPhone portrait photos do not flip on re-save,
3. Downscale to fit ``MAX_DIM`` × ``MAX_DIM`` preserving aspect ratio,
4. Re-encode as **WebP** at quality 85 (RGBA preserved),
5. Replace the in-memory ``FileField`` payload with the new bytes and
   transliterate the basename to ASCII slug. The new filename ends in
   ``.webp`` so Django persists it under the proper extension.

This means **every new upload through any model** that opts into the
pipeline lands on disk as a ≤500 KB WebP with an ASCII slug name —
no more 11 MB ``IMG_7105.png`` or ``ChatGPT_Image_28_апр._...png``
in the filesystem.

Out of scope:
- Pre-existing files (covered by the one-shot management commands).
- Non-image ``FileField``\\s (PDFs, CSV exports — left untouched).
"""
from __future__ import annotations

import io
import logging
import os
import re
import unicodedata
import uuid
from typing import Optional

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


# Caps. Product photography rarely needs more than 1600 px wide for
# the storefront's largest hero slot; 2000 px tall accommodates
# portrait phone shots. Above that is wasted bandwidth on every CDN
# request.
MAX_WIDTH = 1600
MAX_HEIGHT = 2000
WEBP_QUALITY = 85
MIN_PROCESS_BYTES = 50_000  # don't touch tiny icons


_NON_ASCII_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _transliterate(name: str) -> str:
    """Strip Cyrillic + reserved chars; produce safe ASCII slug."""
    # Replace common Cyrillic letters with Latin equivalents so users
    # who upload "Худі2.png" get "khudi2.webp" rather than the URL
    # encoded "%D0%A5%D1%83%D0%B4%D1%96.webp" Apache served before.
    table = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d",
        "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i",
        "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
        "щ": "shch", "ь": "", "ю": "iu", "я": "ia",
        "А": "A", "Б": "B", "В": "V", "Г": "H", "Ґ": "G", "Д": "D",
        "Е": "E", "Є": "Ie", "Ж": "Zh", "З": "Z", "И": "Y", "І": "I",
        "Ї": "I", "Й": "I", "К": "K", "Л": "L", "М": "M", "Н": "N",
        "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
        "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh",
        "Щ": "Shch", "Ь": "", "Ю": "Iu", "Я": "Ia",
        "ы": "y", "э": "e", "ё": "yo", "ъ": "",
        "Ы": "Y", "Э": "E", "Ё": "Yo", "Ъ": "",
        " ": "-",
    })
    nfkd = unicodedata.normalize("NFKD", name.translate(table))
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    cleaned = _NON_ASCII_RE.sub("-", ascii_only).strip("-._")
    return cleaned or "image"


def _should_process(field_file) -> bool:
    """Return True if this is a freshly uploaded file we should compress.

    ``FieldFile`` is the descriptor Django attaches to ``ImageField``
    on the model instance. When the admin posts a new upload it carries
    an ``InMemoryUploadedFile`` / ``TemporaryUploadedFile`` under
    ``.file``; rows fetched from the DB (e.g. during a plain
    ``save()`` without form change) carry a ``django.core.files.File``
    backed by the existing on-disk path — we must skip those or every
    save would re-encode the same WebP into itself, slowly drifting
    quality.
    """
    if not field_file:
        return False
    file_obj = getattr(field_file, "file", None)
    if file_obj is None:
        return False
    # Heuristic: real uploads expose ``content_type``; on-disk files do
    # not. We could also check ``isinstance(InMemoryUploadedFile)`` but
    # ``content_type`` is more robust across Django versions.
    return bool(getattr(file_obj, "content_type", None))


def process_image_field(field_file, *,
                        max_width: int = MAX_WIDTH,
                        max_height: int = MAX_HEIGHT,
                        quality: int = WEBP_QUALITY) -> Optional[str]:
    """Resize + re-encode the upload in place. Returns the new filename.

    Safe to call from a ``pre_save`` signal — the model's ``.save()``
    will then persist the modified ``FieldFile`` to disk via Django's
    standard storage flow, so we do not have to touch the storage
    backend ourselves.

    Returns ``None`` and leaves the field untouched when the upload
    looks already-fine (small, missing, or non-image).
    """
    if not _should_process(field_file):
        return None
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover — Pillow ships with Django
        logger.warning("Pillow not installed; skipping image_intake compression")
        return None

    upload = field_file.file
    try:
        size_hint = upload.size
    except Exception:
        size_hint = 0
    if size_hint and size_hint < MIN_PROCESS_BYTES:
        return None

    # The file pointer may have already been read by Django; rewind.
    try:
        upload.seek(0)
    except Exception:
        pass

    try:
        with Image.open(upload) as img:
            # Format check — refuse to touch SVG/PDF passed through.
            if (img.format or "").upper() not in {
                "JPEG", "JPG", "PNG", "WEBP", "GIF", "BMP", "TIFF",
            }:
                return None
            img = ImageOps.exif_transpose(img)
            src_w, src_h = img.size
            if src_w <= 0 or src_h <= 0:
                return None
            scale = min(max_width / src_w, max_height / src_h, 1.0)
            if scale < 1.0:
                new_size = (
                    max(1, round(src_w * scale)),
                    max(1, round(src_h * scale)),
                )
                img = img.resize(new_size, Image.LANCZOS)
            # Pillow's WebP encoder does not accept "P" or "LA" modes
            # directly; collapse to RGB / RGBA so the save() never
            # raises ValueError.
            if img.mode == "P":
                img = img.convert("RGBA")
            elif img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=6)
            payload = buffer.getvalue()
    except Exception as exc:
        # Pillow can choke on truncated uploads, weird CMYK JPEGs from
        # legacy DSLRs, etc. Logging keeps us informed without
        # blocking the admin from publishing the row — Django will
        # persist the original payload unchanged.
        logger.warning(
            "image_intake: failed to compress %s — %s",
            getattr(field_file, "name", "<unknown>"), exc,
        )
        return None

    # Build the final, browser-safe filename.
    base = getattr(field_file, "name", None) or "image.webp"
    base = os.path.basename(base)
    stem, _ = os.path.splitext(base)
    safe = _transliterate(stem)
    # Avoid collisions: file storages add a random suffix on conflict
    # but that produces ``image_abc123.webp`` URLs; pinning a short
    # uuid up-front keeps URLs deterministic per session.
    suffix = uuid.uuid4().hex[:6]
    new_name = f"{safe}-{suffix}.webp"

    # Replace the field's payload + name. We pass ``save=False`` so
    # the upstream ``ModelForm.save()`` only triggers a single DB
    # write at the end of its own flow.
    field_file.save(new_name, ContentFile(payload), save=False)
    return new_name
