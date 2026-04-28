"""
Административная панель для заказов дропшиперов
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import DropshipperOrder, DropshipperOrderItem, DropshipperStats, DropshipperPayout


class DropshipperOrderItemInline(admin.TabularInline):
    """Inline для отображения товаров в заказе"""
    model = DropshipperOrderItem
    extra = 0
    readonly_fields = ('product', 'color_variant', 'size', 'fit_option_label', 'quantity', 'drop_price', 'selling_price',
                       'recommended_price', 'total_drop_price', 'total_selling_price', 'item_profit')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DropshipperOrder)
class DropshipperOrderAdmin(admin.ModelAdmin):
    """Административная панель для заказов дропшиппера"""
    list_display = ('order_number', 'dropshipper_info', 'client_info', 'status_badge',
                    'payment_status_badge', 'profit_display', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('order_number', 'client_name', 'client_phone', 'dropshipper__username',
                     'dropshipper__userprofile__company_name')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'dropshipper', 'profit',
                       'total_drop_price', 'total_selling_price', 'order_details')

    fieldsets = (
        ('Основна інформація', {
            'fields': ('order_number', 'dropshipper', 'created_at', 'updated_at')
        }),
        ('Дані клієнта', {
            'fields': ('client_name', 'client_phone', 'client_np_address')
        }),
        ('Статус та доставка', {
            'fields': ('status', 'payment_status', 'tracking_number')
        }),
        ('Фінанси', {
            'fields': ('total_selling_price', 'total_drop_price', 'profit')
        }),
        ('Додаткова інформація', {
            'fields': ('order_source', 'notes', 'order_details'),
            'classes': ('collapse',)
        }),
    )

    inlines = [DropshipperOrderItemInline]

    def get_queryset(self, request):
        """Оптимизация запросов для списка заказов"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'dropshipper__userprofile'
        ).prefetch_related(
            'items__product',
            'items__color_variant__color'
        )

    def dropshipper_info(self, obj):
        """Отображает информацию о дропшипере"""
        try:
            profile = obj.dropshipper.userprofile
            company = profile.company_name if profile.company_name else obj.dropshipper.username
            phone = profile.phone if profile.phone else '—'
            return format_html(
                '<strong>{}</strong><br><small>📞 {}</small>',
                company, phone
            )
        except Exception:
            return obj.dropshipper.username
    dropshipper_info.short_description = 'Дропшипер'

    def client_info(self, obj):
        """Отображает информацию о клиенте"""
        return format_html(
            '<strong>{}</strong><br><small>📞 {}</small>',
            obj.client_name if obj.client_name else '—',
            obj.client_phone if obj.client_phone else '—'
        )
    client_info.short_description = 'Клієнт'

    def status_badge(self, obj):
        """Отображает статус заказа с цветным бейджем"""
        colors = {
            'draft': '#fbbf24',
            'pending': '#8b5cf6',
            'confirmed': '#3b82f6',
            'processing': '#f59e0b',
            'shipped': '#06b6d4',
            'delivered': '#10b981',
            'cancelled': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def payment_status_badge(self, obj):
        """Отображает статус оплаты с цветным бейджем"""
        colors = {
            'unpaid': '#fbbf24',
            'paid': '#10b981',
            'refunded': '#6b7280'
        }
        color = colors.get(obj.payment_status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 11px;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Оплата'

    def profit_display(self, obj):
        """Отображает прибыль с форматированием"""
        if obj.profit > 0:
            return format_html(
                '<span style="color: #10b981; font-weight: 700;">+{} грн</span>',
                obj.profit
            )
        return format_html('<span style="color: #6b7280;">{} грн</span>', obj.profit)
    profit_display.short_description = 'Прибуток'

    def order_details(self, obj):
        """Отображает детали заказа"""
        items_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        items_html += '<tr style="background: #f3f4f6; font-weight: 600;">'
        items_html += '<th style="padding: 8px; text-align: left;">Товар</th>'
        items_html += '<th style="padding: 8px; text-align: center;">Кількість</th>'
        items_html += '<th style="padding: 8px; text-align: right;">Ціна дропа</th>'
        items_html += '<th style="padding: 8px; text-align: right;">Ціна продажу</th>'
        items_html += '<th style="padding: 8px; text-align: right;">Прибуток</th>'
        items_html += '</tr>'

        for item in obj.items.all():
            items_html += '<tr style="border-bottom: 1px solid #e5e7eb;">'
            items_html += f'<td style="padding: 8px;">{item.product.title}'
            if item.size:
                items_html += f'<br><small>Розмір: {item.size}</small>'
            if item.fit_label:
                items_html += f'<br><small>Посадка: {item.fit_label}</small>'
            if item.color_variant:
                items_html += f'<br><small>Колір: {item.color_variant.color.name if hasattr(item.color_variant.color, "name") else str(item.color_variant.color)}</small>'
            items_html += '</td>'
            items_html += f'<td style="padding: 8px; text-align: center;">{item.quantity}</td>'
            items_html += f'<td style="padding: 8px; text-align: right;">{item.drop_price} грн</td>'
            items_html += f'<td style="padding: 8px; text-align: right;">{item.selling_price} грн</td>'
            items_html += f'<td style="padding: 8px; text-align: right; color: #10b981; font-weight: 600;">+{item.item_profit} грн</td>'
            items_html += '</tr>'

        items_html += '</table>'
        return mark_safe(items_html)
    order_details.short_description = 'Деталі замовлення'

    def save_model(self, request, obj, form, change):
        """Пересчитывает прибыль при сохранении"""
        obj.calculate_profit()
        super().save_model(request, obj, form, change)


@admin.register(DropshipperOrderItem)
class DropshipperOrderItemAdmin(admin.ModelAdmin):
    """Административная панель для товаров в заказе дропшиппера"""
    list_display = ('order_link', 'product', 'size', 'fit_option_label', 'quantity', 'drop_price',
                    'selling_price', 'item_profit')
    list_filter = ('order__status', 'product__category')
    search_fields = ('order__order_number', 'product__title')
    readonly_fields = ('order', 'product', 'color_variant', 'fit_option_code', 'fit_option_label', 'total_drop_price',
                       'total_selling_price', 'item_profit')

    def get_queryset(self, request):
        """Оптимизация запросов для списка товаров"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'order',
            'product',
            'color_variant__color'
        )

    def order_link(self, obj):
        """Ссылка на заказ"""
        url = reverse('admin:orders_dropshipperorder_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Замовлення'


@admin.register(DropshipperStats)
class DropshipperStatsAdmin(admin.ModelAdmin):
    """Административная панель для статистики дропшипера"""
    list_display = ('dropshipper', 'total_orders', 'completed_orders', 'total_revenue',
                    'total_profit', 'last_order_date')
    list_filter = ('last_order_date',)
    search_fields = ('dropshipper__username', 'dropshipper__userprofile__company_name')
    readonly_fields = ('dropshipper', 'total_orders', 'completed_orders', 'cancelled_orders',
                       'total_revenue', 'total_profit', 'total_drop_cost', 'total_items_sold',
                       'last_order_date', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DropshipperPayout)
class DropshipperPayoutAdmin(admin.ModelAdmin):
    """Административная панель для выплат дропшиперам"""
    list_display = ('payout_number', 'dropshipper_info', 'amount', 'status_badge',
                    'payment_method', 'requested_at')
    list_filter = ('status', 'payment_method', 'requested_at')
    search_fields = ('payout_number', 'dropshipper__username',
                     'dropshipper__userprofile__company_name')
    readonly_fields = ('payout_number', 'dropshipper', 'requested_at',
                       'processed_at', 'completed_at', 'orders_list')

    def get_queryset(self, request):
        """Оптимизация запросов для списка выплат"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'dropshipper__userprofile'
        ).prefetch_related(
            'included_orders'
        )

    fieldsets = (
        ('Основна інформація', {
            'fields': ('payout_number', 'dropshipper', 'amount', 'status')
        }),
        ('Метод оплати', {
            'fields': ('payment_method', 'payment_details')
        }),
        ('Дати', {
            'fields': ('requested_at', 'processed_at', 'completed_at')
        }),
        ('Замовлення', {
            'fields': ('orders_list',),
            'classes': ('collapse',)
        }),
        ('Додаткова інформація', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def dropshipper_info(self, obj):
        """Отображает информацию о дропшипере"""
        try:
            profile = obj.dropshipper.userprofile
            company = profile.company_name if profile.company_name else obj.dropshipper.username
            return format_html('<strong>{}</strong>', company)
        except Exception:
            return obj.dropshipper.username
    dropshipper_info.short_description = 'Дропшипер'

    def status_badge(self, obj):
        """Отображает статус выплаты с цветным бейджем"""
        colors = {
            'pending': '#fbbf24',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'rejected': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def orders_list(self, obj):
        """Список заказов в выплате"""
        if not obj.id:
            return '—'

        orders_html = '<table style="width: 100%; border-collapse: collapse;">'
        orders_html += '<tr style="background: #f3f4f6; font-weight: 600;">'
        orders_html += '<th style="padding: 8px; text-align: left;">Номер</th>'
        orders_html += '<th style="padding: 8px; text-align: left;">Клієнт</th>'
        orders_html += '<th style="padding: 8px; text-align: right;">Сума</th>'
        orders_html += '</tr>'

        for order in obj.included_orders.all():
            url = reverse('admin:orders_dropshipperorder_change', args=[order.id])
            orders_html += '<tr style="border-bottom: 1px solid #e5e7eb;">'
            orders_html += f'<td style="padding: 8px;"><a href="{url}">{order.order_number}</a></td>'
            orders_html += f'<td style="padding: 8px;">{order.client_name}</td>'
            orders_html += f'<td style="padding: 8px; text-align: right;">{order.profit} грн</td>'
            orders_html += '</tr>'

        orders_html += '</table>'
        return mark_safe(orders_html)
    orders_list.short_description = 'Замовлення у виплаті'
