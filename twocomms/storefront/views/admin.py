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
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils.text import slugify

from ..models import (
    Product,
    ProductStatus,
    Category,
    PromoCode,
    PrintProposal,
    Catalog,
    SizeGrid,
)
from ..forms import (
    ProductForm,
    ProductSEOForm,
    CategoryForm,
    PrintProposalForm,
    SizeGridForm,
    CatalogOptionFormSet,
    build_color_variant_formset,
)
from .utils import unique_slugify
from .promo import render_admin_promocodes_page
from storefront.services.catalog import (
    append_product_gallery,
    formset_to_variant_payloads,
    sync_variant_images,
)


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


@login_required
def admin_panel(request):
    """
    Упрощённая реализация головної адмін-панелі.

    Підтримує ключові секції:
    - stats (поки що лише базові значення)
    - promocodes (повністю через новий інтерфейс)

    Інші секції рендеряться з порожнім контекстом, щоб зберегти працездатність шаблону.
    """
    if not request.user.is_staff:
        return redirect('home')

    section = request.GET.get('section', 'stats')

    # Промокоди виносимо в окремий повноцінний шаблон
    if section == 'promocodes':
        return render_admin_promocodes_page(request)

    # Базові плейсхолдери для інших секцій
    context = {
        'section': section,
        'stats': {
            'period': request.GET.get('period', 'all_time'),
            'period_name': 'За весь час',
            'online_users': 0,
            'sessions_period': 0,
            'page_views_period': 0,
            'bounce_rate': 0,
            'orders_count': 0,
            'orders_today': 0,
            'revenue': 0,
            'avg_order_value': 0,
            'total_users': 0,
            'new_users_period': 0,
            'active_users_today': 0,
            'active_users_period': 0,
            'total_products': 0,
            'total_categories': 0,
            'print_proposals_pending': 0,
            'promocodes_used': 0,
            'total_points_earned': 0,
            'users_with_points': 0,
        },
        'orders': [],
        'users': [],
        'catalogs': [],
        'offline_stores': [],
        'print_proposals': [],
    }

    return render(request, 'pages/admin_panel.html', context)


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


