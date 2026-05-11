"""Швидко надає warehouse-доступ існуючому користувачу (за username/email)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from warehouse.permissions import WAREHOUSE_GROUP_NAME


class Command(BaseCommand):
    help = "Додає користувача до групи warehouse_admins (та робить is_staff)."

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="Username або email користувача")
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Прибрати користувача з групи warehouse_admins",
        )

    def handle(self, *args, **options):
        ident = options["identifier"]
        remove = options.get("remove", False)
        User = get_user_model()
        user = User.objects.filter(username=ident).first() or User.objects.filter(email=ident).first()
        if user is None:
            raise CommandError(f"Користувача '{ident}' не знайдено")

        group, _ = Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)

        if remove:
            user.groups.remove(group)
            self.stdout.write(self.style.SUCCESS(f"❌ {user.username} видалено з {WAREHOUSE_GROUP_NAME}"))
            return

        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
            self.stdout.write(f"✓ {user.username}.is_staff = True")

        user.groups.add(group)
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {user.username} тепер у групі {WAREHOUSE_GROUP_NAME} (warehouse admin)"
            )
        )
