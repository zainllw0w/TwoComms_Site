"""
Admin views - Административная панель.

Содержит views для:
- Управления товарами
- Управления категориями
- Управления промокодами
- Генерации контента (AI, SEO)
- Статистики и отчетов
- Дропшипинг панель
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils.text import slugify

from ..models import Product, Category, PromoCode, PrintProposal
from ..forms import ProductForm, CategoryForm, PrintProposalForm
from .utils import unique_slugify


# ==================== ADMIN VIEWS ====================

@staff_member_required
def admin_dashboard(request):
    """
    Главная страница административной панели.
    
    Показывает:
    - Статистику продаж
    - Последние заказы
    - Популярные товары
    - Сводка по складу
    """
    from orders.models import Order
    from django.db.models import Count, Sum
    from datetime.datetime import timedelta
    from django.utils import timezone
    
    # Статистика за последние 30 дней
    last_30_days = timezone.now() - timedelta(days=30)
    
    stats = {
        'total_orders': Order.objects.filter(created__gte=last_30_days).count(),
        'total_revenue': Order.objects.filter(
            created__gte=last_30_days,
            payment_status='paid'
        ).aggregate(total=Sum('total_sum'))['total'] or 0,
        'pending_orders': Order.objects.filter(status='new').count(),
        'total_products': Product.objects.count(),
        'total_categories': Category.objects.count()
    }
    
    # Последние заказы
    recent_orders = Order.objects.order_by('-created')[:10]
    
    # Популярные товары
    # TODO: Реализовать на основе статистики продаж
    
    return render(
        request,
        'admin/dashboard.html',
        {
            'stats': stats,
            'recent_orders': recent_orders
        }
    )


@staff_member_required
def manage_products(request):
    """
    Список всех товаров с возможностью фильтрации.
    
    Query params:
        category: ID категории для фильтрации
        featured: Показать только featured
        search: Поиск по названию
    """
    products = Product.objects.select_related('category').order_by('-id')
    
    # Фильтры
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    if request.GET.get('featured'):
        products = products.filter(featured=True)
    
    search = request.GET.get('search')
    if search:
        products = products.filter(title__icontains=search)
    
    categories = Category.objects.all()
    
    return render(
        request,
        'admin/manage_products.html',
        {
            'products': products,
            'categories': categories
        }
    )


@transaction.atomic
def add_product(request):
    """
    Добавление нового товара через унифицированный интерфейс.
    
    Supports:
    - AJAX форма (JSON response)
    - Обычная форма (HTML redirect)
    - Добавление цветовых вариантов
    - Загрузка изображений
    """
    # TODO: Полная реализация добавления товара
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'add_product'):
        return old_views.add_product(request)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            if not getattr(product, 'slug', None):
                base = slugify(product.title or '')
                product.slug = unique_slugify(Product, base)
            product.save()
            return redirect('product', slug=product.slug)
    else:
        form = ProductForm()
    
    return render(
        request,
        'pages/add_product_new.html',
        {
            'form': form,
            'product': None,
            'is_new': True
        }
    )


@login_required
def add_category(request):
    """
    Добавление новой категории.
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('catalog')
    else:
        form = CategoryForm()
    
    return render(
        request,
        'pages/add_category.html',
        {'form': form}
    )


def add_print(request):
    """
    Страница предложения принтов от пользователей.
    
    Features:
    - Анти-спам (лимит 1 минута)
    - Загрузка изображений или URL
    - Система баллов за одобренные принты
    """
    # TODO: Полная реализация
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'add_print'):
        return old_views.add_print(request)
    
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        form = PrintProposalForm(request.POST, request.FILES)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.user = request.user
            proposal.save()
            return redirect('cooperation')
    else:
        form = PrintProposalForm()
    
    proposals = []
    if request.user.is_authenticated:
        proposals = PrintProposal.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]
    
    return render(
        request,
        'pages/add_print.html',
        {
            'form': form,
            'proposals': proposals
        }
    )


@staff_member_required
def manage_print_proposals(request):
    """
    Административная панель для управления предложениями принтов.
    
    Actions:
    - Approve (одобрить)
    - Reject (отклонить)
    - Award points (начислить баллы)
    - Award promocode (выдать промокод)
    """
    status_filter = request.GET.get('status', 'pending')
    
    proposals = PrintProposal.objects.filter(
        status=status_filter
    ).select_related('user').order_by('-created_at')
    
    return render(
        request,
        'admin/manage_print_proposals.html',
        {
            'proposals': proposals,
            'status_filter': status_filter
        }
    )


@staff_member_required
def manage_promo_codes(request):
    """
    Управление промокодами.
    
    Features:
    - Создание новых промокодов
    - Редактирование существующих
    - Деактивация
    - Статистика использования
    """
    promo_codes = PromoCode.objects.all().order_by('-created_at')
    
    return render(
        request,
        'admin/manage_promo_codes.html',
        {'promo_codes': promo_codes}
    )


@staff_member_required
def generate_seo_content(request):
    """
    Генерация SEO контента с помощью AI (OpenAI).
    
    Features:
    - AI-генерация keywords
    - AI-генерация descriptions
    - Bulk операции для всех товаров
    """
    # TODO: Полная реализация AI генерации
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'generate_seo_content'):
        return old_views.generate_seo_content(request)
    
    return render(request, 'admin/generate_seo.html')


@staff_member_required
def generate_alt_texts(request):
    """
    Генерация ALT текстов для изображений.
    
    Uses AI для автоматического описания изображений товаров.
    """
    # TODO: Реализовать генерацию alt текстов
    return render(request, 'admin/generate_alt_texts.html')


@staff_member_required
def manage_orders(request):
    """
    Управление заказами.
    
    Features:
    - Список всех заказов
    - Фильтрация по статусу
    - Обновление статусов
    - Добавление TTN (tracking number)
    - Печать накладных
    """
    from orders.models import Order
    
    status_filter = request.GET.get('status', '')
    
    orders = Order.objects.select_related('user').order_by('-created')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    return render(
        request,
        'admin/manage_orders.html',
        {
            'orders': orders,
            'status_filter': status_filter
        }
    )


@staff_member_required
def sales_statistics(request):
    """
    Статистика продаж.
    
    Features:
    - Графики продаж по дням/неделям/месяцам
    - Топ товары
    - Топ категории
    - Средний чек
    - Конверсия
    """
    # TODO: Реализовать детальную статистику
    return render(request, 'admin/sales_statistics.html')


@staff_member_required
def inventory_management(request):
    """
    Управление складом.
    
    Features:
    - Остатки товаров
    - Поступления
    - Списания
    - Резервы под заказы
    """
    # TODO: Реализовать управление складом
    return render(request, 'admin/inventory.html')
















