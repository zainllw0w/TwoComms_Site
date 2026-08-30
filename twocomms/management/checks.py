"""Deployment checks for security-critical Instagram bot configuration."""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security)
def private_instagram_media_check(app_configs=None, **_kwargs):
    del app_configs
    configured = str(getattr(settings, "IG_PRIVATE_MEDIA_ROOT", "") or "").strip()
    if not configured and bool(getattr(settings, "DEBUG", False)):
        return []
    if not configured:
        return [Error(
            "IG_PRIVATE_MEDIA_ROOT is required in production.",
            hint=(
                "Provision an absolute worker-owned 0700 directory outside "
                "MEDIA_ROOT and the checkout."
            ),
            id="management.E901",
        )]
    try:
        from management.services.ig_private_media import validate_private_root

        validate_private_root(require_exists=True)
    except Exception as exc:
        return [Error(
            f"IG private media storage is unsafe: {type(exc).__name__}.",
            hint=(
                "Use a canonical, non-symlink, euid-owned 0700 directory outside "
                "MEDIA_ROOT and the checkout."
            ),
            id="management.E902",
        )]
    return []


@register(Tags.compatibility)
def gemini_accounting_shadow_check(app_configs=None, **_kwargs):
    """Validate the reversible S3b gate without touching accounting tables."""
    del app_configs
    from management.services.gemini_accounting_runtime import (
        is_pacific_midnight,
        parse_effective_from,
    )

    mode = str(
        getattr(settings, "GEMINI_ACCOUNTING_V2_MODE", "off") or "off"
    ).strip().casefold()
    if mode not in {"off", "shadow"}:
        return [Error(
            "GEMINI_ACCOUNTING_V2_MODE must be 'off' or 'shadow'.",
            hint="Use off for rollback; enforcement modes are not part of S3b.",
            id="management.E910",
        )]
    if mode == "off":
        return []

    effective = parse_effective_from(
        getattr(settings, "GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM", "")
    )
    if not is_pacific_midnight(effective):
        return [Error(
            "Gemini shadow accounting requires an aware Pacific-midnight effective timestamp.",
            hint=(
                "Set GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM to an ISO timestamp "
                "whose America/Los_Angeles local time is exactly 00:00:00."
            ),
            id="management.E911",
        )]

    from management.services import gemini_keys

    configured = [
        alias for alias in gemini_keys.ALL_KEYS if gemini_keys._key_value(alias)
    ]
    identities = [gemini_keys.project_group(alias) for alias in configured]
    errors = []
    if any(not identity for identity in identities):
        errors.append(Error(
            "Every configured Gemini alias needs a stable project identity.",
            id="management.E912",
        ))
    if len(set(identities)) != len(identities):
        errors.append(Error(
            "Configured Gemini aliases contain duplicate project identities.",
            hint="Shadow accounting requires one explicit identity per independent project.",
            id="management.E913",
        ))
    values = [gemini_keys._key_value(alias) for alias in configured]
    if len(set(values)) != len(values):
        errors.append(Warning(
            "Configured Gemini aliases contain duplicate credentials.",
            hint=(
                "Shadow remains observational, but enforcement must not be enabled "
                "until credential/project mapping is corrected."
            ),
            id="management.W914",
        ))
    return errors
