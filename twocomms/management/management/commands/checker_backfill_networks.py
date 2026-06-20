"""Бекфіл мереж лідів: класифікує parser-ліди й привʼязує до LeadNetwork.

Ідемпотентно (можна ганяти повторно). Чіпає лише авто-привʼязки
(network_membership_source in ("", "auto")); ручні/AI рішення зберігає.
Запуск на проді:
    python manage.py checker_backfill_networks
"""
from django.core.management.base import BaseCommand

from management.services import network_resolver


class Command(BaseCommand):
    help = "Класифікує parser-ліди (standalone/generic/network) і привʼязує до мереж (ідемпотентно)"

    def handle(self, *args, **options):
        stats = network_resolver.resolve_all()
        self.stdout.write("Резолвинг мереж завершено:")
        self.stdout.write(f"  standalone (одиночні)     : {stats['standalone']}")
        self.stdout.write(f"  generic (родові назви)    : {stats['generic']}")
        self.stdout.write(f"  network (кластери-мережі) : {stats['network']}")
        self.stdout.write(f"  LeadNetwork всього        : {stats['networks_total']}")
