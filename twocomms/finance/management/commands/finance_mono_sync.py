"""Періодична синхронізація monobank-інтеграцій (виклик із крона).

Поважає ліміт Monobank (1 statement-запит/60с): за замовчуванням один прогін
обробляє один рахунок на підключення і ротує рахунки між запусками. Запускати
раз на кілька хвилин:

    */5 * * * *  cd /path && python manage.py finance_mono_sync

Прапори:
    --full            backfill всієї історії (більше вікон за прогін)
    --connection ID   лише конкретне підключення
    --max-windows N   к-сть statement-вікон на рахунок за прогін (типово 1)
    --max-accounts N  к-сть рахунків за cron-прогін (типово 1)
    --all-accounts    ручний режим: синхронізувати всі авто-рахунки
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
        parser.add_argument('--max-accounts', type=int, default=1)
        parser.add_argument(
            '--all-accounts', action='store_true',
            help='Ручний режим: синхронізувати всі рахунки підключення за один запуск',
        )

    def handle(self, *args, **opts):
        qs = IntegrationConnection.objects.filter(
            provider='monobank', auto_sync=True).exclude(status='disconnected')
        if opts.get('connection'):
            qs = qs.filter(id=opts['connection'])

        total_created = 0
        for conn in qs:
            if not conn.has_token:
                continue

            if opts['all_accounts']:
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
                continue

            accounts = list(conn.accounts.filter(
                auto_sync=True).exclude(external_account_id='').order_by('id'))
            if not accounts:
                self.stdout.write(f'conn {conn.id}: немає auto-sync рахунків')
                continue

            max_accounts = max(1, min(int(opts['max_accounts'] or 1), len(accounts)))
            meta = dict(conn.meta or {})
            start = int(meta.get('mono_sync_next_account_index') or 0) % len(accounts)
            selected = [accounts[(start + offset) % len(accounts)] for offset in range(max_accounts)]
            client = mono_service._client_for(conn, use_cache=False)

            created = skipped = 0
            rate_limited = False
            processed = 0
            for account in selected:
                try:
                    res = mono_service.sync_account(
                        account, user=None, full=opts['full'], client=client,
                        max_windows=opts['max_windows'], reconcile_balance=False,
                    )
                except mono_api.MonoApiError as exc:
                    self.stderr.write(f'conn {conn.id} account {account.id}: {exc}')
                    continue
                processed += 1
                created += res.get('created', 0)
                skipped += res.get('skipped', 0)
                rate_limited = rate_limited or res.get('rate_limited', False)

            if processed:
                mono_service.reconcile_internal_transfers(conn.company, user=None)

            conn.refresh_from_db(fields=['meta'])
            meta = dict(conn.meta or {})
            meta['mono_sync_next_account_index'] = (start + max_accounts) % len(accounts)
            conn.meta = meta
            conn.save(update_fields=['meta'])

            total_created += created
            rl = ' (rate-limited, добере наступний прогін)' if rate_limited else ''
            account_ids = ','.join(str(a.id) for a in selected)
            self.stdout.write(
                f'conn {conn.id}: +{created} нових, {processed}/{len(accounts)} рахунків '
                f'(accounts {account_ids}, skipped {skipped}){rl}')
        self.stdout.write(self.style.SUCCESS(f'Готово. Нових операцій: {total_created}'))
