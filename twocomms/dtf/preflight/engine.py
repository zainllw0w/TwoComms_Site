from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Any

try:
    from PIL import Image, ImageFilter, ImageOps, ImageStat
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageFilter = None
    ImageOps = None
    ImageStat = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None

from ..utils import get_file_extension


ALLOWED_EXTS = {"png", "jpg", "jpeg", "webp", "pdf"}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PIXEL_DIM = 20000
SAFE_MARGIN_PX = 20


@dataclass(slots=True)
class Finding:
    code: str
    status: str
    message: str
    value: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "status": self.status,
            "message": self.message,
        }
        if self.value:
            payload["value"] = self.value
        return payload


def _sniff_magic(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "webp"
    return ""


def _to_result(findings: list[Finding], metrics: dict[str, Any], *, engine_version: str) -> dict[str, Any]:
    has_fail = any(item.status == "fail" for item in findings)
    has_warn = any(item.status == "warn" for item in findings)
    result = "FAIL" if has_fail else "WARN" if has_warn else "PASS"
    return {
        "result": result,
        "has_warn": has_warn,
        "has_fail": has_fail,
        "checks": [item.as_dict() for item in findings],
        "metrics": metrics,
        "warnings": [item.code for item in findings if item.status == "warn"],
        "errors": [item.code for item in findings if item.status == "fail"],
        "preflight_version": "2.0",
        "engine_version": engine_version,
    }


def _detect_dpi(image: Image.Image) -> float:
    dpi = image.info.get("dpi") if image and hasattr(image, "info") else None
    if isinstance(dpi, (tuple, list)) and dpi:
        return float(dpi[0] or 0)
    if isinstance(dpi, (int, float)):
        return float(dpi)
    return 0.0


def _tiny_text_risk(image: Image.Image) -> bool:
    if not (ImageOps and ImageFilter and ImageStat):
        return False
    gray = ImageOps.grayscale(image)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    mean_edge = float(stat.mean[0]) if stat.mean else 0.0
    return mean_edge > 26.0


def _analyze_image(data: bytes, findings: list[Finding], metrics: dict[str, Any]) -> None:
    if not Image:
        findings.append(Finding("PF_IMAGE_LIB_MISSING", "warn", "Image library unavailable"))
        return
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception:
        findings.append(Finding("PF_IMAGE_DECODE_FAIL", "fail", "Cannot decode image payload"))
        return
    width, height = image.size
    metrics["width_px"] = width
    metrics["height_px"] = height
    metrics["mode"] = image.mode

    if width > MAX_PIXEL_DIM or height > MAX_PIXEL_DIM:
        findings.append(Finding("PF_DIMENSIONS_TOO_LARGE", "fail", "Pixel dimensions exceed safe limit", f"{width}x{height}px"))
    else:
        findings.append(Finding("PF_DIMENSIONS_OK", "ok", "Pixel dimensions accepted", f"{width}x{height}px"))

    dpi = _detect_dpi(image)
    metrics["dpi"] = dpi or 0
    if dpi <= 0:
        findings.append(Finding("PF_DPI_UNKNOWN", "warn", "DPI metadata not found"))
    elif dpi < 300:
        findings.append(Finding("PF_DPI_LOW", "warn", "DPI is below 300", f"{dpi:.1f}"))
    else:
        findings.append(Finding("PF_DPI_OK", "ok", "DPI is acceptable", f"{dpi:.1f}"))

    if "A" in image.getbands():
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        metrics["has_alpha"] = True
        if bbox:
            left, top, right, bottom = bbox
            metrics["content_bbox"] = [left, top, right, bottom]
            if left < SAFE_MARGIN_PX or top < SAFE_MARGIN_PX or (width - right) < SAFE_MARGIN_PX or (height - bottom) < SAFE_MARGIN_PX:
                findings.append(Finding("PF_MARGIN_SMALL", "warn", "Content is too close to edge", f"bbox={bbox}"))
            else:
                findings.append(Finding("PF_MARGIN_OK", "ok", "Margins look safe", f"bbox={bbox}"))
        else:
            findings.append(Finding("PF_EMPTY_ALPHA", "warn", "Alpha channel has no visible content"))
    else:
        metrics["has_alpha"] = False
        findings.append(Finding("PF_NO_ALPHA", "warn", "No alpha channel detected"))

    mode = (image.mode or "").upper()
    if "CMYK" in mode:
        findings.append(Finding("PF_COLOR_CMYK", "warn", "CMYK image may shift colors in DTF workflow"))
    elif "RGB" in mode or "RGBA" in mode:
        findings.append(Finding("PF_COLOR_RGB", "ok", "RGB color mode detected"))
    else:
        findings.append(Finding("PF_COLOR_UNKNOWN", "warn", "Uncommon color mode", mode or "unknown"))

    if _tiny_text_risk(image):
        findings.append(Finding("PF_TINY_TEXT_RISK", "warn", "Potential tiny text or excessive detail"))
    else:
        findings.append(Finding("PF_TINY_TEXT_OK", "ok", "No tiny text risk detected"))


def _analyze_pdf(data: bytes, findings: list[Finding], metrics: dict[str, Any]) -> None:
    if not PdfReader:
        findings.append(Finding("PF_PDF_LIB_MISSING", "warn", "PDF parser unavailable; limited checks"))
        return
    reader = PdfReader(BytesIO(data))
    page_count = len(reader.pages)
    metrics["pdf_page_count"] = page_count
    if page_count > 1:
        findings.append(Finding("PF_PDF_MULTIPAGE", "fail", "Only single-page PDF is allowed"))
    else:
        findings.append(Finding("PF_PDF_PAGECOUNT_OK", "ok", "Single-page PDF"))

    if not reader.pages:
        findings.append(Finding("PF_PDF_EMPTY", "fail", "PDF has no pages"))
        return

    page = reader.pages[0]
    mediabox = page.mediabox
    width_pt = float(mediabox.width or 0)
    height_pt = float(mediabox.height or 0)
    metrics["pdf_width_pt"] = width_pt
    metrics["pdf_height_pt"] = height_pt
    if width_pt <= 0 or height_pt <= 0:
        findings.append(Finding("PF_PDF_MEDIABOX_INVALID", "fail", "Invalid PDF MediaBox"))
    else:
        findings.append(Finding("PF_PDF_MEDIABOX_OK", "ok", "MediaBox detected", f"{width_pt:.1f}x{height_pt:.1f}pt"))


def analyze_upload(uploaded_file, *, engine_version: str = "2.0.0", allowed_exts: set[str] | None = None) -> dict[str, Any]:
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    size_bytes = int(getattr(uploaded_file, "size", 0) or 0)
    allowed = allowed_exts or ALLOWED_EXTS
    metrics["ext"] = ext
    metrics["content_type"] = content_type
    metrics["size_bytes"] = size_bytes

    if ext not in allowed:
        findings.append(Finding("PF_TYPE_NOT_ALLOWED", "fail", "File extension is not allowed", ext or "unknown"))
        return _to_result(findings, metrics, engine_version=engine_version)

    if size_bytes > MAX_FILE_BYTES:
        findings.append(Finding("PF_FILE_TOO_LARGE", "fail", "File size exceeds max allowed", str(size_bytes)))
        return _to_result(findings, metrics, engine_version=engine_version)

    raw = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if not raw:
        findings.append(Finding("PF_EMPTY_FILE", "fail", "File is empty"))
        return _to_result(findings, metrics, engine_version=engine_version)

    metrics["sha256"] = hashlib.sha256(raw).hexdigest()
    magic = _sniff_magic(raw[:32])
    metrics["magic"] = magic or "unknown"

    if magic and ext not in {"jpeg"} and magic != ext and not (ext == "jpg" and magic == "jpg"):
        findings.append(Finding("PF_MAGIC_MISMATCH", "fail", "Magic bytes do not match extension"))
        return _to_result(findings, metrics, engine_version=engine_version)
    findings.append(Finding("PF_MAGIC_OK", "ok", "Magic bytes check passed", magic or ext))

    if ext == "pdf":
        _analyze_pdf(raw, findings, metrics)
    else:
        _analyze_image(raw, findings, metrics)

    return _to_result(findings, metrics, engine_version=engine_version)


def build_preview_assets(uploaded_file) -> tuple[bytes | None, bytes | None]:
    if not Image:
        return None, None
    ext = get_file_extension(getattr(uploaded_file, "name", ""))
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        return None, None

    raw = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    if not raw:
        return None, None

    image = Image.open(BytesIO(raw)).convert("RGBA")
    thumb = image.copy()
    thumb.thumbnail((1200, 1200))

    thumb_io = BytesIO()
    thumb.convert("RGB").save(thumb_io, format="JPEG", quality=88, optimize=True)

    overlay = thumb.copy()
    if "A" in overlay.getbands():
        alpha = overlay.getchannel("A")
        bbox = alpha.getbbox()
    else:
        bbox = None

    if bbox:
        from PIL import ImageDraw  # local import to avoid hard dependency in module init

        draw = ImageDraw.Draw(overlay)
        draw.rectangle(bbox, outline=(255, 120, 70, 255), width=3)
        margin = SAFE_MARGIN_PX
        draw.rectangle(
            (margin, margin, overlay.width - margin, overlay.height - margin),
            outline=(90, 168, 255, 210),
            width=2,
        )

    overlay_io = BytesIO()
    overlay.convert("RGB").save(overlay_io, format="JPEG", quality=88, optimize=True)
    return thumb_io.getvalue(), overlay_io.getvalue()
