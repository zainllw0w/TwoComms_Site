"""Immutable value objects shared by Instagram catalog intelligence services."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


def immutable_mapping(value=None) -> Mapping:
    return MappingProxyType(dict(value or {}))


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
class PricingConfiguration:
    variant_id: int | None
    color_id: int | None
    color_slug: str
    color_label: str
    fit_code: str
    option_values: Mapping[str, str]
    compatible_sizes: tuple[str, ...]
    price: Decimal
    reason: str = ""
    is_thermo: bool = False

    def __post_init__(self):
        object.__setattr__(self, "option_values", immutable_mapping(self.option_values))


@dataclass(frozen=True)
class PriceSnapshot:
    configurations: tuple[PricingConfiguration, ...] = ()
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    exact: bool = False
    display: str = ""


@dataclass(frozen=True)
class CatalogVariant:
    variant_id: int
    color_id: int
    color_slug: str
    color_label: str
    sku: str = ""


@dataclass(frozen=True)
class CatalogFit:
    code: str
    label: str


@dataclass(frozen=True)
class CatalogProduct:
    product_id: int
    slug: str
    title: str
    category_id: int
    category_slug: str
    category_label: str
    garment_type: str = ""
    catalog_priority: int = 0
    aliases: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    traits: Mapping[str, str] = field(default_factory=dict)
    semantic_revision_id: int | None = None
    variants: tuple[CatalogVariant, ...] = ()
    fits: tuple[CatalogFit, ...] = ()
    pricing: PriceSnapshot = field(default_factory=PriceSnapshot)

    def __post_init__(self):
        object.__setattr__(self, "aliases", immutable_mapping(self.aliases))
        object.__setattr__(self, "traits", immutable_mapping(self.traits))


@dataclass(frozen=True)
class CatalogGraph:
    products: tuple[CatalogProduct, ...]
    digest: str
    canonical_json: str


@dataclass(frozen=True)
class CommerceTurnRequest:
    """Bounded model output consumed by deterministic catalog code."""

    exact_product_id: int | None = None
    exact_unique_alias: bool = False
    query: str = ""
    field_updates: Mapping[str, str] = field(default_factory=dict)
    hard: Mapping[str, str] = field(default_factory=dict)
    preferences: Mapping[str, str] = field(default_factory=dict)
    semantic_constraints: Mapping[str, str] = field(default_factory=dict)
    garment_type: str = ""

    def __post_init__(self):
        for field_name in (
            "field_updates",
            "hard",
            "preferences",
            "semantic_constraints",
        ):
            object.__setattr__(self, field_name, immutable_mapping(getattr(self, field_name)))


@dataclass(frozen=True)
class CatalogCandidate:
    product_id: int
    slug: str
    title: str
    category_id: int
    category_slug: str
    category_label: str
    garment_type: str
    catalog_priority: int
    traits: Mapping[str, str]
    pricing: PriceSnapshot
    constraints: tuple[tuple[str, str], ...] = ()
    score: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()
    relaxed_constraints: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "traits", immutable_mapping(self.traits))


@dataclass(frozen=True)
class CandidateDecision:
    candidates: tuple[CatalogCandidate, ...]
    auto_select: bool
    selected_product_id: int | None
    pending_question: str = ""
    relaxed_alternatives: tuple[CatalogCandidate, ...] = ()
    canonical_json: str = ""
