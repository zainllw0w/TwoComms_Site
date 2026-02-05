"""
Upload validation helpers.

Focused on image uploads that can come from public/admin forms.
"""

from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

DEFAULT_MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8MB
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "avif"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/avif",
}


def _normalized_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    return ext


def _safe_filename(prefix: str, extension: str) -> str:
    safe_prefix = "".join(ch if ch.isalnum() else "-" for ch in (prefix or "upload")).strip("-") or "upload"
    return f"{safe_prefix}-{uuid4().hex}.{extension}"


def validate_image_file(uploaded_file, field_name: str = "upload", max_size: int = DEFAULT_MAX_IMAGE_SIZE):
    """
    Validate and normalize an uploaded image.
    """
    if not uploaded_file:
        return uploaded_file

    if uploaded_file.size > max_size:
        raise ValidationError(f"Файл завеликий. Максимальний розмір: {max_size // (1024 * 1024)}MB.")

    extension = _normalized_extension(uploaded_file.name)
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Неприпустиме розширення файлу: .{extension or 'unknown'}. "
            f"Дозволено: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValidationError(f"Неприпустимий MIME-тип: {content_type}.")

    # Magic/content validation via Pillow.
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Файл не є коректним зображенням.")
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    uploaded_file.name = _safe_filename(field_name, extension)
    return uploaded_file


def validate_image_list(files, field_name: str = "upload", max_size: int = DEFAULT_MAX_IMAGE_SIZE):
    if not files:
        return files
    return [validate_image_file(item, field_name=field_name, max_size=max_size) for item in files if item]
