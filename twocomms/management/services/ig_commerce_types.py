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
