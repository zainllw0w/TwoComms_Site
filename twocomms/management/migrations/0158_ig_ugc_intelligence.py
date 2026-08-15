import django.db.models.deletion
import django.utils.timezone
import hashlib
import hmac
import re
import unicodedata
from django.conf import settings
from django.db import migrations, models


UGC_TABLES = (
    "management_igugcreward",
    "management_igugcevidenceassessment",
    "management_igugcrewardlifetime",
    "management_igugcrewarddelivery",
)

_IDENTITY_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def _active_identity_key():
    """Return the configured key-id/secret used by runtime lifetime digests.

    The migration must never derive an irreversible identity marker from the
    Django ``SECRET_KEY``: rotating that setting would make a deleted client
    eligible for a second reward.  A missing or malformed production keyring
    therefore aborts the migration before any non-transactional DDL runs.
    """
    raw = getattr(settings, "IG_UGC_IDENTITY_HMAC_KEYRING", {})
    active_id = str(
        getattr(settings, "IG_UGC_IDENTITY_HMAC_ACTIVE_KEY_ID", "") or ""
    ).strip()
    if not isinstance(raw, dict) or not raw or not active_id:
        raise RuntimeError(
            "IG_UGC_IDENTITY_HMAC_KEYRING and active key id are required"
        )
    normalized = {}
    for raw_key_id, raw_secret in raw.items():
        key_id = str(raw_key_id or "").strip()
        secret = str(raw_secret or "")
        if not _IDENTITY_KEY_ID_RE.fullmatch(key_id):
            raise RuntimeError("IG UGC identity HMAC key id is invalid")
        if len(secret.encode("utf-8")) < 32:
            raise RuntimeError("IG UGC identity HMAC secret must be at least 32 bytes")
        normalized[key_id] = secret.encode("utf-8")
    if active_id not in normalized:
        raise RuntimeError("IG UGC active identity HMAC key id is not in keyring")
    return active_id, normalized[active_id]


def _identity_digest_for_igsid(igsid):
    """Build the same versioned digest consumed by ``ig_ugc_rewards``."""
    normalized = unicodedata.normalize("NFKC", str(igsid or "")).strip().casefold()
    if not normalized:
        raise RuntimeError("UGC lifetime identity is empty")
    key_id, secret = _active_identity_key()
    material = f"instagram-ugc-lifetime:v1:{normalized}".encode("utf-8")
    digest = hmac.new(secret, material, hashlib.sha256).hexdigest()
    return f"{key_id}:{digest}"


def ensure_ugc_tables_innodb(apps, schema_editor):
    if schema_editor.connection.vendor not in {"mysql", "mariadb"}:
        return
    with schema_editor.connection.cursor() as cursor:
        for table in UGC_TABLES:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                [table],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"required UGC table is missing: {table}")
            if str(row[0]).lower() != "innodb":
                schema_editor.execute(
                    f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE=InnoDB"
                )


