"""Показати або застосувати підписку вебхука Instagram.

Функція `ensure_instagram_subscription()` існувала, але в production-коді її
ніхто не викликав — тільки тести. Тому змінити набір полів підписки було нічим,
і задеплоєна підтримка `messaging_postbacks` (кнопки карточок) не почала б
працювати сама собою.

`--apply` виконує ОБ'ЄДНАННЯ: спочатку читає поточні поля, потім записує їх
разом з обов'язковими. Meta замінює весь набір, тому сліпий запис зняв би поля,
підписані раніше вручну, і зламав би шляхи, які зараз працюють.
"""
from django.core.management.base import BaseCommand

from management.models import InstagramBotSettings
from management.services.instagram_bot import (
    REQUIRED_SUBSCRIPTION_FIELDS,
    ensure_instagram_subscription,
    instagram_subscription_fields,
)


class Command(BaseCommand):
    help = "Показати поточну підписку вебхука Instagram; --apply додає обов'язкові поля."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Записати об'єднаний набір полів у Meta (інакше — тільки читання).",
        )

    def handle(self, *args, **options):
        settings_row = InstagramBotSettings.load()
        current = instagram_subscription_fields(settings_row)
        required = tuple(REQUIRED_SUBSCRIPTION_FIELDS)
        missing = tuple(field for field in required if field not in current)

        self.stdout.write(f"current  : {', '.join(current) or '(порожньо або недоступно)'}")
        self.stdout.write(f"required : {', '.join(required)}")
        self.stdout.write(f"missing  : {', '.join(missing) or '(нічого)'}")

        if not options["apply"]:
            self.stdout.write(
                "read-only: щоб застосувати об'єднаний набір, запустіть з --apply"
            )
            return
        if not missing:
            self.stdout.write("нічого застосовувати: усі обов'язкові поля вже підписані")
            return

        result = ensure_instagram_subscription(settings_row)
        self.stdout.write(f"result   : {result}")
        after = instagram_subscription_fields(settings_row)
        self.stdout.write(f"after    : {', '.join(after) or '(порожньо або недоступно)'}")