@staff_member_required
def admin_product_builder(request, product_id=None):
    """
    Новый конструктор товара.
    
    Поддерживает создание и редактирование товара с цветовыми вариантами.
    """
    is_new = product_id is None

    if product_id is not None:
        product = get_object_or_404(
            Product.objects.select_related('catalog', 'category'),
            pk=product_id
        )
    else:
        product = Product(status=ProductStatus.DRAFT)
    original_slug = product.slug

    # Базовые формы
    if request.method == 'POST':
        product_form = ProductForm(
            data=request.POST,
            files=request.FILES,
            prefix='product',
            instance=product,
        )
        seo_form = ProductSEOForm(
            data=request.POST,
            prefix='seo',
            instance=product,
        )
    else:
        product_form = ProductForm(prefix='product', instance=product)
        seo_form = ProductSEOForm(prefix='seo', instance=product)

    # Определяем выбранный каталог
    catalog_instance = None
    product_form_valid = None
    seo_form_valid = None

    if request.method == 'POST':
        product_form_valid = product_form.is_valid()
        if product_form_valid:
            catalog_instance = product_form.cleaned_data.get('catalog')
        else:
            catalog_id = product_form.data.get('product-catalog')
            if catalog_id:
                catalog_instance = Catalog.objects.filter(pk=catalog_id).first()
    else:
        catalog_id = request.GET.get('catalog')
        if product.catalog_id:
            catalog_instance = product.catalog
        elif catalog_id:
            catalog_instance = Catalog.objects.filter(pk=catalog_id).first()

    # Сетка размеров
    size_grid_instance = None
    if getattr(product, 'size_grid_id', None):
        size_grid_instance = product.size_grid
    elif catalog_instance:
        size_grid_instance = catalog_instance.size_grids.filter(is_active=True).order_by('order', 'name').first()

    if request.method == 'POST':
        size_grid_base_instance = size_grid_instance
        if size_grid_base_instance is None and catalog_instance:
            size_grid_base_instance = SizeGrid(catalog=catalog_instance)
        size_grid_form = SizeGridForm(
            data=request.POST,
            files=request.FILES,
            prefix='size_grid',
            instance=size_grid_base_instance
        )
        size_grid_form_used = size_grid_form.has_changed()
        size_grid_form_valid = True
        if size_grid_form_used:
            size_grid_form_valid = size_grid_form.is_valid()
            size_grid_requires_catalog = (
                size_grid_form_valid
                and not getattr(size_grid_form.instance, 'catalog_id', None)
                and catalog_instance is None
            )
            if size_grid_requires_catalog:
                size_grid_form.add_error(None, 'Оберіть каталог перед збереженням сітки розмірів.')
                size_grid_form_valid = False
    else:
        size_grid_form = SizeGridForm(prefix='size_grid', instance=size_grid_instance)
        size_grid_form_used = False
        size_grid_form_valid = True

    # Цвета и изображения
    color_formset = build_color_variant_formset(
        product=product,
        data=request.POST if request.method == 'POST' else None,
        files=request.FILES if request.method == 'POST' else None,
        prefix='color_variants'
    )

    option_formset = None
    option_formset_valid = True
    option_formset_has_changes = False
    if catalog_instance:
        if request.method == 'POST':
            option_formset = CatalogOptionFormSet(
                data=request.POST,
                prefix='catalog-options',
                instance=catalog_instance
            )
            option_formset_valid = option_formset.is_valid()
            option_formset_has_changes = any(form.has_changed() for form in option_formset.forms) or bool(option_formset.deleted_forms)
        else:
            option_formset = CatalogOptionFormSet(
                prefix='catalog-options',
                instance=catalog_instance
            )

    catalogs = Catalog.objects.filter(is_active=True).order_by('order', 'name')

    if request.method == 'POST':
        if product_form_valid is None:
            product_form_valid = product_form.is_valid()

        seo_form_valid = seo_form.is_valid()
        color_formset_valid = color_formset.is_valid()

        images_valid = True
        for variant_form in color_formset.forms:
            images_formset = getattr(variant_form, 'images_formset', None)
            if images_formset is not None:
                if not images_formset.is_valid():
                    images_valid = False

        if product_form_valid and seo_form_valid and color_formset_valid and images_valid and size_grid_form_valid and option_formset_valid:
            with transaction.atomic():
                product_obj = product_form.save(commit=False)
                # Генерация slug, если не задан або змінено
                desired_slug = product_obj.slug or slugify(product_obj.title or '')
                if product_obj.pk:
                    if original_slug and desired_slug == original_slug:
                        product_obj.slug = original_slug
                    else:
                        product_obj.slug = unique_slugify(Product, desired_slug)
                else:
                    product_obj.slug = unique_slugify(Product, desired_slug)
                product_obj.status = product_obj.status or ProductStatus.DRAFT

                # Обработка size grid
                size_grid_obj = product_form.cleaned_data.get('size_grid')
                if size_grid_form_used and size_grid_form_valid:
                    temp_grid = size_grid_form.save(commit=False)
                    grid_catalog = temp_grid.catalog or catalog_instance or product_form.cleaned_data.get('catalog')
                    if grid_catalog:
                        temp_grid.catalog = grid_catalog
                        temp_grid.save()
                        size_grid_obj = temp_grid
                elif size_grid_obj and not size_grid_obj.catalog_id and catalog_instance:
                    size_grid_obj.catalog = catalog_instance
                    size_grid_obj.save(update_fields=['catalog'])

                product_obj.size_grid = size_grid_obj
                product_obj.save()
                product_form.save_m2m()

                # SEO поля
                seo_form.instance = product_obj
                seo_form.save()

                # Работа с цветовыми вариантами
                saved_variants = []
                default_assigned = False

                for variant_form in color_formset.forms:
                    if not hasattr(variant_form, 'cleaned_data'):
                        continue

                    if variant_form.cleaned_data.get('DELETE'):
                        if variant_form.instance.pk:
                            variant_form.instance.delete()
                        continue

                    images_formset = getattr(variant_form, 'images_formset', None)
                    images_changed = images_formset.has_changed() if images_formset is not None else False

                    if (
                        not variant_form.cleaned_data
                        or (
                            not variant_form.has_changed()
                            and not images_changed
                            and not variant_form.instance.pk
                        )
                    ):
                        continue

                    variant = variant_form.save(commit=False)
                    variant.product = product_obj

                    if variant.is_default:
                        if default_assigned:
                            variant.is_default = False
                        else:
                            default_assigned = True

                    if variant.order is None:
                        variant.order = 0

                    variant.save()
                    saved_variants.append(variant)

                    if images_formset is not None:
                        images_formset.instance = variant
                        payloads = formset_to_variant_payloads(images_formset)
                        if payloads:
                            sync_variant_images(variant, payloads)

                # Если нет варианта по умолчанию — назначаем первый
                if not default_assigned and saved_variants:
                    primary_variant = saved_variants[0]
                    if not primary_variant.is_default:
                        primary_variant.is_default = True
                        primary_variant.save(update_fields=['is_default'])

                # Дополнительные изображения товара
                extra_images = product_form.cleaned_data.get('extra_images') or []
                append_product_gallery(product_obj, extra_images)

                # Сохранение опций каталога
                if option_formset is not None and option_formset.is_bound and option_formset_valid and option_formset_has_changes:
                    option_formset.save()

                messages.success(request, 'Товар успішно збережено.')
                return redirect('admin_product_builder_edit', product_id=product_obj.pk)
        else:
            messages.error(request, 'Перевірте форму — знайдені помилки.')

    def _extract_value(form, field_name, valid_flag):
        if not form:
            return None
        if form.is_bound:
            if valid_flag is False:
                return None
            if valid_flag is True and hasattr(form, 'cleaned_data'):
                return form.cleaned_data.get(field_name)
            return form.data.get(f'{form.prefix}-{field_name}')
        if form.instance is not None and hasattr(form.instance, field_name):
            return getattr(form.instance, field_name)
        return None

    def _colors_complete():
        if color_formset.is_bound:
            for form in color_formset.forms:
                if getattr(form, 'cleaned_data', None) and form.cleaned_data.get('DELETE'):
                    continue
                if form.has_changed() or getattr(form.instance, 'pk', None):
                    return True
            return False
        if product.pk:
            return product.color_variants.exists()
        return False

    basic_complete = all(
        bool(_extract_value(product_form, field, product_form_valid))
        for field in ('title', 'category', 'price')
    )
    catalog_complete = bool(_extract_value(product_form, 'catalog', product_form_valid))
    colors_complete = _colors_complete()
    seo_complete = any(
        bool(_extract_value(seo_form, field, seo_form_valid))
        for field in ('seo_title', 'seo_description', 'seo_keywords')
    )
    status_value = _extract_value(product_form, 'status', product_form_valid)
    preview_complete = bool(
        status_value and status_value != ProductStatus.DRAFT
    )

    progress_steps = {
        'basic': basic_complete,
        'catalog': catalog_complete,
        'colors': colors_complete,
        'seo': seo_complete,
        'preview': preview_complete,
    }
    total_steps = len(progress_steps)
    completed_steps = sum(1 for completed in progress_steps.values() if completed)
    progress_percent = int(round((completed_steps / total_steps) * 100)) if total_steps else 0

    builder_progress = {
        'steps': progress_steps,
        'completed': completed_steps,
        'total': total_steps,
        'percent': progress_percent,
    }

    context = {
        'product': product if product.pk else None,
        'product_form': product_form,
        'seo_form': seo_form,
        'size_grid_form': size_grid_form,
        'color_formset': color_formset,
        'option_formset': option_formset,
        'catalogs': catalogs,
        'selected_catalog': catalog_instance,
        'is_new': is_new,
        'builder_progress': builder_progress,
    }

    return render(request, 'pages/product_builder.html', context)


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
