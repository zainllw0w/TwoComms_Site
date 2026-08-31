import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Dry-run or auditably repair one false historical Instagram purchase. "
        "No provider or customer message is sent."
    )

    def add_arguments(self, parser):
        parser.add_argument("--review-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int)
        parser.add_argument("--reason", default="")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        from management.ig_bot_models import (
            IgCommercialEpisode,
            IgPaymentConfirmationReview,
        )
        from management.services.bot_payment_truth import (
            client_has_confirmed_purchase,
            client_has_verified_payment,
        )
        from management.services.ig_commercial_episodes import (
            derive_current_episode_stage,
            review_has_false_historical_purchase_correction,
        )

        review = (
            IgPaymentConfirmationReview.objects.select_related("client")
            .filter(pk=options["review_id"])
            .first()
        )
        if review is None:
            raise CommandError("Payment review not found.")
        client = review.client

        def snapshot():
            current = (
                IgCommercialEpisode.objects.filter(
                    client_id=client.pk,
                    open_slot=1,
                    state=IgCommercialEpisode.State.ACTIVE,
                )
                .select_related("deal", "deal__order", "intended_order")
                .order_by("-sequence", "-id")
                .first()
            )
            return {
                "review_id": review.pk,
                "client_id": client.pk,
                "review_status": review.status,
                "already_corrected": review_has_false_historical_purchase_correction(
                    review
                ),
                "linked_episode_count": IgCommercialEpisode.objects.filter(
                    client_id=client.pk,
                    primary_payment_review_id=review.pk,
                ).count(),
                "current_episode_id": current.pk if current else None,
                "stored_stage": client.stage,
                "derived_stage": (
                    derive_current_episode_stage(client, current)
                    if current is not None
                    else "new"
                ),
                "verified_payment": client_has_verified_payment(client),
                "confirmed_purchase": client_has_confirmed_purchase(client),
                "purchases_count": int(client.purchases_count or 0),
            }

        before = snapshot()
        if not options["apply"]:
            self.stdout.write(json.dumps({
                "mode": "dry-run",
                "before": before,
            }, ensure_ascii=False, sort_keys=True))
            return

        reason = str(options["reason"] or "").strip()
        if not reason:
            raise CommandError("--reason is required with --apply.")
        actor_id = options.get("actor_id")
        actor = get_user_model().objects.filter(pk=actor_id).first()
        if actor is None or not (actor.is_staff or actor.is_superuser):
            raise CommandError("--actor-id must reference a staff user.")

        from management.services.ig_payment_review import (
            correct_false_historical_purchase,
        )

        try:
            correct_false_historical_purchase(
                review,
                actor=actor,
                reason=reason,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        review.refresh_from_db()
        client.refresh_from_db()
        self.stdout.write(json.dumps({
            "mode": "apply",
            "before": before,
            "after": snapshot(),
        }, ensure_ascii=False, sort_keys=True))
