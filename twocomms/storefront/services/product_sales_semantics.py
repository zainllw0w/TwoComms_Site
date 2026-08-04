import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max


SUPPORTED_ALIAS_LOCALES = frozenset({"uk", "ru", "en"})

CONTROLLED_TRAITS = {
    "design_family": frozenset({"plain", "plain_logo", "graphic", "collection"}),
    "front_decoration": frozenset({"none", "logo", "print"}),
    "back_decoration": frozenset({"none", "logo", "print"}),
    "hem_construction": frozenset({"standard", "elastic"}),
}

ALLOWED_SOURCES = frozenset({
    "manager",
    "structured_catalog",
    "structured_print_link",
    "migration",
    "bot_vision",
    "free_text",
    "generated_description",
})

NON_AUTHORITATIVE_SOURCES = frozenset({
    "bot_vision",
    "free_text",
    "generated_description",
})

ALLOWED_STATUSES = frozenset({"draft", "verified", "revoked"})

GENERIC_COMMERCE_ALIASES = frozenset({
    # Fits.
    "classic", "classical", "regular", "standard", "oversize", "oversized",
    "класика", "класична", "класичний", "оверсайз",
    "классика", "классическая", "классический",
    # Garment types.
    "t-shirt", "tshirt", "tee", "shirt", "hoodie", "sweatshirt",
    "longsleeve", "long-sleeve", "футболка", "майка", "худі", "худи",
    "світшот", "свитшот", "лонгслів", "лонгслив",
    # Decoration and construction terms are constraints, not product names.
    "logo", "print", "plain", "blank", "elastic", "ribbed", "hem", "cuff",
    "лого", "логотип", "логотипом", "принт", "принтом", "еластичний",
    "еластична", "резинка", "манжет", "эластичный", "эластичная",
    # Controlled colors and their common Ukrainian/Russian adjective forms.
    "black", "white", "red", "blue", "green", "grey", "gray", "yellow",
    "pink", "purple", "orange", "beige", "brown",
    "чорний", "чорна", "чорне", "білий", "біла", "біле", "червоний",
    "червона", "синій", "синя", "зелений", "зелена", "сірий", "сіра",
    "жовтий", "жовта", "рожевий", "рожева", "фіолетовий", "фіолетова",
    "помаранчевий", "помаранчева", "бежевий", "бежева", "коричневий",
    "коричнева", "черный", "черная", "черное", "белый", "белая", "белое",
    "красный", "красная", "синий", "синяя", "зеленый", "зеленая",
    "серый", "серая", "желтый", "желтая", "розовый", "розовая",
    "фиолетовый", "фиолетовая", "оранжевый", "оранжевая", "бежевый",
    "бежевая", "коричневый", "коричневая",
    # Standard apparel sizes.
    "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl", "2xl", "3xl",
    "4xl", "5xl", "onesize", "one-size", "one size", "one", "size",
})

GENERIC_ALIAS_CONNECTORS = frozenset({
    "and", "with", "without", "і", "й", "та", "з", "із", "зі",
    "и", "с", "со", "без",
})


def normalize_aliases(aliases):
    if not isinstance(aliases, dict):
        raise ValidationError({"aliases": "Aliases must be a locale-to-list mapping."})

    normalized = {}
    for locale, values in aliases.items():
        normalized_locale = str(locale).strip().lower()
        if normalized_locale not in SUPPORTED_ALIAS_LOCALES:
            raise ValidationError({"aliases": f"Unsupported alias locale: {locale}."})
        if not isinstance(values, list):
            raise ValidationError({"aliases": f"Aliases for {normalized_locale} must be a list."})

        locale_aliases = []
        seen = set()
        for value in values:
            if not isinstance(value, str):
                raise ValidationError({"aliases": "Every alias must be a string."})
            alias = re.sub(r"\s+", " ", value.strip()).casefold()
            if not alias:
                raise ValidationError({"aliases": "Aliases cannot be empty."})
            if alias not in seen:
                locale_aliases.append(alias)
                seen.add(alias)
        normalized[normalized_locale] = locale_aliases
    return normalized


def normalize_traits(traits):
    if not isinstance(traits, dict):
        raise ValidationError({"traits": "Traits must be a key-to-code mapping."})

    normalized = {}
    for key, value in traits.items():
        if key not in CONTROLLED_TRAITS:
            raise ValidationError({"traits": f"Unsupported semantic trait: {key}."})
        if not isinstance(value, str):
            raise ValidationError({"traits": f"Trait {key} must use a string code."})
        code = value.strip().lower()
        if code not in CONTROLLED_TRAITS[key]:
            raise ValidationError({"traits": f"Unsupported code for {key}: {value}."})
        normalized[key] = code
    return normalized


