"""
Management команда для злиття «розколотих» акаунтів — коли один реальний
користувач має кілька записів User у БД (наприклад, після того, як TG-вхід
створив окремий запис, а Google-вхід — інший).

Стратегія:
  1. Беремо все UserProfile з telegram_id != null.
  2. Для кожного шукаємо інший User з тим самим email АБО тим самим
     UserSocialAuth (provider=google-oauth2) — кандидат на merge.
  3. Якщо знайдено — питаємо `--apply`, інакше тільки виводимо preview.

Запуск:
  python manage.py merge_split_accounts             # dry-run, показує preview
  python manage.py merge_split_accounts --apply     # реально мерджить
  python manage.py merge_split_accounts --user <username>   # тільки одного
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Знаходить і зливає split-акаунти (TG + Google для одного користувача)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Реально виконати merge")
        parser.add_argument("--user", help="Username конкретного користувача (TG-аккаунт)")

    def handle(self, *args, **options):
        from storefront.social_pipeline import _merge_user_data
        from social_django.models import UserSocialAuth

        apply = options["apply"]
        username_filter = options.get("user")

        qs = UserProfile.objects.filter(telegram_id__isnull=False).select_related("user")
        if username_filter:
            qs = qs.filter(user__username=username_filter)

        merged = 0
        skipped = 0
        already_merged = set()
        for profile in qs:
            tg_user = profile.user
            if tg_user.pk in already_merged:
                continue
            tg_email = (tg_user.email or "").strip().lower()
            tg_phone = (profile.phone or "").strip()

            # Не чіпаємо адмінів як TG-юзера, лише якщо вони джерело.
            # Якщо TG-юзер — admin, то він залишається target і
            # пів-аккаунт Google вливається в нього. Це безпечно.

            # Шукаємо потенційного кандидата на merge — лише серед НЕ адмінів
            # (адміна не можна зливати, бо source видаляється).
            candidates = User.objects.exclude(pk=tg_user.pk).filter(
                is_staff=False, is_superuser=False
            )

            email_match = None
            if tg_email:
                email_match = candidates.filter(email__iexact=tg_email).first()

            phone_match = None
            if tg_phone:
                phone_match = candidates.filter(userprofile__phone=tg_phone).first()

            # Юзер з Google-привʼязкою, що має той самий email
            google_match = None
            if tg_email:
                google_match = (
                    candidates
                    .filter(
                        social_auth__provider="google-oauth2",
                        social_auth__user__email__iexact=tg_email,
                    )
                    .first()
                )

            other = email_match or phone_match or google_match
            if not other:
                skipped += 1
                continue
            if other.pk in already_merged:
                # Уже мерджили в попередній ітерації
                continue

            self.stdout.write(
                f"  → TG-user '{tg_user.username}' (id={tg_user.pk}, email='{tg_email}')"
                f"   ↔ candidate '{other.username}' (id={other.pk}, email='{other.email}')"
            )
            if not apply:
                continue

            try:
                _merge_user_data(source=other, target=tg_user)
                merged += 1
                already_merged.add(other.pk)
                self.stdout.write(self.style.SUCCESS(f"     merged ✓"))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"     failed: {exc}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Готово. Кандидатів: {merged + skipped}, "
                                f"merged: {merged}, skipped: {skipped}")
        )
        if not apply and merged + skipped:
            self.stdout.write("Запустіть з --apply для реального merge.")
