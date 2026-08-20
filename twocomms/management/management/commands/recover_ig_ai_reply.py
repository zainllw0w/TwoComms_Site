"""Guarded operator recovery for one failed Instagram AI reply."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from management.models import InstagramBotMessage
from management.services.ig_ai_reply_recovery import (
    process_recovery_job,
    recovery_preflight,
    schedule_recovery,
)


class Command(BaseCommand):
    help = "Inspect or execute one guarded Instagram AI reply recovery."

    def add_arguments(self, parser):
        parser.add_argument("--source-message", type=int, required=True)
        parser.add_argument(
            "--holding-message",
            type=int,
            help="Existing short holding reply to associate with this recovery.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Create/reuse the durable job and perform one guarded send pass.",
        )
        parser.add_argument(
            "--acknowledge-unreceipted-holding",
            action="store_true",
            help=(
                "Explicitly acknowledge that the exact holding row lacks a Meta receipt; "
                "requires --execute and --holding-message."
            ),
        )

    def handle(self, *args, **options):
        source = InstagramBotMessage.objects.filter(
            pk=options["source_message"],
        ).first()
        if source is None:
            raise CommandError("Source Instagram message does not exist")
        holding_id = options.get("holding_message")
        holding = None
        if holding_id:
            holding = InstagramBotMessage.objects.filter(
                pk=holding_id,
                client_id=source.client_id,
                role=InstagramBotMessage.Role.MODEL,
                id__gt=source.pk,
            ).first()
            if holding is None:
                raise CommandError("Holding message must be a later model message for this client")
        acknowledged = bool(options.get("acknowledge_unreceipted_holding"))
        if acknowledged and not options["execute"]:
            raise CommandError("--acknowledge-unreceipted-holding requires --execute")
        if acknowledged and holding is None:
            raise CommandError("--acknowledge-unreceipted-holding requires --holding-message")
        if acknowledged and holding.provider_message_id:
            raise CommandError("holding_must_be_unreceipted")
        preflight = recovery_preflight(
            source,
            acknowledged_unreceipted_holding=holding if acknowledged else None,
        )
        if not options["execute"]:
            payload = {
                "mode": "dry_run",
                **preflight,
                "response_window_deadline": (
                    preflight["response_window_deadline"].isoformat()
                    if preflight.get("response_window_deadline")
                    else None
                ),
                "activated_at": (
                    preflight["activated_at"].isoformat()
                    if preflight.get("activated_at")
                    else None
                ),
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            return
        if preflight.get("guard_reason"):
            raise CommandError(
                f"Recovery guard rejected source {source.pk}: "
                f"{preflight['guard_reason']}"
            )
        try:
            job = schedule_recovery(source, holding_message=holding)
            result = process_recovery_job(job.pk)
        except Exception as exc:
            raise CommandError(f"Recovery failed before completion: {exc}") from exc
        self.stdout.write(json.dumps({
            "mode": "execute",
            "source_message_id": source.pk,
            "job_id": result.pk if result else job.pk,
            "status": result.status if result else "missing",
            "provider_message_id": result.provider_message_id if result else "",
            "attempts": result.attempts if result else 0,
            "last_error": result.last_error if result else "",
        }, ensure_ascii=True, sort_keys=True))
