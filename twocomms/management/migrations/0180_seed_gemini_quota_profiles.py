import datetime

from django.db import migrations


PROFILE_VERSION = "owner-observed-2026-08-29.v1"
PROFILE_MODELS = (
    ("gemini-3.7-flash", 5, 250_000, 20, 1),
    ("gemini-3.6-flash", 5, 250_000, 20, 1),
    ("gemini-3.5-flash", 5, 250_000, 20, 1),
    ("gemini-3.5-flash-lite", 15, 250_000, 500, 2),
)
PROFILE_VALUE_FIELDS = (
    "rpm_limit",
    "input_tpm_limit",
    "rpd_limit",
    "permit_limit",
    "estimator_version",
    "source",
    "source_reference",
    "observed_at",
    "effective_from",
    "effective_until",
)


def seed_owner_observed_profiles(apps, schema_editor):
    """Retry-idempotent seed with fail-closed profile drift detection."""
    profile_model = apps.get_model("management", "GeminiQuotaProfile")
    observed_at = datetime.datetime(
        2026, 8, 29, 17, 18, 56, tzinfo=datetime.timezone.utc
    )
    for model, rpm, input_tpm, rpd, permits in PROFILE_MODELS:
        expected = {
            "rpm_limit": rpm,
            "input_tpm_limit": input_tpm,
            "rpd_limit": rpd,
            "permit_limit": permits,
            "estimator_version": "shadow-calibration-required",
            "source": "owner_observed",
            "source_reference": "owner_ai_studio_screenshot",
            "observed_at": observed_at,
            "effective_from": observed_at,
            "effective_until": None,
        }
        row, created = profile_model.objects.get_or_create(
            profile_version=PROFILE_VERSION,
            model=model,
            defaults=expected,
        )
        if created:
            continue
        drift = {
            field: {"expected": expected[field], "actual": getattr(row, field)}
            for field in PROFILE_VALUE_FIELDS
            if getattr(row, field) != expected[field]
        }
        if drift:
            fields = ", ".join(sorted(drift))
            raise RuntimeError(
                f"Gemini quota profile drift for {PROFILE_VERSION}/{model}: {fields}"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0179_gemini_accounting_v2_schema"),
    ]

    operations = [
        migrations.RunPython(
            seed_owner_observed_profiles,
            migrations.RunPython.noop,
        ),
    ]
