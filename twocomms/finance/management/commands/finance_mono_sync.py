"""Періодична синхронізація monobank-інтеграцій (виклик із крона).

Поважає ліміт Monobank (1 запит/60с): за один прогін бере невелику кількість
statement-вікон на підключення. Запускати раз на кілька хвилин:

    */5 * * * *  cd /path && python manage.py finance_mono_sync

Прапори:
    --full            backfill всієї історії (більше вікон за прогін)
    --connection ID   лише конкретне підключення
    --max-windows N   к-сть statement-вікон на рахунок за прогін (типово 1)
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from finance.models import IntegrationConnection
from finance.services import mono as mono_service
from finance.services import mono_api


class Command(BaseCommand):
    help = 'Синхронізує операції та баланси підключених рахунків monobank'

    def add_arguments(self, parser):
        parser.add_argument('--full', action='store_true', help='Backfill всієї історії')
        parser.add_argument('--connection', type=int, default=None)
        parser.add_argument('--max-windows', type=int, default=1)

    def handle(self, *args, **opts):
        qs = IntegrationConnection.objects.filter(
            provider='monobank', auto_sync=True).exclude(status='disconnected')
        if opts.get('connection'):
            qs = qs.filter(id=opts['connection'])

        total_created = 0
        for conn in qs:
            if not conn.has_token:
                continue
            try:
                summary = mono_service.sync_connection(
                    conn, user=None, full=opts['full'],
                    max_windows_per_account=opts['max_windows'])
            except mono_api.MonoApiError as exc:
                self.stderr.write(f'conn {conn.id}: {exc}')
                continue
            total_created += summary.get('created', 0)
            rl = ' (rate-limited, добере наступний прогін)' if summary.get('rate_limited') else ''
            self.stdout.write(
                f'conn {conn.id}: +{summary["created"]} нових, '
                f'{summary["accounts"]} рахунків{rl}')
        self.stdout.write(self.style.SUCCESS(f'Готово. Нових операцій: {total_created}'))
