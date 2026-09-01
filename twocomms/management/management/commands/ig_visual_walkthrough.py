"""Э1.х — послідовний walkthrough візуальних форматів на власному акаунті.

Контракт і обґрунтування — у `services/ig_visual_walkthrough` і в
`docs/instagram_bot_audit/new/10_VISUAL_MESSAGING.md`.

Три запобіжники, без яких команду не можна давати в руки:

* `--target` мусить бути в `IG_VISUAL_WALKTHROUGH_ALLOWLIST`, інакше відмова.
  Це не «на всяк випадок»: команда відправляє реальне повідомлення в Instagram.
* без `--send` нічого не надсилається, друкується лише payload;
* стан вікна Meta перевіряється читанням ДО відправки, тому закрите вікно дає
  зрозумілу відмову, а не 400 від провайдера.
"""
from __future__ import annotations

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Надіслати один візуальний формат на власний акаунт для перевірки вигляду"

    def add_arguments(self, parser):
        from management.services.ig_visual_walkthrough import STEP_ORDER

        parser.add_argument("--target", required=True, help="username власного акаунта")
        parser.add_argument("--step", required=True, choices=STEP_ORDER)
        parser.add_argument("--lang", default="uk", choices=("uk", "ru", "en"))
        parser.add_argument(
            "--send",
            action="store_true",
            help="Виконати справжню відправку (без цього — тільки друк payload)",
        )

    def handle(self, *args, **options):
        from management.models import IgClient, InstagramBotSettings
        from management.services import ig_visual_walkthrough as walk

        target = str(options["target"]).strip().lstrip("@")
        allowlist = {
            str(name).strip().lstrip("@").lower()
            for name in getattr(django_settings, "IG_VISUAL_WALKTHROUGH_ALLOWLIST", ())
            if str(name).strip()
        }
        if target.lower() not in allowlist:
            raise CommandError(
                f"{target!r} немає в IG_VISUAL_WALKTHROUGH_ALLOWLIST — "
                "прогон дозволений лише на власному акаунті"
            )

        client = (
            IgClient.objects.filter(username__iexact=target).first()
            or IgClient.objects.filter(igsid=target).first()
        )
        if client is None:
            raise CommandError(f"клієнта {target!r} немає в базі")

        window = walk.window_state(client, now=timezone.now())
        self.stdout.write(
            f"target={target} igsid={client.igsid} step={options['step']} "
            f"lang={options['lang']}"
        )
        self.stdout.write(
            f"вікно Meta: {window['state']}; останнє вхідне "
            f"{window['last_inbound_at'] or 'немає'}; safe-запас "
            f"{window['remaining_human']}"
        )

        plan = walk.build_step(options["step"], client=client, lang=options["lang"])
        self.stdout.write("--- що буде надіслано ---")
        for line in plan.describe():
            self.stdout.write(f"  {line}")

        if not options["send"]:
            self.stdout.write(
                self.style.WARNING("dry-run: додайте --send для справжньої відправки")
            )
            return
        if not window["can_send"]:
            raise CommandError(
                "вікно Meta закрите — попросіть написати боту і повторіть; "
                "відправка без вікна дала б 400 від провайдера"
            )

        outcome = walk.deliver(
            plan, settings_row=InstagramBotSettings.load(), client=client
        )
        self.stdout.write(f"результат: {outcome}")
