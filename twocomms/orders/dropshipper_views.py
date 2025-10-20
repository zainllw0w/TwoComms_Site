from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from decimal import Decimal, ROUND_HALF_UP
import json

from .models import DropshipperOrder, DropshipperOrderItem, DropshipperStats, DropshipperPayout
from storefront.models import Product, Category
from productcolors.models import ProductColorVariant
from .forms import CompanyProfileForm
from accounts.models import UserProfile


LONG_SLEEVE_SLUG = 'long-sleeve'


def _get_dropship_categories():
    categories_data = []
    for category in Category.objects.filter(is_active=True).order_by('order', 'name'):
        is_disabled = category.slug == LONG_SLEEVE_SLUG
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'disabled': is_disabled,
        })
    return categories_data


def _format_color_count(count):
    if not count:
        return '1 колір (чорний)'
    if count == 1:
        return '1 колір'
    if 2 <= count <= 4:
        return f'{count} кольори'
    return f'{count} кольорів'


def _dropshipper_products_queryset():
    return (
        Product.objects.filter(
            category__is_active=True,
            is_dropship_available=True,
        )
        .exclude(category__slug=LONG_SLEEVE_SLUG)
        .select_related('category')
        .prefetch_related('color_variants__images')
    )


def _enrich_product(product, dropshipper=None):
    recommended = product.get_recommended_price()
    base_price = recommended.get('base', product.recommended_price or product.price)
    drop_price = product.get_drop_price(dropshipper)

    product.recommended_price_info = recommended
    product.recommended_base_price = int(base_price)
    product.dropship_margin = max(int(base_price) - int(drop_price), 0)
    product.drop_price_value = int(drop_price)

    image = product.display_image
    product.primary_image = image
    product.primary_image_url = getattr(image, 'url', None)

    color_count = product.color_variants.count()
    product.color_count_label = _format_color_count(color_count)
    return product


