"""Helpers for parsing product video URLs (YouTube).

Used by ``Product.video_*`` properties, the PDP gallery (видео-слайд),
Schema.org ``VideoObject`` and the Google Merchant feed ``video_link``.

Supported input formats:
    * https://www.youtube.com/watch?v=<id>
    * https://youtu.be/<id>
    * https://www.youtube.com/embed/<id>
    * https://www.youtube.com/shorts/<id>
    * https://m.youtube.com/watch?v=<id>
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


def extract_youtube_id(url: str) -> str:
    """Return the YouTube video id from any supported URL, else ``""``."""
    raw = (url or "").strip()
    if not raw:
        return ""

    # Bare id passed straight in (defensive — admin may paste just the id).
    if _YOUTUBE_ID_RE.match(raw) and "/" not in raw and "." not in raw:
        return raw

    parsed = urlparse(raw)
    netloc = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if netloc.endswith("youtu.be"):
        candidate = path.strip("/").split("/", 1)[0]
        return candidate if _YOUTUBE_ID_RE.match(candidate) else ""

    if "youtube.com" in netloc or "youtube-nocookie.com" in netloc:
        query = parse_qs(parsed.query)
        if query.get("v"):
            candidate = query["v"][0]
            return candidate if _YOUTUBE_ID_RE.match(candidate) else ""
        match = re.search(r"/(?:embed|shorts|v)/([^/?#]+)", path)
        if match:
            candidate = match.group(1)
            return candidate if _YOUTUBE_ID_RE.match(candidate) else ""

    return ""


def youtube_embed_url(video_id: str) -> str:
    """Privacy-friendly embed URL (youtube-nocookie) for an iframe."""
    if not video_id:
        return ""
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def youtube_watch_url(video_id: str) -> str:
    """Canonical watch URL — used by Merchant feed ``video_link``."""
    if not video_id:
        return ""
    return f"https://www.youtube.com/watch?v={video_id}"


def youtube_thumbnail_url(video_id: str, quality: str = "hqdefault") -> str:
    """Static poster image served by YouTube's image CDN."""
    if not video_id:
        return ""
    return f"https://i.ytimg.com/vi/{video_id}/{quality}.jpg"
