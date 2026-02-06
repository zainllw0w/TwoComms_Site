from __future__ import annotations

import math
import os
import re
import secrets
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from django.conf import settings
from django.utils import translation

try:
    from PIL import Image
except Exception:
    Image = None


ALLOWED_READY_EXTS = {"pdf", "png"}
ALLOWED_HELP_EXTS = {"pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff", "zip", "rar", "7z", "ai", "psd", "svg"}
MIME_BY_EXT = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
    "tif": {"image/tiff"},
    "tiff": {"image/tiff"},
    "svg": {"image/svg+xml", "text/xml", "application/xml"},
    "zip": {"application/zip", "application/x-zip-compressed", "multipart/x-zip"},
    "rar": {"application/x-rar-compressed", "application/vnd.rar"},
    "7z": {"application/x-7z-compressed"},
}
DEFAULT_MAX_FILE_MB = 50
DEFAULT_MAX_COPIES = 500
DEFAULT_MAX_METERS_REVIEW = Decimal("200")
DEFAULT_BASE_RATE = Decimal("350")
DEFAULT_TIERS = [
    {"min": Decimal("10"), "rate": Decimal("330")},
    {"min": Decimal("30"), "rate": Decimal("310")},
    {"min": Decimal("50"), "rate": Decimal("280")},
]
DEFAULT_FEATURE_FLAGS = {
    "enable_view_transitions": False,
    "enable_prerender_order": False,
    "enable_printhead_scan": True,
    "enable_compare": True,
    "enable_lens": True,
    "enable_preflight": False,
    "enable_underbase_preview": False,
    "enable_haptics": False,
    "enable_sound": False,
    "enable_dynamic_favicon": False,
    "tier_mode": "auto",
}


def normalize_phone(value: str) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D+", "", value)
    return digits


def get_file_extension(filename: str) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower().lstrip(".")


