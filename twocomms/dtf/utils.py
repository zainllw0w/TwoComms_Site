from __future__ import annotations

import os
import re
import secrets
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from django.conf import settings
from django.utils import translation
from django.utils.text import slugify
from django.core.files.base import ContentFile

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None


ALLOWED_READY_EXTS = {"pdf", "png"}
ALLOWED_HELP_EXTS = {"pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff", "zip", "rar", "7z", "ai", "psd", "svg"}
ALLOWED_CONSTRUCTOR_EXTS = {"pdf", "png", "jpg", "jpeg", "webp"}
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
    "enable_preflight": True,
    "enable_underbase_preview": False,
    "enable_dynamic_favicon": True,
    "tier_mode": "auto",
}

CYRILLIC_TRANSLIT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "h",
    "ґ": "g",
    "д": "d",
    "е": "e",
    "є": "ye",
    "ж": "zh",
    "з": "z",
    "и": "y",
    "і": "i",
    "ї": "yi",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ь": "",
    "ю": "yu",
    "я": "ya",
    "ъ": "",
    "ы": "y",
    "э": "e",
    "ё": "yo",
}


def normalize_phone(value: str) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D+", "", value)
    return digits


def transliterate_cyrillic(value: str) -> str:
    source = (value or "").strip()
    if not source:
        return ""
    chunks = []
    for char in source:
        lower = char.lower()
        mapped = CYRILLIC_TRANSLIT_MAP.get(lower)
        if mapped is None:
            chunks.append(char)
            continue
        chunks.append(mapped.upper() if char.isupper() else mapped)
    return "".join(chunks)


def build_slug(value: str, *, fallback: str = "item", max_length: int = 240) -> str:
    base = transliterate_cyrillic(value or "")
    slug = slugify(base, allow_unicode=False)
    if not slug:
        slug = slugify(value or "", allow_unicode=False)
    slug = (slug or fallback or "item").strip("-")
    if not slug:
        slug = fallback or "item"
    return slug[:max_length].strip("-") or (fallback or "item")


def unique_slug_for_queryset(queryset, value: str, *, fallback: str = "item", max_length: int = 240, exclude_pk=None) -> str:
    scope = queryset
    if exclude_pk is not None:
        scope = scope.exclude(pk=exclude_pk)

    base = build_slug(value, fallback=fallback, max_length=max_length)
    candidate = base
    counter = 2
    while scope.filter(slug=candidate).exists():
        suffix = f"-{counter}"
        trimmed = base[: max_length - len(suffix)].rstrip("-")
        candidate = f"{trimmed}{suffix}"
        counter += 1
    return candidate


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


def build_content_file_from_bytes(payload: bytes, name: str) -> ContentFile:
    file_obj = ContentFile(payload)
    file_obj.name = name
    return file_obj


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


def _detect_page_dimensions_cm(uploaded_file) -> tuple[float | None, float | None]:
    if not uploaded_file:
        return None, None
    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    try:
        if ext == "pdf":
            head = uploaded_file.read(50000)
            uploaded_file.seek(0)
            box = _detect_pdf_mediabox(head)
            if not box:
                return None, None
            width_pt, height_pt = box
            return width_pt * 2.54 / 72.0, height_pt * 2.54 / 72.0
        if ext in {"png", "jpg", "jpeg", "webp"} and Image:
            img = Image.open(uploaded_file)
            width_px, height_px = img.size
            dpi = img.info.get("dpi") or img.info.get("resolution")
            uploaded_file.seek(0)
            if not dpi:
                return None, None
            if isinstance(dpi, (tuple, list)):
                dpi_x = float(dpi[0] or 0)
                dpi_y = float(dpi[1] or dpi_x or 0)
            else:
                dpi_x = float(dpi or 0)
                dpi_y = dpi_x
            if dpi_x <= 0 or dpi_y <= 0:
                return None, None
            width_cm = (width_px / dpi_x) * 2.54
            height_cm = (height_px / dpi_y) * 2.54
            return width_cm, height_cm
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return None, None
    return None, None


