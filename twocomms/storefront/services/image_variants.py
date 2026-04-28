"""
Хелперы для отдачи оптимизированных media-вариантов без принудительной загрузки оригиналов.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from django.conf import settings


DEFAULT_DISPLAY_WIDTH = 640
DEFAULT_THUMB_WIDTH = 320
MAX_RESPONSIVE_WIDTH = 1440


def _media_url_prefixes() -> Tuple[str, ...]:
    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    prefixes = {media_url}
    if not media_url.startswith("/"):
        prefixes.add(f"/{media_url}")
    return tuple(sorted(prefixes, key=len, reverse=True))


def _url_and_path(image: Any) -> Tuple[str, Optional[Path]]:
    if not image:
        return "", None

    url = ""
    path = None

    if hasattr(image, "url"):
        try:
            url = image.url
        except Exception:
            url = ""
    if not url:
        url = str(image or "")

    if hasattr(image, "path"):
        try:
            path = Path(image.path)
        except Exception:
            path = None

    if path is None and url:
        for prefix in _media_url_prefixes():
            if url.startswith(prefix):
                relative = url[len(prefix):]
                path = Path(settings.MEDIA_ROOT) / relative
                break

    return url, path


def _optimized_url(original_url: str, filename: str) -> str:
    base_url = original_url.rsplit("/", 1)[0] if "/" in original_url else ""
    if not base_url:
        return f"optimized/{filename}"
    return f"{base_url}/optimized/{filename}"


def _existing_responsive_entries(
    original_url: str,
    optimized_dir: Path,
    stem: str,
    extension: str,
) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    pattern = re.compile(rf"^{re.escape(stem)}_(\d+)w\.{re.escape(extension)}$")
    for candidate in optimized_dir.glob(f"{stem}_*w.{extension}"):
        match = pattern.match(candidate.name)
        if not match or not candidate.exists():
            continue
        width = int(match.group(1))
        if width > MAX_RESPONSIVE_WIDTH:
            continue
        entries.append((width, _optimized_url(original_url, candidate.name)))
    return sorted(entries, key=lambda item: item[0])


def _choose_width(entries: list[tuple[int, str]], preferred_width: int) -> str:
    if not entries:
        return ""
    for width, url in entries:
        if width >= preferred_width:
            return url
    return entries[-1][1]


def _srcset(entries: list[tuple[int, str]]) -> str:
    return ", ".join(f"{url} {width}w" for width, url in entries)


def build_optimized_image_payload(
    image: Any,
    *,
    display_width: int = DEFAULT_DISPLAY_WIDTH,
    thumb_width: int = DEFAULT_THUMB_WIDTH,
) -> Dict[str, str]:
    """
    Возвращает JSON-safe URL для одного media-изображения.

    `url` — легкий default src для JS-созданных <img>. `original_url` остается
    доступным для zoom/download и как fallback, если optimized-файлы еще не созданы.
    """
    original_url, path = _url_and_path(image)
    if not original_url:
        return {}

    payload = {
        "url": original_url,
        "src": original_url,
        "original_url": original_url,
        "zoom_url": original_url,
        "thumbnail_url": original_url,
        "avif_url": "",
        "webp_url": "",
        "avif_srcset": "",
        "webp_srcset": "",
        "sizes": "(max-width: 768px) 94vw, (max-width: 992px) 90vw, (max-width: 1600px) 46vw, 720px",
    }

    if path is None:
        return payload

    optimized_dir = path.parent / "optimized"
    stem = path.stem
    avif_entries = _existing_responsive_entries(original_url, optimized_dir, stem, "avif")
    webp_entries = _existing_responsive_entries(original_url, optimized_dir, stem, "webp")

    avif_base = optimized_dir / f"{stem}.avif"
    webp_base = optimized_dir / f"{stem}.webp"

    if avif_entries:
        payload["avif_srcset"] = _srcset(avif_entries)
        payload["avif_url"] = _choose_width(avif_entries, display_width)
    elif avif_base.exists():
        payload["avif_url"] = _optimized_url(original_url, avif_base.name)
        payload["avif_srcset"] = payload["avif_url"]

    if webp_entries:
        payload["webp_srcset"] = _srcset(webp_entries)
        payload["webp_url"] = _choose_width(webp_entries, display_width)
        payload["thumbnail_url"] = _choose_width(webp_entries, thumb_width)
    elif webp_base.exists():
        payload["webp_url"] = _optimized_url(original_url, webp_base.name)
        payload["webp_srcset"] = payload["webp_url"]
        payload["thumbnail_url"] = payload["webp_url"]

    payload["url"] = payload["webp_url"] or payload["original_url"]
    payload["src"] = payload["url"]
    return payload


def optimized_variants_are_current(image_path: Path) -> bool:
    """
    True, если базовые WebP и AVIF существуют и не старее исходника.
    """
    try:
        source_mtime = image_path.stat().st_mtime
    except OSError:
        return False

    optimized_dir = image_path.parent / "optimized"
    required = (
        optimized_dir / f"{image_path.stem}.webp",
        optimized_dir / f"{image_path.stem}.avif",
    )
    for candidate in required:
        try:
            if candidate.stat().st_mtime < source_mtime:
                return False
        except OSError:
            return False
    return True
