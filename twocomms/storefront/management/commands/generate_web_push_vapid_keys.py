import base64

from django.core.management.base import BaseCommand

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


class Command(BaseCommand):
    help = "Generate VAPID keys for browser Web Push."

    def handle(self, *args, **options):
        vapid = Vapid01()
        vapid.generate_keys()

        public_key_bytes = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        public_key = base64.urlsafe_b64encode(public_key_bytes).decode("utf-8").rstrip("=")
        private_key = vapid.private_pem().decode("utf-8")

        self.stdout.write(self.style.SUCCESS("Generated VAPID keys for Web Push."))
        self.stdout.write("")
        self.stdout.write("WEB_PUSH_VAPID_PUBLIC_KEY=" + public_key)
        self.stdout.write("WEB_PUSH_VAPID_SUBJECT=mailto:admin@twocomms.shop")
        self.stdout.write("WEB_PUSH_VAPID_PRIVATE_KEY=")
        self.stdout.write(private_key)
