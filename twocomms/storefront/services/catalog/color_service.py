"""
Colour management helpers: normalisation and deduplication logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from django.db import transaction
from django.db.models import Q

from productcolors.models import Color, ProductColorVariant

HEX_RE = re.compile(r"^[0-9A-F]{6}$")


@dataclass
class ColorDeduplicationResult:
    """
    Outcome of `ensure_color_identity`.

    Attributes:
        color: Canonical colour instance after processing.
        created: True when a brand-new colour row was created.
        updated: True when canonical colour fields were changed.
        merged_ids: IDs of duplicate colours that were merged into canonical.
    """

    color: Color
    created: bool
    updated: bool
    merged_ids: List[int]

    def any_changes(self) -> bool:
        """Convenience flag to check if anything was altered."""
        return self.created or self.updated or bool(self.merged_ids)


def normalize_hex_code(raw: Optional[str]) -> Optional[str]:
    """
    Normalise HEX values to the `#RRGGBB` format.

    Accepts values with/without leading '#', ignores whitespace, and returns
    ``None`` for empty inputs. Raises ValueError for invalid hex strings.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.startswith("#"):
        value = value[1:]
    if not HEX_RE.fullmatch(value.upper()):
        raise ValueError(f"Invalid HEX colour value: {raw!r}")
    return f"#{value.upper()}"


def _duplicate_filter(primary_hex: str, secondary_hex: Optional[str]) -> Q:
    """
    Build a queryset filter that matches colours equivalent to the provided HEX.
    """
    base = Q(primary_hex__iexact=primary_hex)
    if secondary_hex:
        return base & Q(secondary_hex__iexact=secondary_hex)
    return base & (Q(secondary_hex__isnull=True) | Q(secondary_hex=""))


def _collect_equivalent_colors(canonical: Color) -> List[Color]:
    """
    Return duplicates (excluding canonical) that match the same HEX pair.
    """
    secondary = canonical.secondary_hex or None
    candidates = (
        Color.objects.filter(_duplicate_filter(canonical.primary_hex, secondary))
        .exclude(pk=canonical.pk)
        .order_by("pk")
    )
    return list(candidates)


@transaction.atomic
def ensure_color_identity(
    *,
    primary_hex: Optional[str],
    secondary_hex: Optional[str] = None,
    name: Optional[str] = None,
    color: Optional[Color] = None,
) -> ColorDeduplicationResult:
    """
    Normalise colour values, ensure a canonical row exists, and merge duplicates.

    Args:
        primary_hex: Requested primary HEX code.
        secondary_hex: Optional secondary HEX code (for composite colours).
        name: Suggested display name.
        color: Existing colour instance (e.g., from a bound form) that should
            be updated/normalised. If provided, it will be reused when possible.

    Returns:
        ColorDeduplicationResult describing the final canonical colour.
    """
    if color and not color.pk:
        color = None  # we only care about persisted colours

    normalized_primary = normalize_hex_code(primary_hex) or (
        normalize_hex_code(color.primary_hex) if color else None
    )
    normalized_secondary = normalize_hex_code(secondary_hex) if secondary_hex else None

    if not normalized_primary:
        raise ValueError("Primary HEX is required to ensure colour identity.")

    # Search for an existing canonical colour (case-insensitive + NULL/blank).
    duplicates_q = Color.objects.filter(
        _duplicate_filter(normalized_primary, normalized_secondary)
    ).order_by("pk")
    canonical = duplicates_q.first()

    created = False
    updated = False

    if canonical is None and color is not None:
        canonical = color
    elif canonical is None:
        canonical = Color()
        created = True

    if canonical.primary_hex != normalized_primary or canonical.secondary_hex != normalized_secondary:
        canonical.primary_hex = normalized_primary
        canonical.secondary_hex = normalized_secondary
        updated = True

    # Prefer non-empty name, but do not override explicit existing names unless provided.
    if name:
        trimmed = name.strip()
        if trimmed and canonical.name != trimmed:
            canonical.name = trimmed
            updated = True
    elif not canonical.name:
        canonical.name = normalized_primary
        updated = True

    canonical.save()

    merged_ids: List[int] = []
    # Merge other duplicates into canonical.
    for duplicate in _collect_equivalent_colors(canonical):
        ProductColorVariant.objects.filter(color=duplicate).update(color=canonical)
        merged_ids.append(duplicate.pk)
        duplicate.delete()

    # If an external colour instance was supplied and is not canonical, merge it as well.
    if color and canonical.pk != color.pk:
        ProductColorVariant.objects.filter(color=color).update(color=canonical)
        if color.pk not in merged_ids:
            merged_ids.append(color.pk)
        color.delete()

    return ColorDeduplicationResult(
        color=canonical,
        created=created,
        updated=updated,
        merged_ids=merged_ids,
    )

