from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import hashlib
import hmac


def _identity_digest(igsid):
    value = str(igsid or "").strip()
    if not value:
        return ""
    return hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        ("instagram:" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def recreate_append_only_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    # ``atomic = False`` permits an interrupted deploy between DDL statements.
    # Drop only this migration's triggers so a resumed migration is idempotent
    # and the payment-decision guards from 0103 remain untouched.
    drop_append_only_triggers(apps, schema_editor)
    if vendor in {"mysql", "mariadb"}:
        schema_editor.execute(
            "CREATE TRIGGER ig_orderlink_no_update BEFORE UPDATE "
            "ON management_igorderlinkevent FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgOrderLinkEvent is append-only'"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderlink_no_delete BEFORE DELETE "
            "ON management_igorderlinkevent FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgOrderLinkEvent is append-only'"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderattr_no_update BEFORE UPDATE "
            "ON management_igorderattribution FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgOrderAttribution is append-only'"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderattr_no_delete BEFORE DELETE "
            "ON management_igorderattribution FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgOrderAttribution is append-only'"
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            "CREATE TRIGGER ig_orderlink_no_update BEFORE UPDATE "
            "ON management_igorderlinkevent "
            "BEGIN SELECT RAISE(ABORT, 'IgOrderLinkEvent is append-only'); END"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderattr_no_update BEFORE UPDATE "
            "ON management_igorderattribution "
            "BEGIN SELECT RAISE(ABORT, 'IgOrderAttribution is append-only'); END"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderattr_no_delete BEFORE DELETE "
            "ON management_igorderattribution "
            "BEGIN SELECT RAISE(ABORT, 'IgOrderAttribution is append-only'); END"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_orderlink_no_delete BEFORE DELETE "
            "ON management_igorderlinkevent "
            "BEGIN SELECT RAISE(ABORT, 'IgOrderLinkEvent is append-only'); END"
        )
    elif vendor == "postgresql":
        schema_editor.execute(
            "CREATE OR REPLACE FUNCTION ig_order_audit_append_only_raise() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$"
        )
        for table, update_name, delete_name in (
            ("management_igorderlinkevent", "ig_orderlink_no_update", "ig_orderlink_no_delete"),
            ("management_igorderattribution", "ig_orderattr_no_update", "ig_orderattr_no_delete"),
        ):
            schema_editor.execute(f"CREATE TRIGGER {update_name} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION ig_order_audit_append_only_raise()")
            schema_editor.execute(f"CREATE TRIGGER {delete_name} BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION ig_order_audit_append_only_raise()")


def drop_append_only_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor in {"mysql", "mariadb", "sqlite"}:
        for name in (
            "ig_orderlink_no_update",
            "ig_orderlink_no_delete",
            "ig_orderattr_no_update",
            "ig_orderattr_no_delete",
        ):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")
    elif vendor == "postgresql":
        for table, names in (
            ("management_igorderlinkevent", ("ig_orderlink_no_update", "ig_orderlink_no_delete")),
            ("management_igorderattribution", ("ig_orderattr_no_update", "ig_orderattr_no_delete")),
        ):
            for name in names:
                schema_editor.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        schema_editor.execute("DROP FUNCTION IF EXISTS ig_order_audit_append_only_raise()")


def noop_reverse(apps, schema_editor):
    pass


def backfill_existing_instagram_orders(apps, schema_editor):
    Attribution = apps.get_model("management", "IgOrderAttribution")
    Deal = apps.get_model("management", "IgDeal")
    Review = apps.get_model("management", "IgPaymentConfirmationReview")
    Decision = apps.get_model("management", "IgPaymentReviewDecision")
    Projection = apps.get_model("management", "IgPaymentProjection")
    OrderItem = apps.get_model("orders", "OrderItem")

    def authoritative_decision(review):
        if not review or review.status != "confirmed":
            return None
        decision = Decision.objects.filter(
            review_id=review.pk,
            decision="manager_verified",
            verification_source="manager",
            actor_source__in=("management_user", "telegram_user"),
        ).exclude(actor_external_id="").order_by("-id").first()
        return decision

    def item_snapshot(order_id):
        rows = OrderItem.objects.filter(order_id=order_id).order_by("id")
        return [{
            "product_id": row.product_id,
            "color_variant_id": row.color_variant_id,
            "title": row.title,
            "size": row.size or "",
            "fit_option_code": row.fit_option_code or "",
            "fit_option_label": row.fit_option_label or "",
            "option_values": row.option_values or {},
            "option_labels": row.option_labels or {},
            "qty": row.qty,
            "unit_price": str(row.unit_price),
            "line_total": str(row.line_total),
            "price_source": "legacy_order_snapshot",
            "price_evidence_message_ids": [],
        } for row in rows.iterator(chunk_size=200)]

    for deal in Deal.objects.exclude(order_id__isnull=True).select_related("client").iterator(chunk_size=200):
        if Attribution.objects.filter(order_id=deal.order_id).exists():
            continue
        review = Review.objects.filter(
            deal_id=deal.pk,
            order_id=deal.order_id,
            status="confirmed",
        ).order_by("-id").first()
        decision = authoritative_decision(review)
        provider = Projection.objects.filter(
            deal_id=deal.pk, truth__in=("confirmed", "partially_refunded")
        ).exists()
        Attribution.objects.create(
            order_id=deal.order_id,
            client_id=deal.client_id,
            deal_id=deal.pk,
            payment_review_id=getattr(review, "pk", None),
            manager_decision_id=getattr(decision, "pk", None),
            creation_mode="provider_auto" if provider else ("manager_review" if decision else "linked_existing"),
            payment_source="provider_projection" if provider else ("manager_verified" if decision else "unknown"),
            identity_digest=_identity_digest(deal.client.igsid),
            evidence_watermark_message_id=getattr(review, "watermark_message_id", 0) or 0,
            item_provenance=item_snapshot(deal.order_id),
            negotiated_total=deal.amount,
            price_source="legacy_order_snapshot",
        )

    for review in Review.objects.exclude(order_id__isnull=True).select_related("client").iterator(chunk_size=200):
        if Attribution.objects.filter(order_id=review.order_id).exists():
            continue
        decision = authoritative_decision(review)
        Attribution.objects.create(
            order_id=review.order_id,
            client_id=review.client_id,
            deal_id=review.deal_id,
            payment_review_id=review.pk,
            manager_decision_id=getattr(decision, "pk", None),
            creation_mode="linked_existing",
            payment_source="manager_verified" if decision else "unknown",
            identity_digest=_identity_digest(review.client.igsid),
            evidence_watermark_message_id=review.watermark_message_id or 0,
            item_provenance=item_snapshot(review.order_id),
            price_source="legacy_order_snapshot",
        )


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0051_paymentattempt"),
        ("management", "0103_ig_payment_review_truth"),
    ]

    operations = [
        migrations.AlterField(
            model_name="igpaymentreviewdecision",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="payment_review_decisions",
                to="management.igclient",
            ),
        ),
        migrations.AlterField(
            model_name="igpaymentreviewdecision",
            name="review",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="decisions",
                to="management.igpaymentconfirmationreview",
            ),
        ),
        migrations.AlterField(
            model_name="igpaymentconfirmationreview",
            name="order",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="instagram_payment_reviews",
                to="orders.order",
            ),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="fit_option_code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="fit_option_label",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="option_values",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="option_labels",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="price_source",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igdealitem",
            name="price_evidence_message_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="IgOrderAttribution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creation_mode", models.CharField(choices=[("provider_auto", "Автоматично за provider payment"), ("manager_review", "Створено після перевірки менеджером"), ("linked_existing", "Прив'язано до існуючого замовлення")], max_length=32)),
                ("payment_source", models.CharField(choices=[("provider_projection", "Provider projection"), ("provider_attempt", "Provider payment attempt"), ("manager_verified", "Перевірено менеджером"), ("unknown", "Невідоме джерело")], default="unknown", max_length=32)),
                ("identity_digest", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("evidence_watermark_message_id", models.PositiveBigIntegerField(default=0)),
                ("item_provenance", models.JSONField(blank=True, default=list)),
                ("negotiated_total", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("price_source", models.CharField(blank=True, default="", max_length=64)),
                ("price_evidence_message_ids", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_attributions", to="management.igclient")),
                ("created_by", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="ig_order_attributions_created", to=settings.AUTH_USER_MODEL)),
                ("deal", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_attributions", to="management.igdeal")),
                ("manager_decision", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_attributions", to="management.igpaymentreviewdecision")),
                ("order", models.OneToOneField(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="instagram_attribution", to="orders.order")),
                ("payment_review", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_attributions", to="management.igpaymentconfirmationreview")),
            ],
            options={
                "verbose_name": "Атрибуція Instagram-замовлення",
                "verbose_name_plural": "Атрибуції Instagram-замовлень",
                "indexes": [models.Index(fields=["client", "-created_at"], name="ig_order_attr_client_dt"), models.Index(fields=["creation_mode", "-created_at"], name="ig_order_attr_mode_dt")],
            },
        ),
        migrations.CreateModel(
            name="IgOrderLinkEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_kind", models.CharField(default="linked", max_length=32)),
                ("reason_code", models.CharField(blank=True, default="", max_length=64)),
                ("mismatch_snapshot", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="ig_order_link_events", to=settings.AUTH_USER_MODEL)),
                ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_link_events", to="management.igclient")),
                ("order", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="instagram_link_events", to="orders.order")),
                ("review", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="order_link_events", to="management.igpaymentconfirmationreview")),
            ],
            options={
                "indexes": [models.Index(fields=["client", "-created_at"], name="ig_order_link_client_dt")],
                "constraints": [models.UniqueConstraint(fields=("order", "review", "event_kind"), name="ig_order_link_event_once")],
            },
        ),
        migrations.RunPython(backfill_existing_instagram_orders, noop_reverse),
        migrations.RunPython(recreate_append_only_triggers, drop_append_only_triggers),
    ]
