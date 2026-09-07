import hashlib
import json

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SCHEMA_VERSION = 1
COMPILER_VERSION = "instruction-set-v1"
RESERVED_PROGRAMME_TAG = "programme:shooting_prize"


def _bootstrap_item(row):
    tags = []
    triggers = []
    for raw in str(row.intent_tags or "").replace(";", ",").split(","):
        value = raw.strip().casefold()
        if not value:
            continue
        if value.startswith("on:"):
            trigger = value[3:].strip()
            if trigger and trigger not in triggers:
                triggers.append(trigger)
        elif value not in tags:
            tags.append(value)
    programme = {}
    if RESERVED_PROGRAMME_TAG in tags:
        programme = {
            "kind": "shooting_prize",
            "programme_id": "shooting_prize",
            "manager_required": True,
            "confirmed_visual_sample": False,
        }
    return {
        "id": f"instruction:{row.pk}",
        "source_id": int(row.pk),
        "title": str(row.title or "").strip()[:200],
        "body": str(row.body or "").strip(),
        "active": bool(row.is_active),
        "priority": int(row.priority),
        "locale": "all",
        "tags": sorted(tags),
        "triggers": sorted(triggers),
        "programme_metadata": programme,
        "allowed_actions": [],
        "trust_scope": "public_policy",
    }


def bootstrap_instruction_publication(apps, schema_editor):
    BotInstruction = apps.get_model("management", "BotInstruction")
    BotPolicyPublication = apps.get_model("management", "BotPolicyPublication")
    InstagramBotSettings = apps.get_model("management", "InstagramBotSettings")
    AdminAuditLog = apps.get_model("management", "AdminAuditLog")

    rows = list(BotInstruction.objects.order_by("priority", "id")[:301])
    if len(rows) > 300:
        raise RuntimeError("BotInstruction bootstrap exceeds 300 rows")
    items = [_bootstrap_item(row) for row in rows]
    items.sort(key=lambda item: (item["priority"], item["source_id"]))
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "instructions": items,
    }
    encoded = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    publication = BotPolicyPublication.objects.create(
        version=1,
        kind="bootstrap",
        schema_version=SCHEMA_VERSION,
        snapshot=snapshot,
        snapshot_hash=digest,
        compiler_version=COMPILER_VERSION,
        instruction_count=len(items),
        actor_label="migration:0196",
        note="bootstrap current BotInstruction set",
    )
    settings_obj, _created = InstagramBotSettings.objects.get_or_create(pk=1)
    settings_obj.active_instruction_publication_id = publication.pk
    settings_obj.instruction_draft_revision = 1
    settings_obj.save(update_fields=[
        "active_instruction_publication",
        "instruction_draft_revision",
        "updated_at",
    ])
    AdminAuditLog.objects.create(
        actor=None,
        actor_role="migration",
        action="ig_bot.policy_bootstrapped",
        entity_type="bot_instruction_policy",
        entity_id=str(publication.pk),
        before={},
        after={
            "version": 1,
            "snapshot_hash": digest,
            "instruction_count": len(items),
        },
        reason="migration:0196",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0195_ig_turn_revisions"),
    ]

    operations = [
        migrations.AddField(
            model_name="botinstruction",
            name="allowed_actions",
            field=models.JSONField(blank=True, db_default=[], default=list),
        ),
        migrations.AddField(
            model_name="botinstruction",
            name="locale",
            field=models.CharField(
                choices=[
                    ("all", "Усі мови"),
                    ("uk", "Українська"),
                    ("ru", "Російська"),
                    ("en", "Англійська"),
                ],
                db_index=True,
                db_default="all",
                default="all",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="botinstruction",
            name="programme_metadata",
            field=models.JSONField(blank=True, db_default={}, default=dict),
        ),
        migrations.AddField(
            model_name="botinstruction",
            name="trigger_codes",
            field=models.JSONField(blank=True, db_default=[], default=list),
        ),
        migrations.AddField(
            model_name="botinstruction",
            name="trust_scope",
            field=models.CharField(
                choices=[
                    ("public_policy", "Публічна політика"),
                    ("operator_only", "Лише оператор"),
                ],
                db_index=True,
                db_default="public_policy",
                default="public_policy",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="BotPolicyPublication",
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
                ("version", models.PositiveBigIntegerField(unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("bootstrap", "Початковий знімок"),
                            ("publish", "Публікація"),
                            ("rollback", "Відкат"),
                        ],
                        max_length=12,
                    ),
                ),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("snapshot", models.JSONField(default=dict)),
                ("snapshot_hash", models.CharField(db_index=True, max_length=64)),
                ("compiler_version", models.CharField(max_length=32)),
                ("instruction_count", models.PositiveIntegerField(default=0)),
                ("actor_label", models.CharField(blank=True, default="", max_length=150)),
                ("note", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bot_policy_publications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="successor_publications",
                        to="management.botpolicypublication",
                    ),
                ),
                (
                    "restored_from",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rollback_publications",
                        to="management.botpolicypublication",
                    ),
                ),
            ],
            options={
                "ordering": ["-version", "-id"],
                "indexes": [
                    models.Index(
                        fields=["kind", "-version"],
                        name="bot_policy_kind_ver",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="active_instruction_publication",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="active_settings",
                to="management.botpolicypublication",
            ),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="instruction_draft_revision",
            field=models.PositiveBigIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="geminirequest",
            name="policy_manifest",
            field=models.JSONField(blank=True, db_default={}, default=dict),
        ),
        migrations.RunPython(
            bootstrap_instruction_publication,
            migrations.RunPython.noop,
        ),
    ]
