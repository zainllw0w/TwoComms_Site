"""Read-only, content-free status for durable Instagram ingress."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from management.models import InstagramBotSettings
from management.services.ig_webhook_inbox import inbox_status


class Command(BaseCommand):
    help = "Show bounded webhook inbox counts without customer payloads or IDs."

    def handle(self, *args, **options):
        settings_obj = InstagramBotSettings.objects.filter(pk=1).first()
        if settings_obj is None:
            raise CommandError("Instagram settings are not configured")
        self.stdout.write(json.dumps(
            inbox_status(settings_obj), cls=DjangoJSONEncoder,
            ensure_ascii=False, sort_keys=True,
        ))
