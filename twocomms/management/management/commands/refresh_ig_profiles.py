from django.core.management.base import BaseCommand

from management.models import InstagramBotSettings
from management.services.instagram_bot import refresh_profiles_batch


class Command(BaseCommand):
    help = "Пакетно оновити імена, usernames та локальні аватарки Instagram-клієнтів."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        result = refresh_profiles_batch(
            InstagramBotSettings.load(),
            limit=options["limit"],
            force=options["force"],
        )
        message = (
            f"Профілів перевірено: {result['checked']}; "
            f"оновлено: {result['updated']}; помилок: {result['failed']}; "
            f"стан: {result['state']}"
        )
        writer = self.stdout.write if result["state"] == "ok" else self.stderr.write
        writer(message)
