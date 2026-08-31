import datetime

from django.db import migrations


PROFILE_VERSION = "production-observed-2026-08-31.v2"
ESTIMATOR_VERSION = "json_bytes_div4_v1"
PROFILE_MODELS = (
    (
        "gemini-3.7-flash", 5, 250_000, 20, 1,
        "shadow-calibration-required",
        "owner_limits_2026_08_29;production_prompt_calibration_pending",
    ),
    (
        "gemini-3.6-flash", 5, 250_000, 20, 1,
        ESTIMATOR_VERSION,
        "owner_limits_2026_08_29;prod_ratio_2026_08_31:n15:min1.710:med1.823:max2.376:under0",
    ),
    (
        "gemini-3.5-flash", 5, 250_000, 20, 1,
        "shadow-calibration-required",
        "owner_limits_2026_08_29;production_prompt_calibration_pending",
    ),
    (
        "gemini-3.5-flash-lite", 15, 250_000, 500, 2,
        ESTIMATOR_VERSION,
        "owner_limits_2026_08_29;prod_ratio_2026_08_31:n2:min2.531:med2.600:max2.600:under0",
    ),
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


def seed_calibrated_profiles(apps, schema_editor):
    """Append the first production-calibrated estimator profile set.

    The timestamp is the fixed 2026-08-31 production aggregate boundary, not
    migration execution time.  Re-running a partially applied migration is
    idempotent, while a row with the same immutable identity and different
    policy values fails closed instead of silently rewriting quota history.
    """
    del schema_editor
    profile_model = apps.get_model("management", "GeminiQuotaProfile")
    aggregate_at = datetime.datetime(
        2026, 8, 31, 17, 0, 14, tzinfo=datetime.timezone.utc
    )
    for (
        model, rpm, input_tpm, rpd, permits, estimator, source_reference
    ) in PROFILE_MODELS:
        expected = {
            "rpm_limit": rpm,
            "input_tpm_limit": input_tpm,
            "rpd_limit": rpd,
            "permit_limit": permits,
            "estimator_version": estimator,
            # Limits remain the owner-observed screenshot values; this new
            # immutable version is ADMIN because only the text estimator for
            # 3.6/Lite was calibrated from the production aggregate.
            "source": "admin",
            "source_reference": source_reference,
            "observed_at": aggregate_at,
            "effective_from": aggregate_at,
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
                f"Gemini calibrated quota profile drift for "
                f"{PROFILE_VERSION}/{model}: {fields}"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0185_typed_memory_v2"),
    ]

    operations = [
        migrations.RunPython(
            seed_calibrated_profiles,
            migrations.RunPython.noop,
        ),
    ]
