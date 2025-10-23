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


def _build_products_context(request, *, per_page=None):
    """
    Строит контекст для каталога товаров дропшипера.
    Если per_page=None, показываются все товары без пагинации.
    """
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

    # Если per_page не указан, показываем все товары
    if per_page is None:
        all_products = list(products_qs)
        enriched = [_enrich_product(product, request.user) for product in all_products]
        
        categories = _get_dropship_categories()
        inactive_categories = [category for category in categories if category['disabled']]
        
        return {
            'products': enriched,
            'total_count': len(enriched),
            'categories': categories,
            'selected_category': category_id,
            'search_query': search_query,
            'inactive_categories': inactive_categories,
        }
    
    # Старый код с пагинацией (для совместимости)
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
    
    # Получаем общее количество заказов
    total_orders_count = DropshipperOrder.objects.filter(dropshipper=request.user).count()
    
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
        'total_orders_count': total_orders_count,
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
    """Страница с товарами для дропшиперов - показываем все товары без пагинации"""
    products_context = _build_products_context(request, per_page=None)  # per_page=None показывает все товары
    
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
    """Добавление товара в корзину с данными клиента"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        color_variant_id = data.get('color_variant_id')
        size = data.get('size', '')
        quantity = int(data.get('quantity', 1))
        selling_price = data.get('selling_price')
        
        # Данные клиента
        client_name = data.get('client_name', '').strip()
        client_phone = data.get('client_phone', '').strip()
        client_city = data.get('client_city', '').strip()
        client_np_office = data.get('client_np_office', '').strip()
        order_source = data.get('order_source', '').strip()
        notes = data.get('notes', '').strip()
        payment_method = data.get('payment_method', 'cod')  # Способ оплаты
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'message': 'ID товара обязателен'
            })
        
        # Проверяем обязательные поля клиента
        if not all([client_name, client_phone, client_city, client_np_office]):
            return JsonResponse({
                'success': False,
                'message': 'Заповніть всі обов\'язкові поля клієнта'
            })
        
        product = get_object_or_404(Product, id=product_id)
        color_variant = None
        
        if color_variant_id:
            color_variant = get_object_or_404(ProductColorVariant, id=color_variant_id)
        
        # Получаем актуальную цену дропа
        actual_drop_price = product.get_drop_price(request.user)
        
        # Формируем адрес доставки
        client_np_address = f"{client_city}, {client_np_office}"
        
        # Создаем заказ сразу (новая логика - не используем корзину)
        with transaction.atomic():
            order = DropshipperOrder.objects.create(
                dropshipper=request.user,
                client_name=client_name,
                client_phone=client_phone,
                client_np_address=client_np_address,
                order_source=order_source,
                notes=notes,
                payment_method=payment_method,
                status='pending'
            )
            
            # Добавляем товар в заказ
            order_item = DropshipperOrderItem.objects.create(
                order=order,
                product=product,
                color_variant=color_variant,
                size=size,
                quantity=quantity,
                drop_price=actual_drop_price,
                selling_price=selling_price or product.recommended_price,
                recommended_price=product.recommended_price
            )
            
            # Обновляем итоговые суммы
            order.total_drop_price = order_item.total_drop_price
            order.total_selling_price = order_item.total_selling_price
            order.profit = order.total_selling_price - order.total_drop_price
            
            # Рассчитываем платеж дропшипера в зависимости от способа оплаты
            order.calculate_dropshipper_payment()
            
            order.save()
            
            # Отправляем уведомление в Telegram админу
            try:
                from .telegram_notifications import telegram_notifier
                telegram_notifier.send_dropshipper_order_notification(order)
                print(f"✅ Telegram уведомление отправлено для заказа {order.order_number}")
            except Exception as e:
                # Не прерываем создание заказа если Telegram не работает
                print(f"⚠️ Ошибка отправки Telegram уведомления: {e}")
        
        # Проверяем требуется ли оплата
        requires_payment = order.payment_method in ['prepaid', 'cod']
        payment_amount = None
        if order.payment_method == 'prepaid':
            payment_amount = float(order.total_drop_price)
        elif order.payment_method == 'cod':
            payment_amount = 200.00
        
        return JsonResponse({
            'success': True,
            'message': 'Замовлення створено!',
            'order_id': order.id,
            'order_number': order.order_number,
            'requires_payment': requires_payment,
            'payment_amount': payment_amount,
            'payment_method': order.payment_method
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Помилка при створенні замовлення: {str(e)}'
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
            # Получаем способ оплаты
            payment_method = data.get('payment_method', 'cod')  # По умолчанию - наложенный платеж
            
            # Создаем заказ
            order = DropshipperOrder.objects.create(
                dropshipper=request.user,
                client_name=data.get('client_name', ''),
                client_phone=data.get('client_phone', ''),
                client_np_address=data.get('client_np_address', ''),
                order_source=data.get('order_source', ''),
                notes=data.get('notes', ''),
                payment_method=payment_method,
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
            
            # Рассчитываем сумму, которую должен оплатить дропшипер
            order.calculate_dropshipper_payment()
            
            order.save()
            
            # Отправляем уведомление в Telegram админу
            try:
                from .telegram_notifications import telegram_notifier
                telegram_notifier.send_dropshipper_order_notification(order)
                print(f"Telegram уведомление админу отправлено для заказа {order.order_number}")
            except Exception as e:
                # Не прерываем создание заказа если Telegram не работает
                print(f"Ошибка отправки Telegram уведомления админу: {e}")
            
            # Отправляем уведомление дропшиперу
            try:
                from .telegram_notifications import telegram_notifier
                telegram_notifier.send_dropshipper_order_created_notification(order)
                print(f"✅ Telegram уведомление дропшиперу отправлено для заказа {order.order_number}")
            except Exception as e:
                # Не прерываем создание заказа если Telegram не работает
                print(f"⚠️ Ошибка отправки Telegram уведомления дропшиперу: {e}")
            
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
@require_http_methods(["GET"])
def get_product_details(request, product_id):
    """Получение детальной информации о товаре для модального окна"""
    try:
        product = get_object_or_404(Product, id=product_id)
        
        # Получаем актуальную цену дропа
        drop_price = product.get_drop_price(request.user)
        
        # Получаем рекомендованную цену (как на сайте)
        recommended = product.get_recommended_price()
        recommended_price = recommended.get('base', product.price)
        price_range = {
            'min': recommended.get('min', int(recommended_price * 0.9)),
            'max': recommended.get('max', int(recommended_price * 1.1))
        }
        
        # Получаем варианты цветов
        color_variants = []
        for variant in product.color_variants.all():
            color_name = variant.color.name if variant.color.name else str(variant.color)
            color_variants.append({
                'id': variant.id,
                'name': color_name,
                'color_code': variant.color.primary_hex,
                'secondary_color_code': variant.color.secondary_hex if variant.color.secondary_hex else None
            })
        
        # Получаем основное изображение товара
        main_image_url = None
        if product.main_image:
            main_image_url = product.main_image.url
        elif product.color_variants.exists():
            # Если нет основного изображения, берем первое из вариантов цветов
            first_variant = product.color_variants.first()
            if first_variant and hasattr(first_variant, 'images') and first_variant.images.exists():
                main_image_url = first_variant.images.first().image.url
        
        # Формируем ответ
        product_data = {
            'id': product.id,
            'title': product.title,
            'description': product.description or '',
            'primary_image_url': main_image_url,
            'drop_price': float(drop_price),
            'recommended_price': float(recommended_price),
            'price_range': price_range,  # Добавляем диапазон цены
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


# =============================================================================
# MONOBANK ОПЛАТА ДЛЯ ДРОПШИПЕРОВ
# =============================================================================

import logging
from django.conf import settings
import requests

monobank_logger = logging.getLogger('monobank')


class MonobankAPIError(Exception):
    """Ошибка API Monobank"""
    pass


def _monobank_api_request(method, endpoint, json_payload=None):
    """Выполнить запрос к API Monobank"""
    token = getattr(settings, 'MONOBANK_TOKEN', None)
    if not token:
        raise MonobankAPIError('Monobank API token не налаштований')
    
    base_url = getattr(settings, 'MONOBANK_API_BASE', 'https://api.monobank.ua').rstrip('/')
    url = f"{base_url}{endpoint}"
    
    headers = {
        'X-Token': token,
        'Content-Type': 'application/json'
    }
    
    monobank_logger.info(f'Monobank API request: {method} {endpoint}, payload: {json_payload}')
    
    try:
        if method == 'POST':
            response = requests.post(url, json=json_payload, headers=headers, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        
        data = response.json()
        monobank_logger.info(f'Monobank API response: status={response.status_code}, data={data}')
        
        response.raise_for_status()
        return data
    except requests.exceptions.RequestException as e:
        monobank_logger.error(f'Monobank API error: {e}')
        raise MonobankAPIError(f'Помилка з\'єднання з Monobank: {str(e)}')


@login_required
@require_http_methods(["POST"])
def create_dropshipper_monobank_payment(request):
    """Создать платеж Monobank для дропшипера"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        if not order_id:
            return JsonResponse({
                'success': False,
                'error': 'ID замовлення не вказано'
            })
        
        # Получаем заказ
        order = get_object_or_404(DropshipperOrder, id=order_id, dropshipper=request.user)
        
        # Проверяем что заказ требует оплаты
        if order.payment_method == 'delegation':
            return JsonResponse({
                'success': False,
                'error': 'Це замовлення не потребує оплати (повне делегування)'
            })
        
        # Определяем сумму к оплате и тип платежа
        if order.payment_method == 'prepaid':
            amount = order.total_drop_price
            payment_type = 'Повна оплата дропшипу'
            description = f"Повна оплата дропшипу #{order.order_number}"
        elif order.payment_method == 'cod':
            amount = Decimal('200.00')
            payment_type = 'Передоплата дропшипу'
            description = f"Передоплата 200 грн за дропшип #{order.order_number}"
        else:
            return JsonResponse({
                'success': False,
                'error': 'Невідомий спосіб оплати'
            })
        
        # Формируем корзину товаров для Monobank (с фото, размерами и правильными суммами)
        basket_entries = []
        items_qs = list(order.items.select_related('product', 'color_variant__color').all())
        
        for item in items_qs:
            # Формируем название: Товар • розмір X • колір
            name_parts = [item.product.title]
            if item.size:
                name_parts.append(f"розмір {item.size}")
            if item.color_variant and item.color_variant.color:
                name_parts.append(item.color_variant.color.name)
            display_name = ' • '.join(filter(None, name_parts))[:128]
            
            # Получаем фото товара
            icon_url = ''
            try:
                image_obj = None
                if item.color_variant and item.color_variant.images.exists():
                    image_obj = item.color_variant.images.first().image
                elif item.product.main_image:
                    image_obj = item.product.main_image
                if image_obj and hasattr(image_obj, 'url'):
                    icon_url = request.build_absolute_uri(image_obj.url)
                    if icon_url.startswith('http://'):
                        icon_url = 'https://' + icon_url[len('http://'):]
            except Exception as e:
                monobank_logger.warning(f'Failed to get image for item {item.id}: {e}')
                icon_url = ''
            
            # Для предоплаты показываем фиксированную сумму 200 грн
            # Для полной оплаты показываем реальную стоимость дропа
            if order.payment_method == 'cod':
                # При предоплате показываем один товар с суммой 200 грн
                item_sum = int(amount * 100)  # 200 грн в копійках
                item_qty = 1
                item_name = f"{payment_type} • {display_name}"
            else:
                # При полной оплате показываем реальную стоимость
                item_sum = int(item.drop_price * item.quantity * 100)
                item_qty = item.quantity
                item_name = display_name
            
            basket_entries.append({
                'name': item_name,
                'qty': item_qty,
                'sum': item_sum,
                'icon': icon_url
            })
            
            # Для предоплаты достаточно одного товара
            if order.payment_method == 'cod':
                break
        
        if not basket_entries:
            return JsonResponse({
                'success': False,
                'error': 'Замовлення не містить товарів'
            })
        
        # Формируем payload для Monobank Acquiring API
        payload = {
            'amount': int(amount * 100),  # сумма в копейках
            'ccy': 980,  # гривна
            'merchantPaymInfo': {
                'reference': f"DS-{order.order_number}",
                'destination': description,
                'basketOrder': basket_entries
            },
            'redirectUrl': request.build_absolute_uri('/orders/dropshipper/monobank/return/').replace('http://', 'https://', 1),
            'webHookUrl': request.build_absolute_uri('/orders/dropshipper/monobank/callback/').replace('http://', 'https://', 1),
        }
        
        monobank_logger.info(f'Creating Monobank payment for dropshipper order {order.id}, payload: {payload}')
        
        # Создаем платеж в Monobank
        try:
            creation_data = _monobank_api_request('POST', '/api/merchant/invoice/create', json_payload=payload)
        except MonobankAPIError as e:
            monobank_logger.error(f'Failed to create Monobank payment for dropshipper order {order.id}: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        
        result = creation_data.get('result') or creation_data
        invoice_id = result.get('invoiceId')
        invoice_url = result.get('pageUrl')
        
        if not invoice_id or not invoice_url:
            monobank_logger.error(f'Invalid Monobank response for dropshipper order {order.id}: {creation_data}')
            return JsonResponse({
                'success': False,
                'error': 'Не вдалося створити платіж. Спробуйте пізніше.'
            })
        
        # Сохраняем данные платежа в заказе
        order.monobank_invoice_id = invoice_id
        order.save()
        
        # Сохраняем в сессию
        request.session['dropshipper_monobank_order_id'] = order.id
        request.session['dropshipper_monobank_invoice_id'] = invoice_id
        request.session.modified = True
        
        monobank_logger.info(f'Monobank payment created for dropshipper order {order.id}: {invoice_id}')
        
        return JsonResponse({
            'success': True,
            'page_url': invoice_url,
            'order_id': order.id,
            'invoice_id': invoice_id
        })
        
    except Exception as e:
        monobank_logger.exception(f'Error creating dropshipper Monobank payment: {e}')
        return JsonResponse({
            'success': False,
            'error': f'Помилка при створенні платежу: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def dropshipper_monobank_callback(request):
    """Обработка callback от Monobank для оплаты дропшипера"""
    try:
        data = json.loads(request.body)
        monobank_logger.info(f'Received Monobank callback for dropshipper: {data}')
        
        invoice_id = data.get('invoiceId')
        status = data.get('status')
        
        if not invoice_id:
            monobank_logger.error('No invoiceId in callback')
            return JsonResponse({'success': False})
        
        # Находим заказ по invoice_id
        try:
            order = DropshipperOrder.objects.get(monobank_invoice_id=invoice_id)
        except DropshipperOrder.DoesNotExist:
            monobank_logger.error(f'Order not found for invoice_id: {invoice_id}')
            return JsonResponse({'success': False})
        
        # Обновляем статус оплаты
        if status == 'success':
            order.payment_status = 'paid'
            order.status = 'confirmed'  # Меняем статус на "Підтверджено"
            order.save()
            monobank_logger.info(f'Payment successful for dropshipper order {order.order_number}')
            
            # Отправляем уведомление в Telegram админу об оплате
            try:
                from .telegram_notifications import telegram_notifier
                telegram_notifier.send_dropshipper_payment_notification(order)
                monobank_logger.info(f"Telegram уведомление об оплате отправлено для заказа {order.order_number}")
            except Exception as e:
                # Не прерываем обработку callback если Telegram не работает
                monobank_logger.error(f"Ошибка отправки Telegram уведомления об оплате: {e}")
        elif status == 'failure':
            order.payment_status = 'failed'
            order.save()
            monobank_logger.warning(f'Payment failed for dropshipper order {order.order_number}')
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        monobank_logger.exception(f'Error processing dropshipper Monobank callback: {e}')
        return JsonResponse({'success': False})


@login_required
def dropshipper_monobank_return(request):
    """Обработка возврата пользователя после оплаты Monobank"""
    from django.contrib import messages
    
    order_id = request.session.get('dropshipper_monobank_order_id')
    invoice_id = request.GET.get('invoiceId') or request.session.get('dropshipper_monobank_invoice_id')
    
    if order_id:
        try:
            order = DropshipperOrder.objects.get(id=order_id, dropshipper=request.user)
            
            # Очищаем сессию
            request.session.pop('dropshipper_monobank_order_id', None)
            request.session.pop('dropshipper_monobank_invoice_id', None)
            request.session.modified = True
            
            if order.payment_status == 'paid':
                messages.success(request, f'Оплата успішна! Замовлення {order.order_number} оплачено.')
            else:
                messages.warning(request, f'Очікується підтвердження оплати для замовлення {order.order_number}')
            
            return redirect('orders:dropshipper_orders')
            
        except DropshipperOrder.DoesNotExist:
            messages.error(request, 'Замовлення не знайдено')
    else:
        messages.error(request, 'Помилка: дані про замовлення відсутні')
    
    return redirect('orders:dropshipper_dashboard')


# ============= ADMIN VIEWS =============

@login_required
@require_http_methods(["POST"])
def admin_update_dropship_status(request, order_id):
    """Обновление статуса заказа дропшипера администратором"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    try:
        data = json.loads(request.body)
        order = get_object_or_404(DropshipperOrder, id=order_id)
        
        new_status = data.get('status')
        new_payment_status = data.get('payment_status')
        tracking_number = data.get('tracking_number', '').strip()
        
        if not new_status:
            return JsonResponse({'success': False, 'error': 'Статус не вказано'})
        
        # Валидация статуса
        valid_statuses = [choice[0] for choice in DropshipperOrder.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Невірний статус'})
        
        # Валидация payment_status если указан
        if new_payment_status:
            valid_payment_statuses = [choice[0] for choice in DropshipperOrder.PAYMENT_STATUS_CHOICES]
            if new_payment_status not in valid_payment_statuses:
                return JsonResponse({'success': False, 'error': 'Невірний статус оплати'})
        
        old_status = order.status
        old_payment_status = order.payment_status
        
        order.status = new_status
        
        # Обновляем payment_status если указан
        if new_payment_status:
            order.payment_status = new_payment_status
        
        # Обновляем ТТН если предоставлен
        if tracking_number:
            order.tracking_number = tracking_number
        
        # Логика изменения статуса
        # Если переводим в "Відправлено" - требуем ТТН
        if new_status == 'shipped' and not tracking_number and not order.tracking_number:
            return JsonResponse({
                'success': False,
                'error': 'Для статусу "Відправлено" необхідно вказати ТТН'
            })
        
        order.save()
        
        # Отправляем уведомления об изменении статуса
        if old_status != new_status:
            # Уведомление дропшиперу
            try:
                from .telegram_notifications import telegram_notifier
                telegram_notifier.send_dropshipper_status_change_notification(order, old_status, new_status)
                monobank_logger.info(f"✅ Telegram уведомление дропшиперу отправлено для заказа {order.order_number}")
            except Exception as e:
                monobank_logger.error(f"⚠️ Ошибка отправки Telegram уведомления дропшиперу: {e}")
            
            # Уведомление админу об изменении статуса
            try:
                from .telegram_notifications import telegram_notifier
                # Используем существующую функцию или создаем новую для админа
                admin_message = f"""🔄 <b>ЗМІНА СТАТУСУ ДРОПШИП ЗАМОВЛЕННЯ</b>

<b>Замовлення:</b> #{order.order_number}
<b>Дропшипер:</b> {order.dropshipper.userprofile.company_name if order.dropshipper.userprofile.company_name else order.dropshipper.username}

<b>Старий статус:</b> {dict(DropshipperOrder.STATUS_CHOICES).get(old_status, old_status)}
<b>Новий статус:</b> {order.get_status_display()}

<b>Клієнт:</b> {order.client_name if order.client_name else 'Не вказано'}
<b>Телефон:</b> {order.client_phone if order.client_phone else 'Не вказано'}"""
                
                if order.tracking_number:
                    admin_message += f"\n<b>ТТН:</b> {order.tracking_number}"
                
                admin_message += f"\n\n🔗 <a href=\"https://twocomms.shop/admin-panel/?section=collaboration\">Переглянути в адмін-панелі</a>"
                
                telegram_notifier.send_message(admin_message)
                monobank_logger.info(f"✅ Telegram уведомление админу об изменении статуса отправлено для заказа {order.order_number}")
            except Exception as e:
                monobank_logger.error(f"⚠️ Ошибка отправки Telegram уведомления админу: {e}")
        
        # Логируем изменение
        monobank_logger.info(
            f'Admin {request.user.username} changed order {order.order_number} '
            f'status from {old_status} to {new_status}'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Статус змінено на "{order.get_status_display()}"',
            'new_status': new_status,
            'new_status_display': order.get_status_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невірний формат даних'}, status=400)
    except Exception as e:
        monobank_logger.exception(f'Error updating dropship order status: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def admin_check_np_status(request, order_id):
    """Проверка статуса НП и автоматическое обновление заказа"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    try:
        order = get_object_or_404(DropshipperOrder, id=order_id)
        
        # Вызываем метод модели для проверки статуса
        success, message = order.check_np_status_and_update()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'new_status': order.status,
                'new_status_display': order.get_status_display(),
                'shipment_status': order.shipment_status,
                'payout_processed': order.payout_processed
            })
        else:
            return JsonResponse({'success': False, 'error': message})
        
    except Exception as e:
        monobank_logger.exception(f'Error checking NP status: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
