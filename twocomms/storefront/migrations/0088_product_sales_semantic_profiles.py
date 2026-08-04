import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SEMANTIC_TABLES = (
    "storefront_productsalessemanticprofile",
    "storefront_productsalessemanticprofilerevision",
)

SEMANTIC_TRIGGER_NAMES = (
    "sf_sem_rev_no_update",
    "sf_sem_rev_no_delete",
)


def ensure_semantic_tables_innodb(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor not in {"mysql", "mariadb"}:
        return
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for table in SEMANTIC_TABLES:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                [table],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"required semantic table is missing: {table}")
            if str(row[0]).lower() != "innodb":
                schema_editor.execute(f"ALTER TABLE {quote(table)} ENGINE=InnoDB")


def drop_semantic_revision_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor in {"mysql", "mariadb", "sqlite"}:
        for name in SEMANTIC_TRIGGER_NAMES:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")
    elif vendor == "postgresql":
        table = "storefront_productsalessemanticprofilerevision"
        for name in SEMANTIC_TRIGGER_NAMES:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        schema_editor.execute("DROP FUNCTION IF EXISTS sf_semantic_revision_append_only()")


def create_semantic_revision_triggers(apps, schema_editor):
    drop_semantic_revision_triggers(apps, schema_editor)
    vendor = schema_editor.connection.vendor
    table = "storefront_productsalessemanticprofilerevision"
    if vendor in {"mysql", "mariadb"}:
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'Product sales semantic revisions are append-only'"
        )
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'Product sales semantic revisions are append-only'"
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_update BEFORE UPDATE ON {table} BEGIN "
            "SELECT RAISE(ABORT, 'Product sales semantic revisions are append-only'); END"
        )
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_delete BEFORE DELETE ON {table} BEGIN "
            "SELECT RAISE(ABORT, 'Product sales semantic revisions are append-only'); END"
        )
    elif vendor == "postgresql":
        schema_editor.execute(
            "CREATE OR REPLACE FUNCTION sf_semantic_revision_append_only() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Product sales semantic revisions are append-only'; END; $$"
        )
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION sf_semantic_revision_append_only()"
        )
        schema_editor.execute(
            f"CREATE TRIGGER sf_sem_rev_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION sf_semantic_revision_append_only()"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("storefront", "0087_promocodegroup_innodb"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductSalesSemanticProfile",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sales_semantic_profile",
                        to="storefront.product",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProductSalesSemanticProfileRevision",
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
                ("revision", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("verified", "Verified"),
                            ("revoked", "Revoked"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("schema_version", models.PositiveIntegerField(default=1)),
                ("aliases", models.JSONField(blank=True, default=dict)),
                ("traits", models.JSONField(blank=True, default=dict)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manager", "Manager"),
                            ("structured_catalog", "Structured catalog"),
                            ("structured_print_link", "Structured print link"),
                            ("migration", "Migration"),
                            ("bot_vision", "Bot vision suggestion"),
                            ("free_text", "Free text suggestion"),
                            ("generated_description", "Generated description suggestion"),
                        ],
                        max_length=32,
                    ),
                ),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="revisions",
                        to="storefront.productsalessemanticprofile",
                    ),
                ),
                (
                    "supersedes",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="superseded_by_revision",
                        to="storefront.productsalessemanticprofilerevision",
                    ),
                ),
                (
                    "verified_by",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verified_product_sales_semantic_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("profile_id", "revision")},
        ),
        migrations.AddConstraint(
            model_name="productsalessemanticprofilerevision",
            constraint=models.UniqueConstraint(
                fields=("profile", "revision"),
                name="product_semantic_revision_once",
            ),
        ),
        migrations.AddField(
            model_name="productsalessemanticprofile",
            name="effective_revision",
            field=models.OneToOneField(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="effective_for_profile",
                to="storefront.productsalessemanticprofilerevision",
            ),
        ),
        migrations.RunPython(
            ensure_semantic_tables_innodb,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            create_semantic_revision_triggers,
            reverse_code=drop_semantic_revision_triggers,
        ),
    ]
