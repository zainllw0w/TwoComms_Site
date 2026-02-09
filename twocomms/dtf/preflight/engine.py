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
ROLL_WIDTH_CM = 60.0
ROLL_WIDTH_TOLERANCE_CM = 8.0


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


def _status_score(status: str) -> int:
    normalized = (status or "").lower()
    if normalized == "fail":
        return 3
    if normalized == "warn":
        return 2
    if normalized == "ok":
        return 1
    return 0


def _pick_worst_status(*statuses: str) -> str:
    best = "ok"
    best_score = 1
    for status in statuses:
        score = _status_score(status)
        if score > best_score:
            best = status
            best_score = score
    return best


def _first_finding(findings: list[Finding], codes: set[str]) -> Finding | None:
    for item in findings:
        if item.code in codes:
            return item
    return None


def _first_by_status(findings: list[Finding], status: str) -> Finding | None:
    target = (status or "").lower()
    for item in findings:
        if (item.status or "").lower() == target:
            return item
    return None


def _physical_size_cm(metrics: dict[str, Any]) -> tuple[float, float] | None:
    width_pt = float(metrics.get("pdf_width_pt") or 0)
    height_pt = float(metrics.get("pdf_height_pt") or 0)
    if width_pt > 0 and height_pt > 0:
        return (width_pt * 2.54 / 72.0, height_pt * 2.54 / 72.0)

    width_px = float(metrics.get("width_px") or 0)
    height_px = float(metrics.get("height_px") or 0)
    dpi = float(metrics.get("dpi") or 0)
    if width_px > 0 and height_px > 0 and dpi > 0:
        return (width_px * 2.54 / dpi, height_px * 2.54 / dpi)
    return None


def _is_roll_width_ok(dimensions: tuple[float, float] | None) -> bool:
    if not dimensions:
        return False
    width_cm, height_cm = dimensions
    return (
        abs(width_cm - ROLL_WIDTH_CM) <= ROLL_WIDTH_TOLERANCE_CM
        or abs(height_cm - ROLL_WIDTH_CM) <= ROLL_WIDTH_TOLERANCE_CM
    )


def _format_cm_value(dimensions: tuple[float, float] | None) -> str:
    if not dimensions:
        return ""
    width_cm, height_cm = dimensions
    return f"{width_cm:.1f}x{height_cm:.1f} cm"


def _build_recommendations(
    findings: list[Finding],
    metrics: dict[str, Any],
    result: str,
) -> list[str]:
    code_set = {item.code for item in findings}
    recommendations: list[str] = []

    if {"PF_DPI_LOW", "PF_DPI_UNKNOWN"} & code_set:
        recommendations.append("Export artwork at 300 DPI for stable print detail.")
    if "PF_MARGIN_SMALL" in code_set:
        recommendations.append("Keep critical artwork at least 20 px away from file edges.")
    if {"PF_NO_ALPHA", "PF_EMPTY_ALPHA"} & code_set:
        recommendations.append("Use transparent background and trim unused canvas.")
    if "PF_TINY_TEXT_RISK" in code_set:
        recommendations.append("Avoid ultra-thin lines and text below ~1 pt.")
    if not _is_roll_width_ok(_physical_size_cm(metrics)):
        recommendations.append("Ensure one file side aligns with 60 cm roll width.")
    if (result or "").upper() == "FAIL":
        recommendations.append("Resolve FAIL checks before submitting the file.")
    if not recommendations:
        recommendations.append("File passed automated checks; proceed to manual manager review.")
    return recommendations


