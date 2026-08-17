"""Test-only fixtures for the strict call auto-analysis runtime contract."""

from management.models import InstagramBotSettings
from management.services.call_auto_analysis import (
    publish_call_auto_analysis_marker,
    remove_call_auto_analysis_marker,
)


def enable_call_auto_analysis(test_case) -> InstagramBotSettings:
    """Enable both durable state layers and clean up the filesystem projection."""
    settings_obj = InstagramBotSettings.load()
    settings_obj.call_auto_analysis_enabled = True
    settings_obj.save(update_fields=["call_auto_analysis_enabled", "updated_at"])
    publish_call_auto_analysis_marker()
    test_case.addCleanup(remove_call_auto_analysis_marker)
    return settings_obj


def disable_call_auto_analysis(test_case) -> None:
    """Ensure each OFF scenario begins without a left-over marker."""
    remove_call_auto_analysis_marker()
    InstagramBotSettings.objects.filter(pk=1).update(call_auto_analysis_enabled=False)
    test_case.addCleanup(remove_call_auto_analysis_marker)