def validate_verified_aliases(aliases):
    for locale, values in aliases.items():
        for alias in values:
            tokens = [
                token.casefold()
                for token in re.findall(r"[^\W_]+(?:-[^\W_]+)*", alias)
            ]
            identity_tokens = [
                token for token in tokens if token not in GENERIC_ALIAS_CONNECTORS
            ]
            if not identity_tokens:
                raise ValidationError({
                    "aliases": (
                        f"Verified alias '{alias}' ({locale}) has no product identity token."
                    )
                })
            is_generic_only = all(
                token in GENERIC_COMMERCE_ALIASES for token in identity_tokens
            )
            if alias in GENERIC_COMMERCE_ALIASES or is_generic_only:
                raise ValidationError({
                    "aliases": (
                        f"Verified alias '{alias}' ({locale}) is generic commerce vocabulary, "
                        "not an exact product identity."
                    )
                })


def validate_semantic_revision(
    *,
    status,
    source,
    aliases=None,
    traits=None,
    verified_by=None,
    verified_at=None,
):
    if status not in ALLOWED_STATUSES:
        raise ValidationError({"status": "Unsupported semantic revision status."})
    if source not in ALLOWED_SOURCES:
        raise ValidationError({"source": "Unsupported semantic revision source."})
    normalized_aliases = normalize_aliases({} if aliases is None else aliases)
    normalized_traits = normalize_traits({} if traits is None else traits)
    if status == "verified":
        if source in NON_AUTHORITATIVE_SOURCES:
            raise ValidationError({"source": "Non-authoritative suggestions cannot be verified."})
        if verified_by is None or verified_at is None:
            raise ValidationError(
                "Verified semantic revisions require a verifier and verification time."
            )
        validate_verified_aliases(normalized_aliases)

    return {
        "aliases": normalized_aliases,
        "traits": normalized_traits,
    }


def get_effective_verified_revision(profile):
    from storefront.models import (
        ProductSalesSemanticProfile,
        ProductSalesSemanticProfileRevision,
    )

    effective_revision_id = ProductSalesSemanticProfile.objects.filter(
        pk=profile.pk
    ).values_list("effective_revision_id", flat=True).first()
    if effective_revision_id is None:
        return None
    return ProductSalesSemanticProfileRevision.objects.filter(
        pk=effective_revision_id,
        profile_id=profile.pk,
        status=ProductSalesSemanticProfileRevision.Status.VERIFIED,
    ).first()


@transaction.atomic
def create_semantic_revision(
    *,
    profile,
    status,
    source,
    aliases=None,
    traits=None,
    schema_version=1,
    supersedes=None,
    verified_by=None,
    verified_at=None,
):
    from storefront.models import (
        ProductSalesSemanticProfile,
        ProductSalesSemanticProfileRevision,
    )

    locked_profile = ProductSalesSemanticProfile.objects.select_for_update().get(pk=profile.pk)
    current_effective_id = locked_profile.effective_revision_id
    supersedes_id = getattr(supersedes, "pk", None)
    if supersedes_id is not None and supersedes.profile_id != locked_profile.pk:
        raise ValidationError({"supersedes": "A revision cannot supersede another profile."})
    if status == ProductSalesSemanticProfileRevision.Status.DRAFT:
        if supersedes_id is not None:
            raise ValidationError({"supersedes": "Draft revisions cannot supersede commerce truth."})
    elif status == ProductSalesSemanticProfileRevision.Status.VERIFIED:
        if supersedes is None and current_effective_id is not None:
            supersedes = locked_profile.effective_revision
            supersedes_id = current_effective_id
        if supersedes_id != current_effective_id:
            raise ValidationError({
                "supersedes": "A verified revision must supersede the current effective revision."
            })
    elif status == ProductSalesSemanticProfileRevision.Status.REVOKED:
        if supersedes_id is None or supersedes_id != current_effective_id:
            raise ValidationError({
                "supersedes": "A revocation must target the current effective revision."
            })
    next_revision = (
        locked_profile.revisions.aggregate(max_revision=Max("revision"))["max_revision"] or 0
    ) + 1
    return ProductSalesSemanticProfileRevision.objects.create(
        profile=locked_profile,
        revision=next_revision,
        status=status,
        schema_version=schema_version,
        supersedes=supersedes,
        aliases={} if aliases is None else aliases,
        traits={} if traits is None else traits,
        source=source,
        verified_by=verified_by,
        verified_at=verified_at,
    )
