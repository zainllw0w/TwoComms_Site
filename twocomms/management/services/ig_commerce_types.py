"""Small immutable value objects shared by Instagram commerce services.

These objects deliberately carry evidence and confidence separately.  A visual
candidate can be useful to the conversation without becoming a payable SKU.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ReferenceSource(StrEnum):
    STOREFRONT = "storefront"
    INSTAGRAM_POST = "instagram_post"
    SCREENSHOT = "screenshot"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProductReference:
    product_id: int | None = None
    is_exact: bool = False
    source: ReferenceSource = ReferenceSource.UNKNOWN
    reason: str = "unknown_reference"
    external_reference: str = ""
    constraints: tuple[tuple[str, str], ...] = ()
    candidate_product_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class CatalogProduct:
    product_id: int
    slug: str
    title: str
    price: int
    category: str
    aliases: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    traits: Mapping[str, str] = field(default_factory=dict)
    semantic_revision_id: int | None = None
    variants: tuple[Mapping[str, Any], ...] = ()
    fits: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class CatalogGraph:
    products: tuple[CatalogProduct, ...]
    digest: str
    canonical_json: str


@dataclass(frozen=True)
class CommerceTurnRequest:
    """Bounded language-model output consumed by deterministic commerce code."""

    exact_product_id: int | None = None
    exact_unique_alias: bool = False
    field_updates: Mapping[str, str] = field(default_factory=dict)
    hard: Mapping[str, str] = field(default_factory=dict)
    preferences: Mapping[str, str] = field(default_factory=dict)
    semantic_constraints: Mapping[str, str] = field(default_factory=dict)
    garment_type: str = ""


@dataclass(frozen=True)
class CatalogCandidate:
    product_id: int
    slug: str
    title: str
    price: int
    category: str
    traits: Mapping[str, str] = field(default_factory=dict)
    score: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()
    relaxed_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateDecision:
    candidates: tuple[CatalogCandidate, ...]
    auto_select: bool
    selected_product_id: int | None
    pending_question: str = ""
    relaxed_alternatives: tuple[CatalogCandidate, ...] = ()
