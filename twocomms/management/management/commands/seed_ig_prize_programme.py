"""Dry-run-first seed for the single editable shooting-prize instruction."""
from django.core.management.base import BaseCommand, CommandError

from management.models import BotInstruction
from management.services.ig_prize_programme import RESERVED_INTENT_TAG


DEFAULT_TITLE = "IG Prize · Стрелковый сертификат"
DEFAULT_PRIORITY = 18
DEFAULT_BODY = (
    "Применяй этот сценарий только когда текущий проверенный результат vision "
    "связан с фактически приложенным изображением и активной версией программы "
    "стрелкового приза. Если видимые признаки дают лишь кандидата, честно скажи, "
    "что изображение похоже на сертификат; не подтверждай подлинность, право на "
    "награду, стоимость, оплату или промокод. Коротко уточни, что клиенту "
    "интереснее: вещь из каталога или собственный принт. Условия и реальное право "
    "подтверждает менеджер. Обычный сертификат, чек, подпись в сообщении или "
    "непрочитанное изображение сами по себе этот сценарий не включают."
)


def _tags(value: object) -> set[str]:
    return {
        item.strip().casefold()
        for item in str(value or "").replace(";", ",").split(",")
        if item.strip()
    }


class Command(BaseCommand):
    help = (
        "Preview the single editable IG shooting-prize instruction; "
        "the release owner must pass --apply to create it."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create the instruction when none exists. Default is dry-run.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        matches = [
            instruction
            for instruction in BotInstruction.objects.order_by("id")
            if RESERVED_INTENT_TAG in _tags(instruction.intent_tags)
        ]
        if len(matches) > 1:
            ids = ",".join(str(item.pk) for item in matches)
            message = f"ambiguous: {len(matches)} programme instructions ({ids}); no changes"
            if apply_changes:
                raise CommandError(message)
            self.stdout.write(self.style.ERROR(message))
            return
        if matches:
            instruction = matches[0]
            self.stdout.write(
                "preserved: existing programme instruction "
                f"id={instruction.pk} active={str(instruction.is_active).lower()}"
            )
            return
        if not apply_changes:
            self.stdout.write(
                "dry-run: would create one active editable shooting-prize instruction"
            )
            return
        instruction = BotInstruction.objects.create(
            title=DEFAULT_TITLE,
            body=DEFAULT_BODY,
            intent_tags=RESERVED_INTENT_TAG,
            is_active=True,
            priority=DEFAULT_PRIORITY,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"created: programme instruction id={instruction.pk}"
            )
        )
