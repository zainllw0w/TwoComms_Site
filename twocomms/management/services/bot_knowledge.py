"""Reviewed public knowledge supplied to the bot policy compiler.

The repository Markdown directory is retained as an archive for editorial
review.  It is deliberately not read into provider payloads: only the
versioned runtime facts in :mod:`approved_public_facts` are provider-safe.
Live directives and the product catalogue remain separate compiler sources.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from django.core.cache import cache

from management.services.approved_public_facts import (
    approved_provider_fact_definitions,
)

CACHE_KEY_PREFIX = "ig_bot_knowledge_manifest_v4"


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


def read_knowledge_manifest(language: str = "uk") -> KnowledgeManifest:
    """Build provider modules from the reviewed runtime fact publication.

    No repository Markdown is opened here.  A missing runtime fact language
    is an explicit readiness failure rather than an accidental fall back to an
    unreviewed archive.
    """
    try:
        modules = [
            KnowledgeModule(module_id, body, priority)
            for module_id, body, priority in approved_provider_fact_definitions(language)
        ]
    except ValueError as exc:
        raise KnowledgeReadinessError(
            "approved_public_facts_unavailable",
            "approved public facts are unavailable for the requested language",
            details={"language": language},
        ) from exc
    payload = [{"id": module.id, "body": module.body, "priority": module.priority} for module in modules]
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return KnowledgeManifest(tuple(modules), digest)


def _read_all() -> str:
    """Compatibility wrapper for callers awaiting compiler integration."""
    return read_knowledge_manifest().text


def get_brand_knowledge(language: str = "uk") -> str:
    """Reviewed public knowledge cached by its actual language and content hash."""
    manifest = read_knowledge_manifest(language)
    cache_key = f"{CACHE_KEY_PREFIX}:{language}:{manifest.content_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    cache.set(cache_key, manifest.text, 3600)
    return manifest.text
