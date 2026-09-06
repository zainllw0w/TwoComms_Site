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

from dataclasses import dataclass
from hashlib import sha256
import json
import os

from django.core.cache import cache

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_knowledge")
CACHE_KEY = "ig_bot_knowledge_manifest_v2"
CACHE_MTIME_KEY = "ig_bot_knowledge_mtime_v2"


class KnowledgeReadinessError(RuntimeError):
    """The versioned knowledge source cannot safely participate in a prompt.

    Details deliberately contain source identifiers only, never file contents.
    """

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True)
class KnowledgeModule:
    id: str
    body: str
    priority: int

    def policy_input(self) -> dict:
        return {"id": self.id, "body": self.body, "priority": self.priority, "tags": (), "active": True}


@dataclass(frozen=True)
class KnowledgeManifest:
    modules: tuple[KnowledgeModule, ...]
    content_hash: str

    @property
    def text(self) -> str:
        return "\n\n".join(module.body for module in self.modules)

    def policy_inputs(self) -> list[dict]:
        return [module.policy_input() for module in self.modules]


def _dir_mtime() -> float:
    latest = 0.0
    try:
        for name in os.listdir(KNOWLEDGE_DIR):
            if name.lower().endswith(".md"):
                p = os.path.join(KNOWLEDGE_DIR, name)
                latest = max(latest, os.path.getmtime(p))
    except FileNotFoundError as exc:
        raise KnowledgeReadinessError(
            "knowledge_directory_missing", "knowledge directory is missing",
            details={"source": "repository_knowledge"},
        ) from exc
    except OSError as exc:
        raise KnowledgeReadinessError(
            "knowledge_directory_unreadable", "knowledge directory cannot be read",
            details={"source": "repository_knowledge", "error_type": type(exc).__name__},
        ) from exc
    return latest


def read_knowledge_manifest() -> KnowledgeManifest:
    """Read every Markdown source as a whole semantic module.

    Unlike the old helper, a missing or unreadable file is a readiness gap,
    not an invisible deletion and not a character slice through a rule.
    """
    modules: list[KnowledgeModule] = []
    try:
        for name in sorted(os.listdir(KNOWLEDGE_DIR)):
            if not name.lower().endswith(".md"):
                continue
            try:
                with open(os.path.join(KNOWLEDGE_DIR, name), encoding="utf-8") as fh:
                    text = fh.read().strip()
            except (OSError, UnicodeError) as exc:
                raise KnowledgeReadinessError(
                    "knowledge_file_unreadable", "knowledge file cannot be read",
                    details={"id": f"knowledge:{name}", "error_type": type(exc).__name__},
                ) from exc
            if text:
                modules.append(KnowledgeModule(f"knowledge:{name}", text, len(modules)))
    except FileNotFoundError as exc:
        raise KnowledgeReadinessError(
            "knowledge_directory_missing", "knowledge directory is missing",
            details={"source": "repository_knowledge"},
        ) from exc
    except OSError as exc:
        raise KnowledgeReadinessError(
            "knowledge_directory_unreadable", "knowledge directory cannot be read",
            details={"source": "repository_knowledge", "error_type": type(exc).__name__},
        ) from exc
    payload = [{"id": module.id, "body": module.body, "priority": module.priority} for module in modules]
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return KnowledgeManifest(tuple(modules), digest)


def _read_all() -> str:
    """Compatibility wrapper for callers awaiting compiler integration."""
    return read_knowledge_manifest().text


def get_brand_knowledge() -> str:
    """Контент усіх MD-файлів бази знань (з кешем за mtime)."""
    mtime = _dir_mtime()
    cached_mtime = cache.get(CACHE_MTIME_KEY)
    cached = cache.get(CACHE_KEY)
    if cached is not None and cached_mtime == mtime:
        return cached.text
    manifest = read_knowledge_manifest()
    cache.set(CACHE_KEY, manifest, 3600)
    cache.set(CACHE_MTIME_KEY, mtime, 3600)
    return manifest.text
