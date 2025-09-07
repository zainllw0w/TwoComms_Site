"""
Оптимизированные представления для улучшения производительности
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Prefetch
from django.contrib.auth.models import User

from .optimizations import DatabaseOptimizer, CacheManager, QueryAnalyzer
from .models import Product, Category
from accounts.models import UserProfile, UserPoints
from orders.models import Order

@cache_page(300)  # Кэшируем на 5 минут
def home_optimized(request):
    """Оптимизированная главная страница"""
    try:
        # Получаем кэшированные данные
        data = CacheManager.get_cached_home_data()
        
        # Подготавливаем цвета для товаров
        featured_variants = []
        if data['featured']:
            for variant in data['featured'].color_variants.all():
                featured_variants.append({
                    'primary_hex': variant.color.primary_hex,
                    'secondary_hex': variant.color.secondary_hex or '',
                    'is_default': variant.is_default,
                })
        
        # Подготавливаем цвета для новинок
        for product in data['products']:
            colors_preview = []
            for variant in product.color_variants.all():
                colors_preview.append({
                    'primary_hex': variant.color.primary_hex,
                    'secondary_hex': variant.color.secondary_hex or '',
                })
            setattr(product, 'colors_preview', colors_preview)
        
        has_more = data['total_products'] > 8
        
        return render(request, 'pages/index.html', {
            'featured': data['featured'],
            'categories': data['categories'],
            'products': data['products'],
            'featured_variants': featured_variants,
            'has_more_products': has_more,
            'current_page': 1,
            'total_products': data['total_products']
        })
    
    except Exception as e:
        # Fallback к оригинальной логике при ошибке
        from .views import home
        return home(request)

@require_GET
def load_more_products_optimized(request):
    """Оптимизированная загрузка дополнительных товаров"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 8
        offset = (page - 1) * per_page
        
        # Используем оптимизированный запрос
        products = list(DatabaseOptimizer.get_optimized_products_with_colors(
            limit=per_page, offset=offset
        ))
        
        # Подготавливаем цвета
        for product in products:
            colors_preview = []
            for variant in product.color_variants.all():
                colors_preview.append({
                    'primary_hex': variant.color.primary_hex,
                    'secondary_hex': variant.color.secondary_hex or '',
                })
            setattr(product, 'colors_preview', colors_preview)
        
        # Проверяем есть ли еще товары (используем кэш)
        total_products = DatabaseOptimizer.get_products_count_cached()
        has_more = (offset + per_page) < total_products
        
        # Рендерим HTML
        products_html = render_to_string('partials/products_list.html', {
            'products': products,
            'page': page
        })
        
        return JsonResponse({
            'html': products_html,
            'has_more': has_more,
            'next_page': page + 1 if has_more else None
        })
    
    except Exception as e:
        return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def admin_panel_optimized(request):
    """Оптимизированная админ-панель"""
    if not request.user.is_staff:
        return redirect('home')
    
    section = request.GET.get('section', 'stats')
    ctx = {'section': section}
    
    if section == 'users':
        # Используем оптимизированный запрос
        users = DatabaseOptimizer.get_optimized_users_with_stats()
        
        user_data = []
        for user in users:
            profile = getattr(user, 'userprofile', None)
            points = getattr(user, 'points', None)
            
            # Данные уже агрегированы в запросе
            order_status_counts = {
                'new': user.new_orders,
                'prep': user.prep_orders,
                'ship': user.ship_orders,
                'done': user.done_orders,
                'cancelled': user.cancelled_orders
            }
            
            payment_status_counts = {
                'unpaid': user.unpaid_orders,
                'checking': user.checking_orders,
                'partial': user.partial_orders,
                'paid': user.paid_orders
            }
            
            total_spent = user.total_spent or 0
            points_spent = points.total_spent if points else 0
            
            # Получаем промокоды пользователя
            try:
                from .models import PromoCode
                user_promocodes = PromoCode.objects.filter(user=user).order_by('-created_at')
                used_promocodes = []
                for order in user.orders.all():
                    if order.promo_code:
                        used_promocodes.append({
                            'code': order.promo_code.code,
                            'discount': order.promo_code.discount,
                            'used_in_order': order.order_number,
                            'used_date': order.created
                        })
            except:
                user_promocodes = []
                used_promocodes = []
            
            user_data.append({
                'user': user,
                'profile': profile,
                'points': points,
                'total_orders': user.total_orders_count,
                'order_status_counts': order_status_counts,
                'payment_status_counts': payment_status_counts,
                'total_spent': total_spent,
                'points_spent': points_spent,
                'promocodes': user_promocodes,
                'used_promocodes': used_promocodes
            })
        
        ctx.update({'user_data': user_data})
    
    elif section == 'orders':
        # Оптимизированные запросы для заказов
        from django.db.models import F
        
        # Получаем кэшированную статистику
        stats = DatabaseOptimizer.get_orders_stats_cached()
        
        # Базовый queryset с оптимизацией
        orders = Order.objects.select_related('user', 'promo_code').prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        )
        
        # Применяем фильтры
        status_filter = request.GET.get('status', 'all')
        payment_filter = request.GET.get('payment', 'all')
        user_id_filter = request.GET.get('user_id')
        
        if status_filter != 'all':
            orders = orders.filter(status=status_filter)
        if payment_filter != 'all':
            orders = orders.filter(payment_status=payment_filter)
        if user_id_filter:
            orders = orders.filter(user_id=user_id_filter)
        
        orders = orders.order_by('-created')[:100]  # Ограничиваем для производительности
        
        ctx.update({
            'orders': orders,
            'stats': stats,
            'status_filter': status_filter,
            'payment_filter': payment_filter,
            'user_id_filter': user_id_filter
        })
    
    elif section == 'stats':
        # Используем кэшированную статистику
        stats = DatabaseOptimizer.get_orders_stats_cached()
        
        # Дополнительная статистика
        from .models import Product, Category, PrintProposal
        from accounts.models import UserPoints
        
        stats.update({
            'total_products': Product.objects.count(),
            'total_categories': Category.objects.count(),
            'total_users': User.objects.count(),
            'print_proposals_pending': PrintProposal.objects.filter(status='pending').count(),
            'total_points_earned': UserPoints.objects.aggregate(
                total=Sum('points')
            )['total'] or 0,
        })
        
        ctx.update({'stats': stats})
    
    return render(request, 'pages/admin_panel.html', ctx)

@cache_page(600)  # Кэшируем каталог на 10 минут
def catalog_optimized(request, cat_slug=None):
    """Оптимизированный каталог"""
    categories = Category.objects.filter(is_active=True).order_by('order', 'name')
    
    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        products = DatabaseOptimizer.get_optimized_products_with_colors().filter(
            category=category
        )
        show_category_cards = False
    else:
        category = None
        products = DatabaseOptimizer.get_optimized_products_with_colors()
        show_category_cards = True
    
    return render(request, 'pages/catalog.html', {
        'categories': categories,
        'category': category,
        'products': products,
        'show_category_cards': show_category_cards
    })

# Middleware для мониторинга производительности
class PerformanceMiddleware:
    """Middleware для мониторинга производительности"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Логируем время начала запроса
        import time
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Логируем время выполнения
        process_time = time.time() - start_time
        
        # Логируем медленные запросы
        if process_time > 1.0:  # Запросы дольше 1 секунды
            logger.warning(f"Slow request: {request.path} took {process_time:.2f}s")
        
        # Добавляем заголовок с временем выполнения
        response['X-Process-Time'] = f"{process_time:.3f}"
        
        return response
