"""Typed, single-query resolution of an Instagram advertising referral."""

from dataclasses import dataclass

from django.db.models import Q


@dataclass(frozen=True)
class AdReferralResolution:
    status: str
    reason_codes: tuple[str, ...] = ()
    campaign: object | None = None

    @property
    def product_id(self) -> int | None:
        raw = getattr(self.campaign, "product_id", None)
        return int(raw) if raw else None


def resolve_ad_referral(client) -> AdReferralResolution:
    """Resolve once, detecting duplicate/conflicting active mappings.

    ``resolved`` means one authoritative active mapping with a usable product
    or theme. ``ambiguous`` is durable business ambiguity, while
    ``unavailable`` means there is no mapping or the resolver could not prove
    one. Callers can therefore degrade safely without treating an exception as
    a successful catalog match.
    """
    ad_id = str(getattr(client, "ad_id", "") or "").strip()
    ref = str(getattr(client, "ad_ref", "") or "").strip()
    if not ad_id and not ref:
        return AdReferralResolution("unavailable", ("referral_absent",))

    from management.models import BotAdCampaign

    query = Q()
    if ad_id:
        query |= Q(ad_id=ad_id)
    if ref:
        query |= Q(ref=ref)
    try:
        matches = list(
            BotAdCampaign.objects.filter(query, is_active=True)
            .select_related("product")
            .order_by("id")[:3]
        )
    except Exception:
        return AdReferralResolution("unavailable", ("resolver_unavailable",))
    if not matches:
        return AdReferralResolution("unavailable", ("mapping_missing",))
    if len(matches) > 1:
        return AdReferralResolution("ambiguous", ("duplicate_active_mapping",))

    campaign = matches[0]
    if campaign.product_id:
        from storefront.models import ProductStatus

        if campaign.product.status != ProductStatus.PUBLISHED:
            return AdReferralResolution(
                "unavailable",
                ("mapped_product_unpublished",),
                campaign,
            )
    elif not str(campaign.theme or "").strip():
        return AdReferralResolution(
            "unavailable",
            ("mapping_has_no_target",),
            campaign,
        )
    return AdReferralResolution("resolved", ("mapping_resolved",), campaign)
