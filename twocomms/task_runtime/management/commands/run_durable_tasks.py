import os
import socket

from django.core.management.base import BaseCommand, CommandError

from task_runtime.runtime import run_bounded_worker


class Command(BaseCommand):
    help = "Run one bounded batch of allowlisted durable Django tasks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--lease-seconds", type=int, default=60)
        parser.add_argument("--worker-id", default="")

    def handle(self, *args, **options):
        worker_id = options["worker_id"].strip() or f"{socket.gethostname()}:{os.getpid()}"
        try:
            outcome = run_bounded_worker(
                limit=options["limit"],
                lease_seconds=options["lease_seconds"],
                worker_id=worker_id[:128],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            "claimed={claimed} completed={completed} failed={failed}".format(**outcome)
        )
