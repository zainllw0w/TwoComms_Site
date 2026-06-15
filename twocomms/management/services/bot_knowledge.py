"""
База знань бота TwoComms.

Три шари контексту (об'єднуються і кешуються, інжектяться в Gemini):
1. Репозиторні Markdown-файли: management/bot_knowledge/*.md
   (бренд, засновник, доставка, оплата, повернення, промо, розмірні сітки,
   колаборації, FAQ, тон спілкування). Версіонуються в git, редагуються вручну.
2. Live-директиви: поле InstagramBotSettings.knowledge_base (редагується в UI
   вкладки «Бот» миттєво) — напр. «закінчились футболки з резинкою → пропонувати
   без резинки». Найвищий пріоритет.
3. Каталог товарів (див. bot_catalog).

Файли кешуються; інвалідовуються за max(mtime), тож правки підхоплюються без
рестарту.
"""
from __future__ import annotations

import os

from django.core.cache import cache

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_knowledge")
CACHE_KEY = "ig_bot_knowledge_md"
CACHE_MTIME_KEY = "ig_bot_knowledge_mtime"
MAX_CHARS = 24000


def _dir_mtime() -> float:
    latest = 0.0
    try:
        for name in os.listdir(KNOWLEDGE_DIR):
            if name.lower().endswith(".md"):
                p = os.path.join(KNOWLEDGE_DIR, name)
                latest = max(latest, os.path.getmtime(p))
    except FileNotFoundError:
        return 0.0
    return latest


def _read_all() -> str:
    parts = []
    try:
        for name in sorted(os.listdir(KNOWLEDGE_DIR)):
            if not name.lower().endswith(".md"):
                continue
            try:
                with open(os.path.join(KNOWLEDGE_DIR, name), encoding="utf-8") as fh:
                    text = fh.read().strip()
                if text:
                    parts.append(text)
            except Exception:
                continue
    except FileNotFoundError:
        return ""
    combined = "\n\n".join(parts).strip()
    if len(combined) > MAX_CHARS:
        combined = combined[:MAX_CHARS] + "\n…(скорочено)"
    return combined


def get_brand_knowledge() -> str:
    """Контент усіх MD-файлів бази знань (з кешем за mtime)."""
    mtime = _dir_mtime()
    cached_mtime = cache.get(CACHE_MTIME_KEY)
    cached = cache.get(CACHE_KEY)
    if cached is not None and cached_mtime == mtime:
        return cached
    text = _read_all()
    cache.set(CACHE_KEY, text, 3600)
    cache.set(CACHE_MTIME_KEY, mtime, 3600)
    return text
