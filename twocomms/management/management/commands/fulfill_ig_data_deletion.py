"""Исполнить заявку на удаление данных DIRECT_BOT после проверки владения.

Публичная форма только регистрирует заявку (F-SEC-002). Удаление —
осознанное действие человека, у которого есть доступ к серверу.

    python manage.py fulfill_ig_data_deletion --list
    python manage.py fulfill_ig_data_deletion --code=ABCD1234 --dry-run
    python manage.py fulfill_ig_data_deletion --code=ABCD1234 --actor="ivan"
"""
from django.core.management.base import BaseCommand, CommandError

from management.models import BotDataDeletionRequest
from management.services.ig_data_deletion import (
    DeletionRequestNotActionable,
    fulfill_deletion_request,
)


class Command(BaseCommand):
    help = "Fulfill a verified DIRECT_BOT data deletion request."

    def add_arguments(self, parser):
        parser.add_argument("--code", help="confirmation code of the request")
        parser.add_argument(
            "--actor",
            default="",
            help="who verified ownership (goes into the audit trail)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="list pending requests and exit",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="show what would be deleted without deleting",
        )

    def handle(self, *args, **options):
        if options["list"]:
            pending = BotDataDeletionRequest.objects.filter(
                status=BotDataDeletionRequest.Status.PENDING_VERIFICATION
            ).order_by("created_at")
            if not pending:
                self.stdout.write("No pending deletion requests.")
                return
            for row in pending:
                self.stdout.write(
                    f"{row.confirmation_code}  {row.created_at:%Y-%m-%d %H:%M}  "
                    f"{row.normalized_identifier or '<empty>'}"
                )
            return

        code = (options.get("code") or "").strip().upper()
        if not code:
            raise CommandError("--code is required (or use --list)")

        row = BotDataDeletionRequest.objects.filter(confirmation_code=code).first()
        if row is None:
            raise CommandError(f"request {code} not found")

        if options["dry_run"]:
            from management.bot_views import _log_rows_for_sender_ids
            from management.models import (
                IgClient,
                InstagramBotMessage,
                InstagramBotRawEvent,
            )
            from django.db.models import Q

            ident = row.normalized_identifier or row.identifier
            clients = list(
                IgClient.objects.filter(
                    Q(igsid__iexact=ident)
                    | Q(username__iexact=ident)
                    | Q(display_name__iexact=ident)
                    | Q(phone_normalized__iexact=ident)
                )
            )
            sender_ids = {ident} | {c.igsid for c in clients if c.igsid}
            self.stdout.write(f"request {code} status={row.status}")
            self.stdout.write(f"  identifier: {ident}")
            self.stdout.write(f"  clients:    {len(clients)}")
            self.stdout.write(
                "  messages:   "
                f"{InstagramBotMessage.objects.filter(Q(sender_id__in=sender_ids) | Q(client__in=clients)).count()}"
            )
            self.stdout.write(
                "  raw events: "
                f"{InstagramBotRawEvent.objects.filter(sender_id__in=sender_ids).count()}"
            )
            self.stdout.write(
                f"  logs:       {_log_rows_for_sender_ids(sender_ids).count()}"
            )
            self.stdout.write("dry-run: nothing deleted")
            return

        actor = (options.get("actor") or "").strip() or "cli"
        try:
            deletion = fulfill_deletion_request(row, actor_label=f"manager:{actor}")
        except DeletionRequestNotActionable as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"{code} fulfilled: clients={deletion['clients']} "
                f"messages={deletion['messages']} raw_events={deletion['raw_events']} "
                f"logs={deletion['logs']}"
            )
        )
