"""
Команда для исправления домена в Django Sites framework
"""
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Исправляет домен в Django Sites framework'

    def handle(self, *args, **options):
        try:
            site = Site.objects.get(id=1)
            old_domain = site.domain
            site.domain = 'twocomms.shop'
            site.name = 'TwoComms'
            site.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Домен успешно изменен с "{old_domain}" на "{site.domain}"'
                )
            )
        except Site.DoesNotExist:
            # Создаем новый сайт если его нет
            site = Site.objects.create(
                id=1,
                domain='twocomms.shop',
                name='TwoComms'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Создан новый сайт: {site.domain}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка: {e}')
            )