def _sniff_magic(uploaded_file) -> str:
    try:
        pos = uploaded_file.tell()
    except Exception:
        pos = None

    try:
        head = uploaded_file.read(32)
    finally:
        try:
            if pos is not None:
                uploaded_file.seek(pos)
            else:
                uploaded_file.seek(0)
        except Exception:
            pass

    if not head:
        return ""
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "webp"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith(b"Rar!\x1a\x07\x00") or head.startswith(b"Rar!\x1a\x07\x01\x00"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    return ""


def build_safe_upload_name(prefix: str, original_name: str) -> str:
    ext = get_file_extension(original_name)
    token = secrets.token_hex(16)
    safe_prefix = re.sub(r"[^a-z0-9_-]+", "-", (prefix or "file").lower()).strip("-") or "file"
    safe_ext = f".{ext}" if ext else ""
    return f"{safe_prefix}-{token}{safe_ext}"


def validate_uploaded_file(uploaded_file, *, allowed_exts: set[str], max_file_mb: int, strict_magic: bool = True):
    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    if ext not in allowed_exts:
        raise ValueError("unsupported_extension")

    max_bytes = int(max_file_mb) * 1024 * 1024
    if getattr(uploaded_file, "size", 0) and uploaded_file.size > max_bytes:
        raise ValueError("file_too_large")

    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    expected_mimes = MIME_BY_EXT.get(ext, set())
    if expected_mimes and content_type and content_type not in expected_mimes:
        raise ValueError("mime_mismatch")
    if content_type in {"text/x-php", "application/x-httpd-php", "application/javascript", "text/javascript"}:
        raise ValueError("forbidden_mime")

    if strict_magic:
        sniffed = _sniff_magic(uploaded_file)
        if ext == "jpeg":
            ext_for_magic = "jpg"
        elif ext == "tif":
            ext_for_magic = "tiff"
        else:
            ext_for_magic = ext

        # For vector/native design formats without stable signatures, skip strict magic check.
        magic_optional_exts = {"ai", "psd", "svg"}
        if ext_for_magic not in magic_optional_exts:
            if not sniffed:
                raise ValueError("unknown_magic")
            if ext_for_magic == "tiff" and sniffed != "tiff":
                raise ValueError("magic_mismatch")
            elif ext_for_magic != "tiff" and sniffed != ext_for_magic:
                raise ValueError("magic_mismatch")

    return uploaded_file


def get_limits():
    return {
        "max_file_mb": getattr(settings, "DTF_MAX_FILE_MB", DEFAULT_MAX_FILE_MB),
        "max_copies": getattr(settings, "DTF_MAX_COPIES", DEFAULT_MAX_COPIES),
        "max_meters_review": Decimal(str(getattr(settings, "DTF_MAX_METERS_REVIEW", DEFAULT_MAX_METERS_REVIEW))),
    }


def get_pricing_config():
    config = getattr(settings, "DTF_PRICING", None)
    if not config:
        return {
            "base_rate": DEFAULT_BASE_RATE,
            "tiers": DEFAULT_TIERS,
        }
    base_rate = Decimal(str(config.get("base_rate", DEFAULT_BASE_RATE)))
    tiers = []
    for tier in config.get("tiers", DEFAULT_TIERS):
        tiers.append({
            "min": Decimal(str(tier.get("min"))),
            "rate": Decimal(str(tier.get("rate"))),
        })
    tiers.sort(key=lambda x: x["min"])
    return {"base_rate": base_rate, "tiers": tiers}


def get_feature_flags():
    flags = dict(DEFAULT_FEATURE_FLAGS)
    overrides = getattr(settings, "DTF_FEATURE_FLAGS", {}) or {}
    flags.update(overrides)
    return flags


def calculate_pricing(length_m: Decimal, copies: int):
    if length_m is None or copies is None:
        return None
    config = get_pricing_config()
    meters_total = (length_m * Decimal(copies)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = config["base_rate"]
    tier_label = "base"
    for tier in config["tiers"]:
        if meters_total >= tier["min"]:
            rate = tier["rate"]
            tier_label = f">={tier['min']}"
    price_total = (meters_total * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    limits = get_limits()
    requires_review = meters_total >= limits["max_meters_review"]
    return {
        "meters_total": meters_total,
        "rate": rate,
        "price_total": price_total,
        "pricing_tier": tier_label,
        "requires_review": requires_review,
    }


def _detect_pdf_mediabox(data: bytes):
    match = re.search(rb"/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]", data)
    if not match:
        return None
    try:
        x1 = float(match.group(1))
        y1 = float(match.group(2))
        x2 = float(match.group(3))
        y2 = float(match.group(4))
    except Exception:
        return None
    width_pt = max(0.0, x2 - x1)
    height_pt = max(0.0, y2 - y1)
    return width_pt, height_pt


def detect_length_m(uploaded_file) -> Decimal | None:
    if not uploaded_file:
        return None
    ext = get_file_extension(uploaded_file.name)
    try:
        if ext == "pdf":
            head = uploaded_file.read(50000)
            uploaded_file.seek(0)
            box = _detect_pdf_mediabox(head)
            if not box:
                return None
            width_pt, height_pt = box
            width_in = width_pt / 72.0
            height_in = height_pt / 72.0
            width_cm = width_in * 2.54
            height_cm = height_in * 2.54
            return _length_from_dimensions(width_cm, height_cm)
        if ext == "png" and Image:
            img = Image.open(uploaded_file)
            width_px, height_px = img.size
            dpi = img.info.get("dpi") or img.info.get("resolution")
            uploaded_file.seek(0)
            if dpi and isinstance(dpi, (tuple, list)):
                dpi_x = dpi[0] or 0
                dpi_y = dpi[1] or dpi_x
            elif dpi:
                dpi_x = dpi_y = dpi
            else:
                return None
            if not dpi_x:
                return None
            width_in = width_px / float(dpi_x)
            height_in = height_px / float(dpi_y or dpi_x)
            width_cm = width_in * 2.54
            height_cm = height_in * 2.54
            return _length_from_dimensions(width_cm, height_cm)
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return None
    return None


def _length_from_dimensions(width_cm: float, height_cm: float) -> Decimal | None:
    if not width_cm or not height_cm:
        return None
    # Expect width around 60cm; allow some tolerance
    tolerance = 8.0
    if abs(width_cm - 60.0) <= tolerance:
        length_cm = height_cm
    elif abs(height_cm - 60.0) <= tolerance:
        length_cm = width_cm
    else:
        return None
    length_m = Decimal(str(length_cm / 100.0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return length_m if length_m > 0 else None


def activate_language_from_request(request, allowed=("uk", "ru", "en")):
    lang = request.GET.get("lang")
    if lang in allowed:
        request.session["dtf_lang"] = lang
        request._dtf_lang = lang
    else:
        lang = request.session.get("dtf_lang") or request.COOKIES.get("dtf_lang") or allowed[0]
        request._dtf_lang = lang
    translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return lang


def build_lang_links(request, allowed=("uk", "ru", "en")):
    links = {}
    query = request.GET.copy()
    for code in allowed:
        query["lang"] = code
        links[code] = f"{request.path}?{urlencode(query, doseq=True)}"
    return links
