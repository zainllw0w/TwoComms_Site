"""Build a deterministic, verified and price-aware catalog snapshot."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError

from fable5.size_grid_services import normalize_size_grid_payload, normalize_size_value
from productcolors.models import ProductColorVariant
from storefront.models import (
    Product,
    ProductSalesSemanticProfileRevision,
    ProductStatus,
)

from .ig_catalog_pricing import prepare_pricing_context, resolve_product_pricing
from .ig_commerce_types import (
    CatalogFit,
    CatalogGraph,
    CatalogProduct,
    CatalogVariant,
    PriceSnapshot,
    PricingConfiguration,
)


def _money_json(value: Decimal | None):
    return format(value, "f") if value is not None else None


def _aliases(value) -> dict[str, tuple[str, ...]]:
    return {
        str(locale): tuple(str(alias) for alias in aliases)
        for locale, aliases in sorted((value or {}).items())
        if isinstance(aliases, list)
    }


_GARMENT_TYPES_BY_CATEGORY = {
    "tshirt": "tshirt",
    "tshirts": "tshirt",
    "t-shirt": "tshirt",
    "t-shirts": "tshirt",
    "hoodie": "hoodie",
    "hoodies": "hoodie",
    "long-sleeve": "longsleeve",
    "long-sleeves": "longsleeve",
    "longsleeve": "longsleeve",
    "longsleeves": "longsleeve",
    "sweatshirt": "sweatshirt",
    "sweatshirts": "sweatshirt",
}


def _prefetched(obj, relation):
    cache = getattr(obj, "_prefetched_objects_cache", {})
    return list(cache.get(relation, ()))


def _usable_grid(grid):
    if grid is None or not grid.is_active:
        return None
    try:
        profile = grid.fable5_profile
    except Exception:
        profile = None
    return grid if profile is None or profile.is_active else None


def _grid_sizes(grid) -> list[str]:
    grid = _usable_grid(grid)
    if grid is None:
        return []
    try:
        guide = normalize_size_grid_payload(deepcopy(grid.guide_data or {}))
    except ValidationError:
        return []
    return list(dict.fromkeys(
        normalized
        for row in guide.get("rows", ())
        if (normalized := normalize_size_value(row.get("size")))
    ))


def _catalog_sizes(product) -> list[str]:
    catalog = getattr(product, "catalog", None)
    if catalog is None:
        return []
    size_options = sorted(
        (
            option for option in _prefetched(catalog, "options")
            if option.option_type == "size"
        ),
        key=lambda option: (option.order, option.id),
    )
    if not size_options:
        return []
    values = sorted(
        _prefetched(size_options[0], "values"),
        key=lambda value: (value.order, value.id),
    )
    return list(dict.fromkeys(
        normalized
        for value in values
        if (normalized := normalize_size_value(value.value))
    ))


def _fallback_grid(product, option_key):
    direct = _usable_grid(getattr(product, "size_grid", None))
    if direct is not None:
        return direct
    catalog = getattr(product, "catalog", None)
    if catalog is None:
        return None
    grids = sorted(
        (
            grid for grid in _prefetched(catalog, "size_grids")
            if _usable_grid(grid) is not None
        ),
        key=lambda grid: (grid.order, grid.name, grid.id),
    )
    if not grids:
        return None
    exact = []
    neutral = []
    for grid in grids:
        try:
            profile_key = str(grid.fable5_profile.option_key or "")
        except Exception:
            profile_key = ""
        if profile_key == option_key:
            exact.append(grid)
        elif not profile_key:
            neutral.append(grid)
    return (exact or neutral or grids)[0]


def _configuration_sizes(product, variant, row) -> tuple[str, ...]:
    option_key = str(row.get("option_key") or "")
    fit_code = str(row.get("fit_code") or "")
    product_assignments = {
        assignment.option_key: assignment
        for assignment in _prefetched(product, "fable5_size_grid_assignments")
    }
    variant_assignments = {
        assignment.option_key: assignment
        for assignment in _prefetched(variant, "fable5_size_grid_assignments")
    }
    variant_assignment = variant_assignments.get(option_key)
    product_assignment = product_assignments.get(option_key)
    explicit_variant_grid = variant_assignment is not None
    grid = _usable_grid(
        variant_assignment.size_grid
        if variant_assignment is not None
        else product_assignment.size_grid
        if product_assignment is not None
        else _fallback_grid(product, option_key)
    )
    sizes = _grid_sizes(grid)
    catalog_sizes = _catalog_sizes(product)
    if sizes and catalog_sizes and not explicit_variant_grid:
        sizes = [size for size in catalog_sizes if size in sizes]
    elif not sizes:
        sizes = catalog_sizes

    product_rules = {
        (rule.option_key, normalize_size_value(rule.size)): rule
        for rule in _prefetched(product, "fable5_size_rules")
    }
    variant_rules = {
        (rule.fit_code, normalize_size_value(rule.size)): rule
        for rule in _prefetched(variant, "fable5_size_rules")
    }
    resolved = []
    for size in sizes:
        product_rule = product_rules.get((option_key, size))
        if product_rule is not None and not product_rule.is_enabled:
            continue
        variant_rule = (
            variant_rules.get((fit_code, size))
            or variant_rules.get(("", size))
        )
        if variant_rule is not None and (
            not variant_rule.is_enabled
            or (variant_rule.stock is not None and variant_rule.stock <= 0)
        ):
            continue
        resolved.append(size)
    return tuple(resolved)


def _price_snapshot(product, variants_by_id, value: dict) -> PriceSnapshot:
    configurations = tuple(
        PricingConfiguration(
            variant_id=(int(row["variant_id"]) if row.get("variant_id") is not None else None),
            color_id=(int(row["color_id"]) if row.get("color_id") is not None else None),
            color_slug=str(row.get("color_slug") or ""),
            color_label=str(row.get("color") or ""),
            fit_code=str(row.get("fit_code") or ""),
            option_values={
                str(key): str(option_value)
                for key, option_value in sorted((row.get("option_values") or {}).items())
            },
            compatible_sizes=_configuration_sizes(
                product,
                variants_by_id[int(row["variant_id"])],
                row,
            ) if row.get("variant_id") is not None else (),
            price=Decimal(str(row["price"])),
            reason=str(row.get("price_reason") or ""),
            is_thermo=bool(row.get("is_thermo")),
        )
        for row in value.get("configurations", ())
    )
    return PriceSnapshot(
        configurations=configurations,
        minimum=(Decimal(str(value["minimum"])) if value.get("minimum") is not None else None),
        maximum=(Decimal(str(value["maximum"])) if value.get("maximum") is not None else None),
        exact=bool(value.get("exact")),
        display=str(value.get("display") or ""),
    )


def pricing_payload(pricing: PriceSnapshot) -> dict:
    return {
        "configurations": [
            {
                "variant_id": row.variant_id,
                "color_id": row.color_id,
                "color_slug": row.color_slug,
                "color_label": row.color_label,
                "fit_code": row.fit_code,
                "option_values": dict(row.option_values),
                "compatible_sizes": list(row.compatible_sizes),
                "price": _money_json(row.price),
                "reason": row.reason,
                "is_thermo": row.is_thermo,
            }
            for row in pricing.configurations
        ],
        "minimum": _money_json(pricing.minimum),
        "maximum": _money_json(pricing.maximum),
        "exact": pricing.exact,
        "display": pricing.display,
    }


def product_payload(item: CatalogProduct) -> dict:
    return {
        "product_id": item.product_id,
        "slug": item.slug,
        "title": item.title,
        "category": {
            "id": item.category_id,
            "slug": item.category_slug,
            "label": item.category_label,
        },
        "garment_type": item.garment_type,
        "catalog_priority": item.catalog_priority,
        "aliases": {key: list(value) for key, value in item.aliases.items()},
        "traits": dict(item.traits),
        "semantic_revision_id": item.semantic_revision_id,
        "variants": [
            {
                "id": row.variant_id,
                "color_id": row.color_id,
                "color_slug": row.color_slug,
                "color_label": row.color_label,
                "sku": row.sku,
            }
            for row in item.variants
        ],
        "fits": [
            {"code": row.code, "label": row.label}
            for row in item.fits
        ],
        "pricing": pricing_payload(item.pricing),
    }


def _effective_revision(product):
    try:
        revision = product.sales_semantic_profile.effective_revision
    except Product.sales_semantic_profile.RelatedObjectDoesNotExist:
        return None
    if revision is None:
        return None
    if revision.status != ProductSalesSemanticProfileRevision.Status.VERIFIED:
        return None
    if revision.profile_id != product.sales_semantic_profile.pk:
        return None
    if revision.source == ProductSalesSemanticProfileRevision.Source.BOT_VISION:
        return None
    return revision


def build_catalog_graph(*, product_ids=None) -> CatalogGraph:
    product_filter = {"status": ProductStatus.PUBLISHED}
    if product_ids is not None:
        product_filter["pk__in"] = tuple(int(value) for value in product_ids)
    products = list(
        Product.objects.filter(**product_filter)
        .select_related(
            "catalog",
            "category",
            "sales_semantic_profile__effective_revision",
            "size_grid",
        )
        .order_by("pk")
    )
    variants = list(
        ProductColorVariant.objects.filter(product_id__in=[row.pk for row in products])
        .select_related("color")
        .order_by("product_id", "order", "pk")
    )
    prepare_pricing_context(products, variants)
    variants_by_product: dict[int, list[ProductColorVariant]] = {}
    for variant in variants:
        variants_by_product.setdefault(variant.product_id, []).append(variant)
    variants_by_id = {variant.pk: variant for variant in variants}

    graph_products = []
    for product in products:
        product_variants = variants_by_product.get(product.pk, [])
        revision = _effective_revision(product)
        raw_pricing = resolve_product_pricing(
            product,
            variants=product_variants,
            context_prepared=True,
        )
        graph_products.append(CatalogProduct(
            product_id=int(product.pk),
            slug=str(product.slug),
            title=str(product.title),
            category_id=int(product.category_id),
            category_slug=str(getattr(product.category, "slug", "") or ""),
            category_label=str(getattr(product.category, "name", "") or ""),
            garment_type=_GARMENT_TYPES_BY_CATEGORY.get(
                str(getattr(product.category, "slug", "") or "").strip().lower(),
                "",
            ),
            catalog_priority=int(product.priority or 0),
            aliases=_aliases(revision.aliases) if revision else {},
            traits=dict(sorted((revision.traits or {}).items())) if revision else {},
            semantic_revision_id=int(revision.pk) if revision else None,
            variants=tuple(
                CatalogVariant(
                    variant_id=int(variant.pk),
                    color_id=int(variant.color_id),
                    color_slug=str(variant.slug or ""),
                    color_label=str(getattr(variant.color, "name", "") or ""),
                    sku=str(variant.sku or ""),
                )
                for variant in product_variants
            ),
            fits=tuple(
                CatalogFit(code=str(option.code), label=str(option.label))
                for option in product.fit_options.all()
                if option.is_active
            ),
            pricing=_price_snapshot(product, variants_by_id, raw_pricing),
        ))

    immutable_products = tuple(graph_products)
    canonical_json = json.dumps(
        [product_payload(item) for item in immutable_products],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return CatalogGraph(
        products=immutable_products,
        digest=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
        canonical_json=canonical_json,
    )
