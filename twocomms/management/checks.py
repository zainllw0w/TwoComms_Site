"""Deployment checks for security-critical Instagram bot configuration."""

from django.conf import settings
from django.core.checks import Error, Tags, register


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
