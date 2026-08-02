"""Deterministic product filtering and explainable candidate ranking."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from .ig_commerce_types import (
    CandidateDecision,
    CatalogCandidate,
    CatalogGraph,
    CatalogProduct,
    CommerceTurnRequest,
)


_COLOR_FORMS = {
    "чорний": "black", "чорна": "black", "черный": "black", "черная": "black",
    "білий": "white", "біла": "white", "белый": "white", "белая": "white",
    "синій": "blue", "синя": "blue", "синий": "blue", "синяя": "blue",
    "рожевий": "pink", "рожева": "pink", "розовый": "pink", "розовая": "pink",
    "сірий": "grey", "сіра": "grey", "серый": "grey", "серая": "grey",
    "зелений": "green", "зелена": "green", "зеленый": "green", "зеленая": "green",
}
_FIT_FORMS = {
    "класика": "classic", "класична": "classic", "классика": "classic",
    "классическая": "classic", "класичний": "classic", "classic": "classic",
    "стандарт": "classic", "standard": "classic", "regular": "classic",
    "оверсайз": "oversize", "oversized": "oversize", "oversize": "oversize",
}


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _canonical(value: str) -> str:
    value = _norm(value)
    return _COLOR_FORMS.get(value, _FIT_FORMS.get(value, value))


def _request_constraints(request: CommerceTurnRequest) -> dict[str, str]:
    constraints: dict[str, str] = {}
    for source in (request.hard, request.field_updates, request.semantic_constraints):
        for key, value in (source or {}).items():
            if value is not None and str(value).strip():
                constraints[str(key)] = _canonical(value)
    if request.garment_type:
        constraints["garment_type"] = _canonical(request.garment_type)
    return constraints


def _variant_colors(product: CatalogProduct) -> set[str]:
    values = set()
    for variant in product.variants:
        values.add(_canonical(variant.get("slug", "")))
        values.add(_canonical(variant.get("color", "")))
    return {value for value in values if value}


def _fits(product: CatalogProduct) -> set[str]:
    return {_canonical(item.get("code", "")) for item in product.fits if item.get("active", True)}


def _alias_match(product: CatalogProduct, request: CommerceTurnRequest) -> bool:
    aliases = {
        _norm(alias)
        for values in (product.aliases or {}).values()
        for alias in values
    }
    title = _norm(product.title)
    requested = {_norm(value) for value in (request.field_updates or {}).values() if value}
    requested.update(_norm(value) for value in (request.preferences or {}).values() if value)
    return bool(aliases & requested) or title in requested


def _matches_constraint(product: CatalogProduct, key: str, expected: str) -> bool:
    expected = _canonical(expected)
    if key in {"color", "colour"}:
        return expected in _variant_colors(product)
    if key in {"fit", "cut", "style"}:
        return expected in _fits(product)
    if key in {"garment_type", "category"}:
        haystack = {_canonical(product.category), _canonical(product.slug), _canonical(product.title)}
        return expected in haystack or any(expected in value for value in haystack)
    if key in {"size", "size_code"}:
        # Size allocation belongs to the availability layer.  A catalog
        # candidate remains configurable until that exact size is checked.
        return True
    return _canonical(product.traits.get(key, "")) == expected


def _candidate(product: CatalogProduct, *, matched: int, exact_alias: bool, exact_product: bool, reasons: Iterable[str]) -> CatalogCandidate:
    score = (1 if exact_product else 0, 1 if exact_alias else 0, matched, -int(product.product_id))
    return CatalogCandidate(
        product_id=product.product_id,
        slug=product.slug,
        title=product.title,
        price=product.price,
        category=product.category,
        traits=dict(product.traits),
        score=score,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _question(candidates: tuple[CatalogCandidate, ...], constraints: Mapping[str, str]) -> str:
    if not candidates:
        return "Уточните, пожалуйста, другую модель, цвет или фасон."
    if len(candidates) == 1:
        return ""
    if "color" not in constraints and "colour" not in constraints:
        return "Какой цвет выбрать?"
    if "fit" not in constraints:
        return "Выбрать классическую посадку или оверсайз?"
    return "Какой из вариантов вам подходит?"


def rank_candidates(
    graph: CatalogGraph,
    request: CommerceTurnRequest,
    availability=None,
) -> CandidateDecision:
    """Return at most three hard-compatible, stably ordered candidates.

    ``availability`` is intentionally an optional filter hook.  It may mark a
    candidate configurable/allocatable later, but it cannot reintroduce a
    product rejected by a mandatory identity or semantic constraint.
    """
    constraints = _request_constraints(request)
    exact_id = request.exact_product_id
    rows: list[CatalogCandidate] = []
    for product in graph.products:
        if exact_id is not None and product.product_id != int(exact_id):
            continue
        failed = [
            key for key, expected in constraints.items()
            if not _matches_constraint(product, key, expected)
        ]
        if failed:
            continue
        if availability is not None:
            verdict = availability(product)
            if verdict in {False, "unavailable", "unknown"}:
                continue
        exact_alias = _alias_match(product, request)
        matched = len(constraints)
        reasons = [f"matched:{key}" for key in sorted(constraints)]
        if exact_alias:
            reasons.append("verified_alias_or_title")
        if exact_id is not None:
            reasons.append("trusted_exact_reference")
        rows.append(
            _candidate(
                product,
                matched=matched,
                exact_alias=exact_alias,
                exact_product=exact_id is not None,
                reasons=reasons,
            )
        )
    rows.sort(key=lambda item: item.score, reverse=True)
    visible = tuple(rows[:3])
    unique_alias = bool(request.exact_unique_alias and len(rows) == 1)
    auto = bool(rows) and (
        exact_id is not None or unique_alias or len(rows) == 1
    )
    selected = visible[0].product_id if auto else None
    return CandidateDecision(
        candidates=visible,
        auto_select=auto,
        selected_product_id=selected,
        pending_question=_question(visible, constraints) if not auto else "",
    )
