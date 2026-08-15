from django.db import migrations, models


def backfill_reward_evidence_snapshots(apps, schema_editor):
    Reward = apps.get_model("management", "IgUgcReward")
    for reward in (
        Reward.objects.exclude(assessment_id=None)
        .select_related("assessment")
        .iterator(chunk_size=500)
    ):
        assessment = reward.assessment
        reward.assessment_generation_snapshot = assessment.generation
        reward.policy_version_snapshot = assessment.policy_version
        reward.provider_object_digest_snapshot = assessment.provider_object_digest or ""
        reward.catalog_candidates_snapshot = list(assessment.catalog_candidates or [])
        reward.save(update_fields=[
            "assessment_generation_snapshot",
            "policy_version_snapshot",
            "provider_object_digest_snapshot",
            "catalog_candidates_snapshot",
        ])


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0162_ig_follow_cta_refusal"),
    ]

    operations = [
        migrations.AddField(
            model_name="igugcreward",
            name="assessment_generation_snapshot",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="policy_version_snapshot",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="provider_object_digest_snapshot",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="catalog_candidates_snapshot",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            backfill_reward_evidence_snapshots,
            migrations.RunPython.noop,
        ),
    ]