def _build_step_items(
    findings: list[Finding],
    metrics: dict[str, Any],
    result: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    step_items: list[dict[str, Any]] = []

    format_fail = {
        "PF_TYPE_NOT_ALLOWED",
        "PF_FILE_TOO_LARGE",
        "PF_EMPTY_FILE",
        "PF_MAGIC_MISMATCH",
        "PF_IMAGE_DECODE_FAIL",
    }
    format_warn = {
        "PF_IMAGE_LIB_MISSING",
        "PF_PDF_LIB_MISSING",
    }
    format_ok = {
        "PF_MAGIC_OK",
    }
    dpi_warn = {"PF_DPI_UNKNOWN", "PF_DPI_LOW"}
    dpi_ok = {"PF_DPI_OK"}
    size_fail = {"PF_DIMENSIONS_TOO_LARGE", "PF_PDF_EMPTY", "PF_PDF_MULTIPAGE", "PF_PDF_MEDIABOX_INVALID"}
    transparency_warn = {"PF_MARGIN_SMALL", "PF_NO_ALPHA", "PF_EMPTY_ALPHA"}
    transparency_ok = {"PF_MARGIN_OK"}
    tiny_warn = {"PF_TINY_TEXT_RISK", "PF_IMAGE_LIB_MISSING"}
    tiny_ok = {"PF_TINY_TEXT_OK"}

    format_finding = _first_finding(findings, format_fail)
    if format_finding:
        format_status = "fail"
        format_message = format_finding.message
        format_value = format_finding.value
    else:
        format_warn_finding = _first_finding(findings, format_warn)
        format_ok_finding = _first_finding(findings, format_ok)
        if format_warn_finding:
            format_status = "warn"
            format_message = format_warn_finding.message
            format_value = format_warn_finding.value
        elif format_ok_finding:
            format_status = "ok"
            format_message = format_ok_finding.message
            format_value = format_ok_finding.value
        else:
            format_status = "warn"
            format_message = "Format/signature check is incomplete."
            format_value = ""

    step_items.append(
        {
            "key": "format_signature",
            "label": "Format / signature",
            "status": format_status,
            "message": format_message,
            "value": format_value,
        }
    )

    dpi_warn_finding = _first_finding(findings, dpi_warn)
    dpi_ok_finding = _first_finding(findings, dpi_ok)
    if dpi_warn_finding:
        dpi_status = "warn"
        dpi_message = dpi_warn_finding.message
        dpi_value = dpi_warn_finding.value
    elif dpi_ok_finding:
        dpi_status = "ok"
        dpi_message = dpi_ok_finding.message
        dpi_value = dpi_ok_finding.value
    elif str(metrics.get("ext") or "").lower() == "pdf":
        dpi_status = "warn"
        dpi_message = "DPI check for PDF requires rasterization."
        dpi_value = ""
    else:
        dpi_status = "warn"
        dpi_message = "DPI check did not return a stable value."
        dpi_value = ""

    step_items.append(
        {
            "key": "dpi",
            "label": "DPI",
            "status": dpi_status,
            "message": dpi_message,
            "value": dpi_value,
        }
    )

    size_fail_finding = _first_finding(findings, size_fail)
    dimensions = _physical_size_cm(metrics)
    width_ok = _is_roll_width_ok(dimensions)
    if size_fail_finding:
        size_status = "fail"
        size_message = size_fail_finding.message
        size_value = size_fail_finding.value
    else:
        if dimensions:
            size_status = "ok" if width_ok else "warn"
            size_message = "60 cm roll rule passed." if width_ok else "60 cm roll rule mismatch."
            size_value = _format_cm_value(dimensions)
        else:
            size_status = "warn"
            size_message = "Physical size could not be derived."
            size_value = ""

    step_items.append(
        {
            "key": "physical_size_60cm",
            "label": "Physical size / 60 cm",
            "status": size_status,
            "message": size_message,
            "value": size_value,
        }
    )

    transparency_warn_finding = _first_finding(findings, transparency_warn)
    transparency_ok_finding = _first_finding(findings, transparency_ok)
    if transparency_warn_finding:
        trans_status = "warn"
        trans_message = transparency_warn_finding.message
        trans_value = transparency_warn_finding.value
    elif transparency_ok_finding:
        trans_status = "ok"
        trans_message = transparency_ok_finding.message
        trans_value = transparency_ok_finding.value
    elif str(metrics.get("ext") or "").lower() == "pdf":
        trans_status = "warn"
        trans_message = "Transparency and edge bounds are limited for PDF."
        trans_value = ""
    else:
        trans_status = "warn"
        trans_message = "Transparency/edge analysis is incomplete."
        trans_value = ""

    step_items.append(
        {
            "key": "transparency_bounds",
            "label": "Transparency / bounds",
            "status": trans_status,
            "message": trans_message,
            "value": trans_value,
        }
    )

    tiny_warn_finding = _first_finding(findings, tiny_warn)
    tiny_ok_finding = _first_finding(findings, tiny_ok)
    if tiny_warn_finding:
        tiny_status = "warn"
        tiny_message = tiny_warn_finding.message
        tiny_value = tiny_warn_finding.value
    elif tiny_ok_finding:
        tiny_status = "ok"
        tiny_message = tiny_ok_finding.message
        tiny_value = tiny_ok_finding.value
    elif str(metrics.get("ext") or "").lower() == "pdf":
        tiny_status = "warn"
        tiny_message = "Tiny-line risk check is not available for PDF."
        tiny_value = ""
    else:
        tiny_status = "warn"
        tiny_message = "Tiny-line risk check is incomplete."
        tiny_value = ""

    step_items.append(
        {
            "key": "tiny_lines",
            "label": "Tiny lines risk",
            "status": tiny_status,
            "message": tiny_message,
            "value": tiny_value,
        }
    )

    result_upper = (result or "").upper()
    summary_status = "ok"
    summary_message = "Preflight PASS."
    if result_upper == "FAIL":
        summary_status = "fail"
        summary_message = "Preflight FAIL: fix critical issues."
    elif result_upper == "WARN":
        summary_status = "warn"
        summary_message = "Preflight WARN: review recommendations."

    recommendations = _build_recommendations(findings, metrics, result_upper)
    summary = {
        "status": summary_status,
        "message": summary_message,
        "recommendations": recommendations,
    }
    step_items.append(
        {
            "key": "summary",
            "label": "Summary",
            "status": summary_status,
            "message": summary_message,
            "recommendations": recommendations,
        }
    )
    return step_items, recommendations, summary


def _to_result(findings: list[Finding], metrics: dict[str, Any], *, engine_version: str) -> dict[str, Any]:
    has_fail = any(item.status == "fail" for item in findings)
    has_warn = any(item.status == "warn" for item in findings)
    result = "FAIL" if has_fail else "WARN" if has_warn else "PASS"
    step_items, recommendations, summary = _build_step_items(findings, metrics, result)
    return {
        "result": result,
        "has_warn": has_warn,
        "has_fail": has_fail,
        "checks": [item.as_dict() for item in findings],
        "metrics": metrics,
        "warnings": [item.code for item in findings if item.status == "warn"],
        "errors": [item.code for item in findings if item.status == "fail"],
        "step_items": step_items,
        "summary": summary,
        "recommendations": recommendations,
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


def normalize_preflight_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    normalized = dict(report)
    if normalized.get("step_items") and normalized.get("summary"):
        return normalized

    checks = normalized.get("checks") or []
    findings: list[Finding] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        status = str(item.get("status") or "warn").strip().lower()
        message = str(item.get("message") or "").strip()
        value = str(item.get("value") or "").strip()
        findings.append(Finding(code=code, status=status, message=message, value=value))

    has_fail = bool(normalized.get("has_fail"))
    has_warn = bool(normalized.get("has_warn"))
    result = str(normalized.get("result") or "").upper()
    if result not in {"PASS", "WARN", "FAIL"}:
        result = "FAIL" if has_fail else "WARN" if has_warn else "PASS"
    metrics = normalized.get("metrics") if isinstance(normalized.get("metrics"), dict) else {}

    if findings:
        step_items, recommendations, summary = _build_step_items(findings, metrics, result)
    else:
        summary_status = "fail" if result == "FAIL" else "warn" if result == "WARN" else "ok"
        summary_message = "Preflight FAIL: fix critical issues." if result == "FAIL" else (
            "Preflight WARN: review recommendations." if result == "WARN" else "Preflight PASS."
        )
        recommendations = list(normalized.get("recommendations") or [])
        if not recommendations:
            recommendations = ["Upload a file to run full preflight checks."]
        summary = {
            "status": summary_status,
            "message": summary_message,
            "recommendations": recommendations,
        }
        step_items = [
            {
                "key": "summary",
                "label": "Summary",
                "status": summary_status,
                "message": summary_message,
                "recommendations": recommendations,
            }
        ]

    normalized["result"] = result
    normalized["has_fail"] = result == "FAIL" or has_fail
    normalized["has_warn"] = result == "WARN" or has_warn
    normalized["step_items"] = step_items
    normalized["summary"] = summary
    normalized["recommendations"] = recommendations
    return normalized


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
