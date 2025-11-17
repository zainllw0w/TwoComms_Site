"""
Management command для отправки email отчетов по UTM аналитике.

Использование:
    python manage.py send_utm_report --period week --recipients admin@example.com
    python manage.py send_utm_report --period month --format html
"""

import logging
from decimal import Decimal
from io import BytesIO
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from storefront.utm_analytics import (
    get_general_stats,
    get_sources_stats,
    get_campaigns_stats,
    get_funnel_stats,
    get_geo_stats,
    compare_periods,
    calculate_roi,
)
from storefront.utm_cohort_analysis import (
    get_source_ltv_comparison,
    get_repeat_purchase_rate,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправить email отчет по UTM аналитике'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            default='week',
            choices=['today', 'week', 'month', 'all_time'],
            help='Период для отчета (today/week/month/all_time)'
        )
        parser.add_argument(
            '--recipients',
            type=str,
            help='Email получателей через запятую'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='html',
            choices=['html', 'text'],
            help='Формат отчета (html/text)'
        )
        parser.add_argument(
            '--attach-csv',
            action='store_true',
            help='Приложить CSV файлы с детальными данными'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Сгенерировать отчет без отправки email'
        )
    
    def handle(self, *args, **options):
        period = options['period']
        recipients = options.get('recipients')
        format_type = options['format']
        attach_csv = options['attach_csv']
        dry_run = options['dry_run']
        
        # Определяем получателей
        if not recipients:
            # Используем админов из settings если не указаны получатели
            recipients = [admin[1] for admin in getattr(settings, 'ADMINS', [])]
            if not recipients:
                raise CommandError('Укажите получателей через --recipients или настройте ADMINS в settings.py')
        else:
            recipients = [email.strip() for email in recipients.split(',')]
        
        self.stdout.write(f'Генерация отчета за период: {period}')
        
        try:
            # Собираем данные для отчета
            general_stats = get_general_stats(period)
            sources_stats = get_sources_stats(period, limit=10)
            campaigns_stats = get_campaigns_stats(period, limit=10)
            funnel_stats = get_funnel_stats(period)
            geo_stats = get_geo_stats(period, limit=5)
            comparison = compare_periods(period)
            ltv_comparison = get_source_ltv_comparison(period)[:5]
            repeat_rate = get_repeat_purchase_rate(period)
            
            # Преобразуем Decimal в float для шаблона
            def convert_decimals(data):
                if isinstance(data, dict):
                    return {k: convert_decimals(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [convert_decimals(item) for item in data]
                elif isinstance(data, Decimal):
                    return float(data)
                return data
            
            context = {
                'period': period,
                'period_label': self._get_period_label(period),
                'report_date': timezone.now().strftime('%d.%m.%Y %H:%M'),
                'general_stats': convert_decimals(general_stats),
                'sources_stats': convert_decimals(sources_stats),
                'campaigns_stats': convert_decimals(campaigns_stats),
                'funnel_stats': convert_decimals(funnel_stats),
                'geo_stats': convert_decimals(geo_stats),
                'comparison': convert_decimals(comparison),
                'ltv_comparison': convert_decimals(ltv_comparison),
                'repeat_rate': convert_decimals(repeat_rate),
            }
            
            # Генерируем тему письма
            subject = f'UTM Аналітика - Звіт за {context["period_label"]} ({context["report_date"]})'
            
            # Генерируем тело письма
            if format_type == 'html':
                message = self._generate_html_report(context)
            else:
                message = self._generate_text_report(context)
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE'))
                self.stdout.write(f'Тема: {subject}')
                self.stdout.write(f'Получатели: {", ".join(recipients)}')
                self.stdout.write('\n--- Начало отчета ---')
                self.stdout.write(message[:500] + '...')
                self.stdout.write('--- Конец отчета ---\n')
                self.stdout.write(self.style.SUCCESS('Отчет сгенерирован (не отправлен)'))
                return
            
            # Создаем email
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@twocomms.shop'),
                to=recipients,
            )
            
            if format_type == 'html':
                email.content_subtype = 'html'
            
            # Прикрепляем CSV файлы если нужно
            if attach_csv:
                self._attach_csv_files(email, context)
            
            # Отправляем
            email.send(fail_silently=False)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Отчет отправлен на {len(recipients)} адресов'))
            
        except Exception as e:
            logger.error(f'Ошибка при отправке UTM отчета: {e}', exc_info=True)
            raise CommandError(f'Ошибка при генерации/отправке отчета: {e}')
    
    def _get_period_label(self, period):
        """Возвращает украинский лейбл периода"""
        labels = {
            'today': 'сьогодні',
            'week': 'тиждень',
            'month': 'місяць',
            'all_time': 'весь час'
        }
        return labels.get(period, period)
    
    def _generate_html_report(self, context):
        """Генерирует HTML версию отчета"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #8b5cf6;
            border-bottom: 3px solid #8b5cf6;
            padding-bottom: 10px;
        }
        h2 {
            color: #6366f1;
            margin-top: 30px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .metric-card {
            background: #f3f4f6;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #8b5cf6;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #8b5cf6;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        .change-positive {
            color: #10b981;
        }
        .change-negative {
            color: #ef4444;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        th {
            background: #f9fafb;
            font-weight: 600;
            color: #666;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e5e7eb;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>📊 UTM Аналітика - Звіт</h1>
    <p><strong>Період:</strong> {{ period_label }} | <strong>Дата:</strong> {{ report_date }}</p>
    
    <h2>📈 Загальна статистика</h2>
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value">{{ general_stats.total_sessions }}</div>
            <div class="metric-label">Сесії</div>
            {% if comparison.change.sessions %}
                <div class="{% if comparison.change.sessions > 0 %}change-positive{% else %}change-negative{% endif %}">
                    {{ comparison.change.sessions|floatformat:1 }}%
                </div>
            {% endif %}
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ general_stats.total_conversions }}</div>
            <div class="metric-label">Конверсії</div>
            {% if comparison.change.conversions %}
                <div class="{% if comparison.change.conversions > 0 %}change-positive{% else %}change-negative{% endif %}">
                    {{ comparison.change.conversions|floatformat:1 }}%
                </div>
            {% endif %}
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ general_stats.conversion_rate }}%</div>
            <div class="metric-label">CR%</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ general_stats.total_revenue|floatformat:0 }} ₴</div>
            <div class="metric-label">Дохід</div>
            {% if comparison.change.revenue %}
                <div class="{% if comparison.change.revenue > 0 %}change-positive{% else %}change-negative{% endif %}">
                    {{ comparison.change.revenue|floatformat:1 }}%
                </div>
            {% endif %}
        </div>
    </div>
    
    <h2>🎯 Топ-5 джерел трафіку</h2>
    <table>
        <thead>
            <tr>
                <th>Джерело</th>
                <th>Сесії</th>
                <th>Конверсії</th>
                <th>CR%</th>
                <th>Дохід</th>
            </tr>
        </thead>
        <tbody>
            {% for source in sources_stats|slice:":5" %}
            <tr>
                <td><strong>{{ source.utm_source }}</strong></td>
                <td>{{ source.sessions }}</td>
                <td>{{ source.conversions }}</td>
                <td>{{ source.conversion_rate }}%</td>
                <td>{{ source.revenue|floatformat:0 }} ₴</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <h2>💰 LTV по джерелах (Топ-5)</h2>
    <table>
        <thead>
            <tr>
                <th>Джерело</th>
                <th>Сесій</th>
                <th>LTV/Сесія</th>
                <th>Сер. чек</th>
                <th>Замовлень/Сесія</th>
            </tr>
        </thead>
        <tbody>
            {% for item in ltv_comparison %}
            <tr>
                <td><strong>{{ item.utm_source }}</strong></td>
                <td>{{ item.total_sessions }}</td>
                <td>{{ item.ltv_per_session|floatformat:0 }} ₴</td>
                <td>{{ item.avg_order_value|floatformat:0 }} ₴</td>
                <td>{{ item.orders_per_session|floatformat:2 }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <h2>🔄 Повторні покупки</h2>
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value">{{ repeat_rate.repeat_rate }}%</div>
            <div class="metric-label">Відсоток повторних покупок</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ repeat_rate.avg_orders_per_customer|floatformat:2 }}</div>
            <div class="metric-label">Середня к-ть замовлень</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ repeat_rate.avg_time_between_orders|floatformat:0 }}</div>
            <div class="metric-label">Днів між замовленнями</div>
        </div>
    </div>
    
    <h2>📊 Воронка конверсій</h2>
    <table>
        <thead>
            <tr>
                <th>Етап</th>
                <th>Кількість</th>
                <th>%</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Сесії</td>
                <td>{{ funnel_stats.total }}</td>
                <td>100%</td>
            </tr>
            <tr>
                <td>Перегляди товарів</td>
                <td>{{ funnel_stats.product_views }}</td>
                <td>{{ funnel_stats.product_views_rate }}%</td>
            </tr>
            <tr>
                <td>В кошик</td>
                <td>{{ funnel_stats.add_to_cart }}</td>
                <td>{{ funnel_stats.add_to_cart_rate }}%</td>
            </tr>
            <tr>
                <td>Оформлення</td>
                <td>{{ funnel_stats.initiate_checkout }}</td>
                <td>{{ funnel_stats.checkout_rate }}%</td>
            </tr>
            <tr>
                <td>Ліди</td>
                <td>{{ funnel_stats.leads }}</td>
                <td>{{ funnel_stats.lead_rate }}%</td>
            </tr>
            <tr>
                <td><strong>Покупки</strong></td>
                <td><strong>{{ funnel_stats.purchases }}</strong></td>
                <td><strong>{{ funnel_stats.purchase_rate }}%</strong></td>
            </tr>
        </tbody>
    </table>
    
    <div class="footer">
        <p>Цей звіт згенеровано автоматично системою UTM Dispatcher.</p>
        <p>Для детальної інформації відвідайте: <a href="https://twocomms.shop/admin-panel?section=dispatcher">Диспетчер UTM</a></p>
    </div>
</body>
</html>
        """
        
        from django.template import Template, Context
        template = Template(html_template)
        return template.render(Context(context))
    
    def _generate_text_report(self, context):
        """Генерирует текстовую версию отчета"""
        lines = []
        lines.append('=' * 60)
        lines.append('UTM АНАЛІТИКА - ЗВІТ')
        lines.append('=' * 60)
        lines.append(f"Період: {context['period_label']}")
        lines.append(f"Дата: {context['report_date']}")
        lines.append('')
        
        lines.append('ЗАГАЛЬНА СТАТИСТИКА')
        lines.append('-' * 60)
        gs = context['general_stats']
        lines.append(f"Сесії: {gs['total_sessions']}")
        lines.append(f"Конверсії: {gs['total_conversions']}")
        lines.append(f"CR%: {gs['conversion_rate']}%")
        lines.append(f"Дохід: {gs['total_revenue']:.0f} ₴")
        lines.append(f"Середній чек: {gs['avg_order_value']:.0f} ₴")
        lines.append('')
        
        lines.append('ТОП-5 ДЖЕРЕЛ ТРАФІКУ')
        lines.append('-' * 60)
        for source in context['sources_stats'][:5]:
            lines.append(f"{source['utm_source']}: {source['sessions']} сесій, "
                        f"{source['conversions']} конверсій ({source['conversion_rate']}%), "
                        f"{source['revenue']:.0f} ₴")
        lines.append('')
        
        lines.append('ВОРОНКА КОНВЕРСІЙ')
        lines.append('-' * 60)
        fs = context['funnel_stats']
        lines.append(f"Сесії: {fs['total']} (100%)")
        lines.append(f"Перегляди товарів: {fs['product_views']} ({fs['product_views_rate']}%)")
        lines.append(f"В кошик: {fs['add_to_cart']} ({fs['add_to_cart_rate']}%)")
        lines.append(f"Оформлення: {fs['initiate_checkout']} ({fs['checkout_rate']}%)")
        lines.append(f"Ліди: {fs['leads']} ({fs['lead_rate']}%)")
        lines.append(f"Покупки: {fs['purchases']} ({fs['purchase_rate']}%)")
        lines.append('')
        
        lines.append('=' * 60)
        lines.append('Детальна інформація: https://twocomms.shop/admin-panel?section=dispatcher')
        lines.append('=' * 60)
        
        return '\n'.join(lines)
    
    def _attach_csv_files(self, email, context):
        """Прикрепляет CSV файлы к email"""
        try:
            import csv
            from io import StringIO
            
            # 1. Источники трафика
            sources_io = StringIO()
            writer = csv.writer(sources_io)
            writer.writerow(['Джерело', 'Сесії', 'Конверсії', 'CR%', 'Дохід', 'Середній чек'])
            for source in context['sources_stats']:
                writer.writerow([
                    source.get('utm_source', 'direct'),
                    source.get('sessions', 0),
                    source.get('conversions', 0),
                    source.get('conversion_rate', 0),
                    source.get('revenue', 0),
                    source.get('avg_order_value', 0),
                ])
            email.attach('utm_sources.csv', sources_io.getvalue(), 'text/csv')
            
            # 2. Кампании
            campaigns_io = StringIO()
            writer = csv.writer(campaigns_io)
            writer.writerow(['Кампанія', 'Джерело', 'Сесії', 'Конверсії', 'CR%', 'Дохід'])
            for campaign in context['campaigns_stats']:
                writer.writerow([
                    campaign.get('utm_campaign', ''),
                    campaign.get('utm_source', ''),
                    campaign.get('sessions', 0),
                    campaign.get('conversions', 0),
                    campaign.get('conversion_rate', 0),
                    campaign.get('revenue', 0),
                ])
            email.attach('utm_campaigns.csv', campaigns_io.getvalue(), 'text/csv')
            
        except Exception as e:
            logger.warning(f'Не удалось прикрепить CSV файлы: {e}')
