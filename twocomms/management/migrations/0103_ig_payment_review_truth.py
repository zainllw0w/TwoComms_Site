from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_terminal_review_decisions(apps, schema_editor):
    Review = apps.get_model("management", "IgPaymentConfirmationReview")
    Decision = apps.get_model("management", "IgPaymentReviewDecision")

    rows = Review.objects.filter(status__in=["confirmed", "cancelled"]).select_related(
        "client",
        "deal",
        "confirmed_by",
        "cancelled_by",
    )
    for review in rows.iterator(chunk_size=200):
        if Decision.objects.filter(review_id=review.pk).exists():
            continue
        evidence = review.evidence if isinstance(review.evidence, dict) else {}
        telegram = evidence.get("telegram_decision")
        telegram = telegram if isinstance(telegram, dict) else {}
        actor = review.confirmed_by if review.status == "confirmed" else review.cancelled_by
        telegram_user_id = str(telegram.get("telegram_user_id") or "").strip()
        if telegram_user_id:
            actor_source = "telegram_user"
            actor_external_id = telegram_user_id
            actor_label = str(telegram.get("telegram_username") or telegram_user_id)[:150]
        elif actor:
            actor_source = "management_user"
            actor_external_id = str(actor.pk)
            actor_label = str(
                getattr(actor, "username", "")
                or getattr(actor, "email", "")
                or actor.pk
            )[:150]
        else:
            actor_source = "legacy_import"
            actor_external_id = f"review:{review.pk}"
            actor_label = "Legacy review import"
        if review.deal_id and review.deal.pay_type == "prepay_200":
            verification_scope = "prepayment"
        elif review.deal_id and review.deal.pay_type == "online_full":
            verification_scope = "full_payment"
        else:
            verification_scope = "payment_claim"
        is_confirmed = review.status == "confirmed"
        reason_code = "" if is_confirmed else "legacy_cancelled"
        reason_text = "" if is_confirmed else (review.cancellation_reason or reason_code)
        imported_decision = (
            "evidence_accepted_provider_unverified"
            if is_confirmed and actor_source == "legacy_import"
            else ("manager_verified" if is_confirmed else "manager_rejected")
        )
        decision = Decision.objects.create(
            review_id=review.pk,
            client_id=review.client_id,
            decision=imported_decision,
            verification_source=(
                "legacy_import" if actor_source == "legacy_import" else "manager"
            ),
            verification_scope=verification_scope,
            reason_code=reason_code,
            reason_text=reason_text[:500],
            evidence_watermark_message_id=review.watermark_message_id or 0,
            review_status_before="pending",
            review_status_after=review.status,
            stage_before="",
            stage_after=review.client.stage or "",
            actor_id=getattr(actor, "pk", None),
            actor_source=actor_source,
            actor_external_id=actor_external_id[:128],
            actor_label=actor_label,
            telegram_decision=telegram,
        )
        decided_at = review.confirmed_at if is_confirmed else review.cancelled_at
        if decided_at:
            Decision.objects.filter(pk=decision.pk).update(created_at=decided_at)


def noop_reverse(apps, schema_editor):
    pass


def create_append_only_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    drop_append_only_triggers(apps, schema_editor)
    if vendor in {"mysql", "mariadb"}:
        schema_editor.execute(
            "CREATE TRIGGER ig_paydec_no_update BEFORE UPDATE "
            "ON management_igpaymentreviewdecision FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgPaymentReviewDecision is append-only'"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_paydec_no_delete BEFORE DELETE "
            "ON management_igpaymentreviewdecision FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
            "'IgPaymentReviewDecision is append-only'"
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            "CREATE TRIGGER ig_paydec_no_update BEFORE UPDATE "
            "ON management_igpaymentreviewdecision "
            "BEGIN SELECT RAISE(ABORT, 'IgPaymentReviewDecision is append-only'); END"
        )
        schema_editor.execute(
            "CREATE TRIGGER ig_paydec_no_delete BEFORE DELETE "
            "ON management_igpaymentreviewdecision "
            "BEGIN SELECT RAISE(ABORT, 'IgPaymentReviewDecision is append-only'); END"
        )


def drop_append_only_triggers(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS ig_paydec_no_update")
    schema_editor.execute("DROP TRIGGER IF EXISTS ig_paydec_no_delete")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("management", "0102_ig_payment_review_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="IgPaymentReviewDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("manager_verified", "Підтверджено менеджером"), ("manager_rejected", "Відхилено менеджером"), ("evidence_accepted_provider_unverified", "Доказ прийнято, provider не підтверджено")], db_index=True, max_length=48)),
                ("verification_source", models.CharField(db_index=True, default="manager", max_length=32)),
                ("verification_scope", models.CharField(choices=[("full_payment", "Повна оплата"), ("prepayment", "Передоплата"), ("payment_claim", "Заявлений платіж")], max_length=32)),
                ("reason_code", models.CharField(blank=True, default="", max_length=64)),
                ("reason_text", models.CharField(blank=True, default="", max_length=500)),
                ("evidence_watermark_message_id", models.PositiveBigIntegerField(default=0)),
                ("review_status_before", models.CharField(blank=True, default="", max_length=16)),
                ("review_status_after", models.CharField(blank=True, default="", max_length=16)),
                ("stage_before", models.CharField(blank=True, default="", max_length=32)),
                ("stage_after", models.CharField(blank=True, default="", max_length=32)),
                ("actor_source", models.CharField(choices=[("management_user", "Користувач management"), ("telegram_user", "Користувач Telegram"), ("legacy_import", "Імпортовано з legacy review")], max_length=32)),
                ("actor_external_id", models.CharField(max_length=128)),
                ("actor_label", models.CharField(blank=True, default="", max_length=150)),
                ("telegram_decision", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ig_payment_review_decisions", to=settings.AUTH_USER_MODEL)),
                ("client", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name="payment_review_decisions", to="management.igclient")),
                ("review", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name="decisions", to="management.igpaymentconfirmationreview")),
            ],
            options={
                "verbose_name": "Рішення щодо перевірки оплати Instagram",
                "verbose_name_plural": "Рішення щодо перевірок оплати Instagram",
                "ordering": ["-id"],
                "indexes": [
                    models.Index(fields=["review", "-id"], name="ig_paydec_review_id"),
                    models.Index(fields=["client", "-created_at"], name="ig_paydec_client_dt"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="igpaymentreviewdecision",
            constraint=models.CheckConstraint(condition=~models.Q(actor_external_id=""), name="ig_paydec_actor_required"),
        ),
        migrations.AddConstraint(
            model_name="igpaymentreviewdecision",
            constraint=models.CheckConstraint(condition=models.Q(("decision", "manager_rejected"), _negated=True) | models.Q(("reason_code", ""), _negated=True), name="ig_paydec_reject_reason"),
        ),
        migrations.RunPython(backfill_terminal_review_decisions, noop_reverse),
        migrations.RunPython(create_append_only_triggers, drop_append_only_triggers),
    ]
