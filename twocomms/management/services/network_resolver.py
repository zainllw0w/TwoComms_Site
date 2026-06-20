"""Детермінований резолвер мереж лідів.

Консолідація, НЕ паралельна система: переви використовує наявні ключі матчингу
ManagementLead (normalized_name_match_key / website_match_key / phone_last7),
додаючи лише транслітераційну нормалізацію (arber/арбер) і generic-детект.
"""
from __future__ import annotations

from collections import defaultdict

from django.db import transaction
from django.utils.text import slugify

from management.models import (
    LeadNetwork,
    ManagementLead,
    NetworkAlias,
    normalize_name_for_match,
    normalize_website_for_match,
)

# укр/рос → лат транслітерація для злиття латиниці/кирилиці одного бренду.
_UA_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "",
    "ю": "iu", "я": "ia", "’": "", "ʼ": "", "'": "",
    "ё": "e", "ъ": "", "ы": "y", "э": "e",
}

GENERIC_NAME_TOKENS = {
    "військторг", "воєнторг", "воєнторґ", "магазин", "секонд", "секонд хенд",
    "одяг", "взуття", "маркет", "базар", "лавка", "крамниця", "спецодяг",
    "army shop", "military shop", "тактичний магазин", "військовий магазин",
}


def _translit(value: str) -> str:
    return "".join(_UA_LAT.get(ch, ch) for ch in value)


def network_match_key(name: str) -> str:
    """Канонічний ключ для злиття латиниці/кирилиці одного бренду.
    Базується на наявному normalize_name_for_match + транслітерація."""
    base = normalize_name_for_match(name)
    return _translit(base).replace(" ", "")


def is_generic_name(name: str) -> bool:
    """Родова назва (військторг, магазин тощо) — НЕ зливаємо в єдину мережу."""
    return normalize_name_for_match(name) in GENERIC_NAME_TOKENS


# джерела привʼязки, які резолвер може перезаписувати (не чіпає ручні/AI рішення)
_AUTO_SOURCES = ("", "auto")


def classify_cluster(leads: list) -> str:
    """standalone | generic | network. Generic (родова назва) НЕ зливаємо."""
    if any(is_generic_name(lead.shop_name) for lead in leads):
        return "generic"
    if len(leads) < 2:
        return "standalone"
    return "network"


def _unique_slug(base: str) -> str:
    base = slugify(base) or "network"
    slug, i = base, 2
    while LeadNetwork.objects.filter(slug=slug).exists():
        slug, i = f"{base}-{i}", i + 1
    return slug


def _detach(lead: ManagementLead) -> None:
    if lead.network_membership_source not in _AUTO_SOURCES:
        return
    if lead.network_id or lead.needs_disambiguation or lead.network_membership_source:
        lead.network = None
        lead.needs_disambiguation = False
        lead.network_membership_source = ""
        lead.save(update_fields=["network", "needs_disambiguation", "network_membership_source", "updated_at"])


def _mark_generic(lead: ManagementLead) -> None:
    if lead.network_membership_source not in _AUTO_SOURCES:
        return
    if lead.network_id or not lead.needs_disambiguation:
        lead.network = None
        lead.needs_disambiguation = True
        lead.network_membership_source = ""
        lead.save(update_fields=["network", "needs_disambiguation", "network_membership_source", "updated_at"])


def _get_or_create_network(name_key: str, leads: list) -> LeadNetwork:
    alias = NetworkAlias.objects.filter(key_type=NetworkAlias.KeyType.NAME, key_value=name_key).select_related("network").first()
    if alias:
        net = alias.network
    else:
        net = LeadNetwork.objects.create(
            canonical_name=leads[0].shop_name,
            slug=_unique_slug(leads[0].shop_name),
            policy=LeadNetwork.Policy.NEEDS_REVIEW,
        )
        NetworkAlias.objects.create(network=net, key_type=NetworkAlias.KeyType.NAME, key_value=name_key, source="auto")
    # website-алиаси (для матчингу нових лідів у Блоці B)
    for lead in leads:
        wkey = normalize_website_for_match(lead.website_url)
        if wkey:
            NetworkAlias.objects.get_or_create(
                key_type=NetworkAlias.KeyType.WEBSITE, key_value=wkey,
                defaults={"network": net, "source": "auto"},
            )
    return net


def resolve_all() -> dict:
    """Idempotent: класифікує всі parser-ліди й привʼязує до мереж.
    Повертає підсумок {standalone, generic, network, networks_total}."""
    stats = {"standalone": 0, "generic": 0, "network": 0}
    clusters: dict[str, list] = defaultdict(list)
    for lead in ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER):
        clusters[network_match_key(lead.shop_name)].append(lead)

    with transaction.atomic():
        for name_key, leads in clusters.items():
            kind = classify_cluster(leads)
            if kind == "standalone":
                stats["standalone"] += 1
                _detach(leads[0])
            elif kind == "generic":
                stats["generic"] += len(leads)
                for lead in leads:
                    _mark_generic(lead)
            else:
                stats["network"] += 1
                net = _get_or_create_network(name_key, leads)
                for lead in leads:
                    if lead.network_membership_source in _AUTO_SOURCES and (lead.network_id != net.id or lead.needs_disambiguation):
                        lead.network = net
                        lead.needs_disambiguation = False
                        lead.network_membership_source = "auto"
                        lead.save(update_fields=["network", "needs_disambiguation", "network_membership_source", "updated_at"])
                net.members_count = net.leads.count()
                net.save(update_fields=["members_count", "updated_at"])
    stats["networks_total"] = LeadNetwork.objects.count()
    return stats