def preflight_legacy_ugc_rewards(apps, schema_editor):
    # Validate deployment identity configuration before the migration reaches
    # the non-transactional table-engine conversion below.
    _active_identity_key()
    Reward = apps.get_model("management", "IgUgcReward")
    Client = apps.get_model("management", "IgClient")

    duplicate = (
        Reward.objects.exclude(client_id__isnull=True)
        .values("client_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .order_by("client_id")
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "duplicate historical UGC rewards must be reconciled before migration: "
            f"client_id={duplicate['client_id']} count={duplicate['total']}"
        )

    client_ids = list(
        Reward.objects.exclude(client_id__isnull=True)
        .values_list("client_id", flat=True)
    )
    clients = {
        row.pk: row
        for row in Client.objects.filter(pk__in=client_ids).only("pk", "igsid")
    }
    normalized_owners = {}
    for client_id in client_ids:
        client = clients.get(client_id)
        normalized = unicodedata.normalize(
            "NFKC", str(getattr(client, "igsid", "") or "")
        ).strip().casefold()
        if not normalized:
            raise RuntimeError(
                "historical UGC reward has no stable Instagram identity: "
                f"client_id={client_id}"
            )
        previous = normalized_owners.setdefault(normalized, client_id)
        if previous != client_id:
            raise RuntimeError(
                "historical UGC identity collision must be reconciled before migration: "
                f"client_id={client_id} conflicts_with={previous}"
            )


def backfill_ugc_lifetime(apps, schema_editor):
    Reward = apps.get_model("management", "IgUgcReward")
    Client = apps.get_model("management", "IgClient")
    Lifetime = apps.get_model("management", "IgUgcRewardLifetime")

    _active_identity_key()
    client_ids = list(
        Reward.objects.exclude(client_id__isnull=True)
        .values_list("client_id", flat=True)
    )
    clients = {
        row.pk: row
        for row in Client.objects.filter(pk__in=client_ids).only("pk", "igsid")
    }
    for reward in Reward.objects.exclude(client_id__isnull=True).order_by("id"):
        client = clients.get(reward.client_id)
        normalized = unicodedata.normalize(
            "NFKC", str(getattr(client, "igsid", "") or "")
        ).strip().casefold()
        if not normalized:
            raise RuntimeError(
                "historical UGC reward has no stable Instagram identity: "
                f"reward_id={reward.pk} client_id={reward.client_id}"
            )
        digest = _identity_digest_for_igsid(normalized)
        lifetime, created = Lifetime.objects.get_or_create(
            identity_digest=digest,
            defaults={
                "client_id": reward.client_id,
                "reward_id": reward.pk,
                "consumed_at": reward.issued_at or reward.created_at,
            },
        )
        if not created and lifetime.reward_id != reward.pk:
            raise RuntimeError(
                "historical UGC identity collision must be reconciled before migration: "
                f"reward_id={reward.pk} lifetime_id={lifetime.pk}"
            )
        Reward.objects.filter(pk=reward.pk).update(lifetime_slot_key=digest)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("management", "0157_ig_follow_intelligence"),
        ("storefront", "0095_promocode_guest_ugc"),
    ]

    operations = [
        # This must run before non-transactional MySQL DDL. If historical data
        # violates the lifetime invariant, stop without leaving a half-applied
        # migration that would fail differently on the next deploy.
        migrations.RunPython(
            preflight_legacy_ugc_rewards,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ugc_rewards",
                to="management.igclient",
            ),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="evidence_message",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ugc_rewards",
                to="management.instagrambotmessage",
            ),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="order",
            field=models.OneToOneField(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="instagram_ugc_reward",
                to="orders.order",
            ),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="assignment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ugc_rewards",
                to="management.igorderassignment",
            ),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="promo_code",
            field=models.OneToOneField(
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="instagram_ugc_reward",
                to="storefront.promocode",
            ),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="assignment_version",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_ig_ugc_rewards",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="reward_path",
            field=models.CharField(default="delivered_order", db_index=True, max_length=24),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="decision_source",
            field=models.CharField(default="manager", max_length=16),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="issued_at",
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="lifetime_slot_key",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="IgUgcEvidenceAssessment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_message_id", models.CharField(db_index=True, max_length=255)),
                ("provider_object_key", models.CharField(blank=True, default="", db_index=True, max_length=255)),
                (
                    "provider_object_digest",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                ("provider_media_id", models.CharField(blank=True, default="", max_length=255)),
                ("provider_event_id", models.CharField(blank=True, default="", max_length=255)),
                ("target_username", models.CharField(blank=True, default="", max_length=80)),
                ("evidence_fingerprint", models.CharField(db_index=True, max_length=128)),
                ("perceptual_fingerprint", models.CharField(blank=True, default="", db_index=True, max_length=128)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("pending", "Очікує оцінки"),
                            ("qualified_auto", "Автоматично підтверджено"),
                            ("needs_manager_review", "Потрібен менеджер"),
                            ("rejected", "Відхилено"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("decision_source", models.CharField(default="policy", max_length=16)),
                ("policy_version", models.CharField(default="ugc-v1", max_length=32)),
                ("reason_codes", models.JSONField(blank=True, default=list)),
                ("catalog_candidates", models.JSONField(blank=True, default=list)),
                ("confidence", models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ("people_count", models.PositiveSmallIntegerField(default=0)),
                ("garment_count", models.PositiveSmallIntegerField(default=0)),
                ("reward_owner_client_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("generation", models.PositiveBigIntegerField(default=1)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("lease_token", models.CharField(blank=True, default="", max_length=64)),
                ("lease_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ugc_assessments",
                        to="management.igclient",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_ig_ugc_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["client", "-created_at"], name="ig_ugc_assess_client_dt"),
                    models.Index(fields=["decision", "-created_at"], name="ig_ugc_assess_decision_dt"),
                    models.Index(fields=["provider_object_key", "source_message_id"], name="ig_ugc_assess_provider"),
                ],
            },
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="assessment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rewards",
                to="management.igugcevidenceassessment",
            ),
        ),
        migrations.CreateModel(
            name="IgUgcRewardLifetime",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identity_digest", models.CharField(max_length=128, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ugc_reward_lifetime",
                        to="management.igclient",
                    ),
                ),
                (
                    "reward",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lifetime_slot",
                        to="management.igugcreward",
                    ),
                ),
                ("consumed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={
                "indexes": [models.Index(fields=["client", "reward"], name="ig_ugc_life_client_reward")],
            },
        ),
        migrations.CreateModel(
            name="IgUgcRewardDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("message_snapshot", models.TextField()),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("sent", "Sent"),
                            ("waiting_window", "Waiting window"),
                            ("ambiguous", "Ambiguous"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("due_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("lease_token", models.CharField(blank=True, default="", max_length=64)),
                ("lease_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("provider_message_ids", models.JSONField(blank=True, default=list)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ugc_reward_deliveries",
                        to="management.igclient",
                    ),
                ),
                (
                    "reward",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="delivery",
                        to="management.igugcreward",
                    ),
                ),
            ],
            options={
                "ordering": ["due_at", "id"],
                "indexes": [
                    models.Index(fields=["state", "due_at", "id"], name="ig_ugc_delivery_due"),
                    models.Index(fields=["client", "-created_at"], name="ig_ugc_delivery_client"),
                ],
            },
        ),
        # Convert before adding CHECK constraints so MariaDB enforces the
        # path/reviewer XORs on the durable InnoDB table rather than silently
        # inheriting legacy MyISAM behavior.
        migrations.RunPython(ensure_ugc_tables_innodb, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="igugcreward",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        reward_path="external_ugc",
                        order__isnull=True,
                        assignment__isnull=True,
                    )
                    | models.Q(
                        reward_path="delivered_order",
                        order__isnull=False,
                        assignment__isnull=False,
                    )
                ),
                name="ig_ugc_reward_path_refs",
            ),
        ),
        migrations.AddConstraint(
            model_name="igugcreward",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(decision_source="auto", reviewed_by__isnull=True)
                    | models.Q(decision_source="manager", reviewed_by__isnull=False)
                ),
                name="ig_ugc_reward_source_reviewer",
            ),
        ),
        migrations.RunPython(
            backfill_ugc_lifetime,
            migrations.RunPython.noop,
        ),
    ]