def build_preflight_report(uploaded_file, *, allowed_exts: set[str] | None = None):
    checks = []
    if not uploaded_file:
        return {
            "checks": [{"key": "file", "label": "Файл", "status": "fail", "message": "Файл не завантажено"}],
            "has_warn": False,
            "has_fail": True,
        }

    limits = get_limits()
    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    allowed = allowed_exts or ALLOWED_CONSTRUCTOR_EXTS
    checks.append({
        "key": "format",
        "label": "Формат",
        "status": "ok" if ext in allowed else "fail",
        "message": ext.upper() if ext else "N/A",
    })
    max_bytes = int(limits["max_file_mb"]) * 1024 * 1024
    size = int(getattr(uploaded_file, "size", 0) or 0)
    checks.append({
        "key": "size",
        "label": "Розмір",
        "status": "ok" if size and size <= max_bytes else ("warn" if size else "fail"),
        "message": f"{round(size / (1024 * 1024), 2)} MB" if size else "N/A",
    })

    width_cm, height_cm = _detect_page_dimensions_cm(uploaded_file)
    if width_cm and height_cm:
        roll_ok = abs(width_cm - 60.0) <= 8.0 or abs(height_cm - 60.0) <= 8.0
        checks.append({
            "key": "roll_width",
            "label": "Ширина 60 см",
            "status": "ok" if roll_ok else "warn",
            "message": f"{width_cm:.1f}×{height_cm:.1f} см",
        })
    else:
        checks.append({
            "key": "roll_width",
            "label": "Ширина 60 см",
            "status": "warn",
            "message": "Не вдалося точно визначити",
        })

    mime_result = "ok"
    try:
        validate_uploaded_file(
            uploaded_file,
            allowed_exts=allowed,
            max_file_mb=limits["max_file_mb"],
            strict_magic=True,
        )
    except ValueError as exc:
        code = str(exc)
        if code in {"unsupported_extension", "file_too_large"}:
            mime_result = "fail"
        else:
            mime_result = "warn"

    checks.append({
        "key": "security",
        "label": "Security",
        "status": mime_result,
        "message": "Magic/MIME check",
    })
    has_warn = any(item["status"] == "warn" for item in checks)
    has_fail = any(item["status"] == "fail" for item in checks)
    return {
        "checks": checks,
        "has_warn": has_warn,
        "has_fail": has_fail,
    }


def _load_design_image(uploaded_file):
    if not uploaded_file or not Image:
        return None
    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        return None
    try:
        image = Image.open(uploaded_file).convert("RGBA")
        uploaded_file.seek(0)
        return image
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return None


def render_constructor_preview(uploaded_file, *, product_type: str, placement: str, product_color: str = "#151515") -> bytes | None:
    if not Image or not ImageDraw:
        return None
    canvas = Image.new("RGBA", (1200, 1200), "#0b0b0d")
    draw = ImageDraw.Draw(canvas)
    panel = (140, 120, 1060, 1090)
    draw.rounded_rectangle(panel, radius=36, fill="#101318", outline="#2e3340", width=3)

    garment = (280, 220, 920, 1040)
    draw.rounded_rectangle(garment, radius=56, fill=product_color, outline="#5f6475", width=2)
    draw.ellipse((515, 210, 685, 340), fill="#0b0b0d")

    label = f"{(product_type or 'product').upper()} • {(placement or 'front').upper()}"
    font = ImageFont.load_default() if ImageFont else None
    draw.text((180, 145), "DTF CONSTRUCTOR PREVIEW", fill="#d7dbff", font=font)
    draw.text((180, 176), label, fill="#8e95bb", font=font)

    placement_map = {
        "front": (600, 560, 460, 460),
        "back": (600, 560, 460, 460),
        "left_chest": (485, 470, 240, 240),
        "sleeve": (820, 470, 180, 180),
    }
    cx, cy, box_w, box_h = placement_map.get(placement, placement_map["front"])
    x0 = int(cx - box_w / 2)
    y0 = int(cy - box_h / 2)
    x1 = x0 + box_w
    y1 = y0 + box_h
    draw.rounded_rectangle((x0, y0, x1, y1), radius=18, outline="#f6f7ff", width=2)

    design = _load_design_image(uploaded_file)
    if design:
        ratio = min((box_w - 20) / design.width, (box_h - 20) / design.height)
        new_size = (max(1, int(design.width * ratio)), max(1, int(design.height * ratio)))
        design = design.resize(new_size)
        px = int(cx - new_size[0] / 2)
        py = int(cy - new_size[1] / 2)
        canvas.alpha_composite(design, (px, py))
    else:
        draw.text((x0 + 18, y0 + 18), "DESIGN PLACEHOLDER", fill="#c7cbdd", font=font)
        draw.text((x0 + 18, y0 + 44), "PDF/FILE UPLOADED", fill="#8087aa", font=font)

    buf = BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


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
