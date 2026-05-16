#!/usr/bin/env python3
"""
Render localized social preview JPEGs from SVG sources.

SEO molecular-upgrade US-17 — localized OG / Twitter cards.

Reads ``static/img/social-preview-{uk,ru,en}.svg`` and writes the
matching ``social-preview-{uk,ru,en}.jpg`` (1200x630, optimized JPEG)
back to the same directory. Run this whenever you update the SVG
templates; the resulting JPEGs ship as part of the static collect.

Usage::

    python scripts/render_social_previews.py

Dependencies: ``cairosvg`` and ``Pillow``. Both are listed in
``requirements.txt`` but optional during normal app runtime; this
script is invoked manually (or in CI) and never on the request path.

The script is fail-loud — missing dependencies / unreadable SVG sources
abort with a clear error so we never silently ship a stale card.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_IMG_DIR = REPO_ROOT / "twocomms_django_theme" / "static" / "img"
LOCALES = ("uk", "ru", "en")
WIDTH, HEIGHT = 1200, 630
JPEG_QUALITY = 88


def _load_dependencies():
    try:
        import cairosvg  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - script tooling
        raise SystemExit(
            "Missing dependency: install cairosvg and Pillow before running "
            "render_social_previews.py. On macOS / Linux:\n"
            "    pip install cairosvg Pillow\n\n"
            f"Underlying error: {exc}"
        ) from exc
    return cairosvg, Image


def render_one(locale: str) -> Path:
    cairosvg, Image = _load_dependencies()
    svg_path = STATIC_IMG_DIR / f"social-preview-{locale}.svg"
    jpg_path = STATIC_IMG_DIR / f"social-preview-{locale}.jpg"
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG source missing: {svg_path}")
    print(f"[render_social_previews] {locale}: {svg_path.name} → {jpg_path.name}")
    png_bytes = cairosvg.svg2png(
        url=str(svg_path), output_width=WIDTH, output_height=HEIGHT
    )
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img.save(jpg_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return jpg_path


def main() -> int:
    if not STATIC_IMG_DIR.exists():
        print(f"Static dir not found: {STATIC_IMG_DIR}", file=sys.stderr)
        return 1
    for locale in LOCALES:
        render_one(locale)
    print("[render_social_previews] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