def _build_products_context(request, *, per_page=12):
    category_id = request.GET.get('category') or None
    search_query = (request.GET.get('search') or '').strip()

    products_qs = _dropshipper_products_queryset()

    if category_id:
        products_qs = products_qs.filter(category_id=category_id)

    if search_query:
        products_qs = products_qs.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    products_qs = products_qs.order_by('-id')

    paginator = Paginator(products_qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    enriched = [_enrich_product(product, request.user) for product in page_obj.object_list]
    page_obj.object_list = enriched

    categories = _get_dropship_categories()
    inactive_categories = [category for category in categories if category['disabled']]

    return {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'search_query': search_query,
        'inactive_categories': inactive_categories,
    }


def dropshipper_dashboard(request):
    """Главная страница дропшипера с вкладками"""
    # Если пользователь не авторизован, показываем приветственную страницу
    if not request.user.is_authenticated:
        return render(request, 'pages/dropshipper_welcome.html')
    
    # Получаем или создаем статистику дропшипера
    stats, created = DropshipperStats.objects.get_or_create(dropshipper=request.user)
    if not created:
        stats.update_stats()
    
    # Получаем последние заказы
    recent_orders = DropshipperOrder.objects.filter(dropshipper=request.user).order_by('-created_at')[:5]
    
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    products_preview = [
        _enrich_product(product, request.user)
        for product in _dropshipper_products_queryset().order_by('-id')[:8]
    ]

    categories_info = _get_dropship_categories()
    active_categories_count = sum(1 for category in categories_info if not category['disabled'])
    inactive_categories = [category for category in categories_info if category['disabled']]

    context = {
        'stats': stats,
        'recent_orders': recent_orders,
        'payout_methods': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'payment_method_choices': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'profile': profile,
        'dropship_products_preview': products_preview,
        'dropship_products_categories_count': active_categories_count,
        'dropship_inactive_categories': inactive_categories,
    }
    
    return render(request, 'pages/dropshipper_dashboard.html', context)


@login_required
def dropshipper_products(request):
    """Страница с товарами для дропшиперов"""
    products_context = _build_products_context(request, per_page=12)
    
    context = {
        **products_context,
        'payout_methods': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'payment_method_choices': DropshipperPayout.PAYMENT_METHOD_CHOICES,
    }

    template_name = 'pages/dropshipper_products.html'
    if request.GET.get('partial'):
        template_name = 'partials/dropshipper_products_panel.html'
    
    return render(request, template_name, context)


@login_required
def dropshipper_orders(request):
    """Страница с заказами дропшипера"""
    status_filter = request.GET.get('status', '')
    
    # Базовый queryset
    orders = DropshipperOrder.objects.filter(dropshipper=request.user).prefetch_related('items__product')
    print(f"=== ОТЛАДКА ЗАКАЗОВ ===")
    print(f"Пользователь: {request.user.username} (ID: {request.user.id})")
    print(f"Всего заказов в БД: {orders.count()}")
    
    # Выводим все заказы для отладки
    for order in orders:
        print(f"Заказ {order.id}: {order.order_number}, статус: {order.status}, клиент: {order.client_name}")
    
    # Фильтрация по статусу
    if status_filter:
        orders = orders.filter(status=status_filter)
        print(f"После фильтрации по статусу '{status_filter}': {orders.count()} заказов")
    
    # Пагинация
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    print(f"Пагинация: страница {page_number}, всего страниц: {paginator.num_pages}, заказов на странице: {len(page_obj)}")
    print(f"page_obj.object_list содержит: {len(page_obj.object_list)} заказов")
    
    # Проверяем каждый заказ в page_obj
    for i, order in enumerate(page_obj.object_list):
        print(f"page_obj[{i}]: {order.order_number} (статус: {order.status})")
    
    context = {
        'page_obj': page_obj,
        'status_choices': DropshipperOrder.STATUS_CHOICES,
        'selected_status': status_filter,
        'payout_methods': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'payment_method_choices': DropshipperPayout.PAYMENT_METHOD_CHOICES,
    }
    
    print(f"Контекст: page_obj содержит {len(page_obj)} заказов")
    print(f"page_obj.has_other_pages: {page_obj.has_other_pages()}")
    print(f"page_obj.number: {page_obj.number}")
    print(f"page_obj.paginator.count: {page_obj.paginator.count}")
    print("=== КОНЕЦ ОТЛАДКИ ===")

    template_name = 'pages/dropshipper_orders.html'
    if request.GET.get('partial'):
        template_name = 'partials/dropshipper_orders_panel.html'
    
    return render(request, template_name, context)


@login_required
def dropshipper_statistics(request):
    """Страница со статистикой дропшипера"""
    # Получаем статистику
    stats, created = DropshipperStats.objects.get_or_create(dropshipper=request.user)
    if not created:
        stats.update_stats()
    
    # Получаем статистику по месяцам
    monthly_stats = DropshipperOrder.objects.filter(
        dropshipper=request.user,
        status='delivered'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        orders_count=Count('id'),
        total_revenue=Sum('total_selling_price'),
        total_profit=Sum('profit')
    ).order_by('month')
    
    # Получаем топ товаров
    top_products = DropshipperOrderItem.objects.filter(
        order__dropshipper=request.user,
        order__status='delivered'
    ).values('product__title').annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total_selling_price')
    ).order_by('-total_sold')[:10]
    
    average_order_value = Decimal('0')
    if stats.completed_orders:
        average_order_value = (stats.total_revenue / stats.completed_orders).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    delivery_rate = Decimal('0')
    if stats.total_orders:
        delivery_rate = (Decimal(stats.completed_orders) / Decimal(stats.total_orders) * Decimal('100')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

    context = {
        'stats': stats,
        'monthly_stats': monthly_stats,
        'top_products': top_products,
        'average_order_value': average_order_value,
        'delivery_rate': delivery_rate,
        'payout_methods': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'payment_method_choices': DropshipperPayout.PAYMENT_METHOD_CHOICES,
    }

    template_name = 'pages/dropshipper_statistics.html'
    if request.GET.get('partial'):
        template_name = 'partials/dropshipper_statistics_panel.html'
    
    return render(request, template_name, context)


@login_required
def dropshipper_payouts(request):
    """Страница с выплатами дропшипера"""
    # Получаем выплаты
    payouts = DropshipperPayout.objects.filter(dropshipper=request.user).prefetch_related('included_orders')
    
    # Пагинация
    paginator = Paginator(payouts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем доступную сумму для выплаты
    available_amount = DropshipperOrder.objects.filter(
        dropshipper=request.user,
        status='delivered',
        payment_status='paid',
        payouts__isnull=True
    ).aggregate(total=Sum('profit'))['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'available_amount': available_amount,
        'status_choices': DropshipperPayout.STATUS_CHOICES,
        'payment_method_choices': DropshipperPayout.PAYMENT_METHOD_CHOICES,
        'payout_methods': DropshipperPayout.PAYMENT_METHOD_CHOICES,
    }

    template_name = 'pages/dropshipper_payouts.html'
    if request.GET.get('partial'):
        template_name = 'partials/dropshipper_payouts_panel.html'
    
    return render(request, template_name, context)


@login_required
def dropshipper_company_settings(request):
    """Вкладка для редагування компанії"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    initial = {
        'company_name': profile.company_name or '',
        'company_number': profile.company_number or '',
        'phone': profile.phone or request.user.username,
        'email': profile.email or request.user.email or '',
        'website': profile.website or '',
        'instagram': profile.instagram or '',
        'telegram': profile.telegram or '',
        'payment_details': profile.payment_details or '',
    }

    form = CompanyProfileForm(request.POST or None, request.FILES or None, initial=initial)

    if request.method == 'POST':
        if form.is_valid():
            profile.company_name = form.cleaned_data.get('company_name', '').strip()
            profile.company_number = form.cleaned_data.get('company_number', '').strip()
            profile.phone = form.cleaned_data.get('phone', '').strip()
            profile.email = form.cleaned_data.get('email', '').strip()
            profile.website = form.cleaned_data.get('website', '').strip()
            profile.instagram = form.cleaned_data.get('instagram', '').strip()
            profile.telegram = form.cleaned_data.get('telegram', '').strip()
            profile.payment_details = form.cleaned_data.get('payment_details', '').strip()

            avatar = form.cleaned_data.get('avatar')
            if avatar:
                profile.avatar = avatar

            profile.save()

            # Синхронізуємо email у User
            email = form.cleaned_data.get('email')
            if email and email != request.user.email:
                request.user.email = email
                request.user.save(update_fields=['email'])

            summary = {
                'company_name': profile.company_name or '',
                'company_number': profile.company_number or '',
                'phone': profile.phone or request.user.username,
                'email': profile.email or request.user.email or '',
                'website': profile.website or '',
                'instagram': profile.instagram or '',
                'telegram': profile.telegram or '',
                'payment_details': profile.payment_details or '',
                'has_company': bool(profile.company_name),
            }

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Дані компанії оновлено',
                    'profile': summary,
                })

            messages.success(request, 'Дані компанії оновлено')
            return redirect('orders:dropshipper_dashboard')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=422)

    if request.GET.get('partial') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'partials/dropshipper_company_panel.html', {'form': form, 'profile': profile})

    return redirect('orders:dropshipper_dashboard')


@login_required
@require_http_methods(["POST"])
def add_to_cart(request):
    """Добавление товара в корзину"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        color_variant_id = data.get('color_variant_id')
        size = data.get('size', '')
        quantity = int(data.get('quantity', 1))
        selling_price = data.get('selling_price')
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'message': 'ID товара обязателен'
            })
        
        product = get_object_or_404(Product, id=product_id)
        color_variant = None
        
        if color_variant_id:
            color_variant = get_object_or_404(ProductColorVariant, id=color_variant_id)
        
        # Получаем актуальную цену дропа
        actual_drop_price = product.get_drop_price(request.user)
        
        # Сохраняем в сессии
        cart = request.session.get('dropshipper_cart', [])
        
        # Проверяем, есть ли уже такой товар в корзине
        existing_item = None
        for item in cart:
            if (item.get('product_id') == product_id and 
                item.get('color_variant_id') == color_variant_id and 
                item.get('size') == size):
                existing_item = item
                break
        
        if existing_item:
            existing_item['quantity'] += quantity
        else:
            cart.append({
                'product_id': product_id,
                'color_variant_id': color_variant_id,
                'size': size,
                'quantity': quantity,
                'drop_price': actual_drop_price,
                'selling_price': selling_price or product.recommended_price,
                'product_title': product.title,
                'color_name': color_variant.name if color_variant else 'Базовий колір'
            })
        
        request.session['dropshipper_cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': 'Товар додано до корзини',
            'cart_count': len(cart)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при додаванні товару: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def get_cart(request):
    """Получение содержимого корзины"""
    cart = request.session.get('dropshipper_cart', [])
    return JsonResponse({
        'success': True,
        'cart': cart,
        'cart_count': len(cart)
    })


@login_required
@require_http_methods(["POST"])
def remove_from_cart(request):
    """Удаление товара из корзины"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        color_variant_id = data.get('color_variant_id')
        size = data.get('size', '')
        
        cart = request.session.get('dropshipper_cart', [])
        cart = [item for item in cart if not (
            item.get('product_id') == product_id and 
            item.get('color_variant_id') == color_variant_id and 
            item.get('size') == size
        )]
        
        request.session['dropshipper_cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': 'Товар видалено з корзини',
            'cart_count': len(cart)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при видаленні товару: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def clear_cart(request):
    """Очистка корзины"""
    request.session['dropshipper_cart'] = []
    request.session.modified = True
    
    return JsonResponse({
        'success': True,
        'message': 'Корзина очищена'
    })


@login_required
@require_http_methods(["POST"])
def create_dropshipper_order(request):
    """Создание нового заказа дропшипера из корзины"""
    try:
        data = json.loads(request.body)
        print(f"Создаем заказ для пользователя {request.user.id}: {data}")
        
        # Получаем корзину из сессии
        cart = request.session.get('dropshipper_cart', [])
        
        if not cart:
            return JsonResponse({
                'success': False,
                'message': 'Корзина пуста. Добавьте товары перед созданием заказа.'
            })
        
        with transaction.atomic():
            # Создаем заказ
            order = DropshipperOrder.objects.create(
                dropshipper=request.user,
                client_name=data.get('client_name', ''),
                client_phone=data.get('client_phone', ''),
                client_np_address=data.get('client_np_address', ''),
                notes=data.get('notes', ''),
                status='pending'  # Изменяем статус на pending для отображения
            )
            
            # Добавляем товары из корзины
            total_drop_price = 0
            total_selling_price = 0
            
            for item_data in cart:
                product = get_object_or_404(Product, id=item_data['product_id'])
                color_variant = None
                
                if item_data.get('color_variant_id'):
                    color_variant = get_object_or_404(ProductColorVariant, id=item_data['color_variant_id'])
                
                order_item = DropshipperOrderItem.objects.create(
                    order=order,
                    product=product,
                    color_variant=color_variant,
                    size=item_data.get('size', ''),
                    quantity=item_data.get('quantity', 1),
                    drop_price=item_data.get('drop_price', 0),
                    selling_price=item_data.get('selling_price', 0),
                    recommended_price=product.recommended_price
                )
                
                print(f"Создан элемент заказа: {order_item.product.title}, количество: {order_item.quantity}, цена дропа: {order_item.drop_price}, цена продажи: {order_item.selling_price}")
                
                total_drop_price += order_item.total_drop_price
                total_selling_price += order_item.total_selling_price
            
            # Обновляем итоговые суммы заказа
            order.total_drop_price = total_drop_price
            order.total_selling_price = total_selling_price
            order.profit = total_selling_price - total_drop_price
            order.save()
            
            # Очищаем корзину после создания заказа
            request.session['dropshipper_cart'] = []
            request.session.modified = True
            
            print(f"Заказ создан: ID={order.id}, номер={order.order_number}")
            
            return JsonResponse({
                'success': True,
                'order_id': order.id,
                'order_number': order.order_number,
                'message': 'Замовлення успішно створено!'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при створенні замовлення: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def update_order_status(request, order_id):
    """Обновление статуса заказа"""
    order = get_object_or_404(DropshipperOrder, id=order_id, dropshipper=request.user)
    
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status in [choice[0] for choice in DropshipperOrder.STATUS_CHOICES]:
            order.status = new_status
            order.save()
            
            # Обновляем статистику
            stats, created = DropshipperStats.objects.get_or_create(dropshipper=request.user)
            stats.update_stats()
            
            return JsonResponse({
                'success': True,
                'message': 'Статус замовлення оновлено!'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Невірний статус!'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при оновленні статусу: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def request_payout(request):
    """Запрос на выплату"""
    try:
        data = json.loads(request.body)
        
        # Получаем доступные заказы для выплаты
        available_orders = DropshipperOrder.objects.filter(
            dropshipper=request.user,
            status='delivered',
            payment_status='paid',
            payouts__isnull=True
        )
        
        if not available_orders.exists():
            return JsonResponse({
                'success': False,
                'message': 'Немає доступних замовлень для виплати!'
            })
        
        # Рассчитываем сумму выплаты
        total_amount = sum(order.profit for order in available_orders)
        
        with transaction.atomic():
            # Создаем выплату
            payout = DropshipperPayout.objects.create(
                dropshipper=request.user,
                amount=total_amount,
                payment_method=data.get('payment_method', 'card'),
                payment_details=data.get('payment_details', ''),
                notes=data.get('notes', ''),
                status='pending'
            )
            
            # Связываем заказы с выплатой
            payout.included_orders.set(available_orders)
            
            return JsonResponse({
                'success': True,
                'payout_id': payout.id,
                'payout_number': payout.payout_number,
                'amount': float(total_amount),
                'message': 'Запит на виплату створено!'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при створенні запиту на виплату: {str(e)}'
        })


@login_required
def get_product_details(request, product_id):
    """Получение детальной информации о товаре"""
    try:
        product = get_object_or_404(Product.objects.select_related('category'), id=product_id)
        color_variants = ProductColorVariant.objects.filter(product=product).prefetch_related('images', 'color')

        sizes = []
        for variant in color_variants:
            variant_sizes = getattr(variant, 'sizes', '') or ''
            if variant_sizes:
                sizes.extend([size.strip() for size in variant_sizes.split(',') if size.strip()])

        unique_sizes = sorted(set(sizes))

        recommended = product.get_recommended_price()
        drop_price = product.get_drop_price()

        base_images = []
        if product.main_image:
            base_images.append(product.main_image.url)

        color_variants_payload = []
        for variant in color_variants:
            variant_images = [img.image.url for img in variant.images.all()]
            if variant_images:
                base_images.extend(variant_images)

            color_variants_payload.append({
                'id': variant.id,
                'color_name': variant.color.name if variant.color else 'Без кольору',
                'primary_hex': variant.color.primary_hex if variant.color and variant.color.primary_hex else '#000000',
                'images': variant_images,
            })

        gallery = []
        seen = set()
        for url in base_images:
            if url and url not in seen:
                gallery.append(url)
                seen.add(url)

        data = {
            'id': product.id,
            'title': product.title,
            'description': product.description or '',
            'drop_price': float(drop_price),
            'recommended_price': float(recommended.get('base', product.recommended_price or 0)),
            'recommended_min': float(recommended.get('min', product.recommended_price or 0)),
            'recommended_max': float(recommended.get('max', product.recommended_price or 0)),
            'main_image': gallery[0] if gallery else None,
            'gallery': gallery,
            'color_variants': color_variants_payload,
            'sizes': unique_sizes,
            'available_for_order': product.is_available_for_dropship(),
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({
            'error': f'Помилка при отриманні інформації про товар: {str(e)}'
        }, status=400)


@login_required
@require_http_methods(["GET"])
def get_product_details(request, product_id):
    """Получение детальной информации о товаре для модального окна"""
    try:
        product = get_object_or_404(Product, id=product_id)
        
        # Получаем актуальную цену дропа
        drop_price = product.get_drop_price(request.user)
        
        # Получаем варианты цветов
        color_variants = []
        for variant in product.color_variants.all():
            color_variants.append({
                'id': variant.id,
                'name': variant.name,
                'color_code': variant.color_code
            })
        
        # Формируем ответ
        product_data = {
            'id': product.id,
            'title': product.title,
            'description': product.description,
            'primary_image_url': product.primary_image_url,
            'drop_price': float(drop_price),
            'recommended_price': float(product.recommended_price),
            'color_variants': color_variants,
            'category': {
                'id': product.category.id,
                'name': product.category.name
            }
        }
        
        return JsonResponse({
            'success': True,
            'product': product_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при завантаженні товару: {str(e)}'
        })
