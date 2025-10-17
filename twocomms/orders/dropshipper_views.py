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
import json

from .models import DropshipperOrder, DropshipperOrderItem, DropshipperStats, DropshipperPayout
from storefront.models import Product, Category
from productcolors.models import ProductColorVariant


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
    
    # Получаем категории для фильтрации
    categories = Category.objects.filter(is_active=True).order_by('order', 'name')
    
    context = {
        'stats': stats,
        'recent_orders': recent_orders,
        'categories': categories,
    }
    
    return render(request, 'pages/dropshipper_dashboard.html', context)


@login_required
def dropshipper_products(request):
    """Страница с товарами для дропшиперов"""
    category_id = request.GET.get('category')
    search_query = request.GET.get('search', '')
    
    # Базовый queryset
    products = Product.objects.filter(
        category__is_active=True
    ).select_related('category').prefetch_related('color_variants__images')
    
    # Фильтрация по категории
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Поиск
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории для фильтра
    categories = Category.objects.filter(is_active=True).order_by('order', 'name')
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'search_query': search_query,
    }
    
    return render(request, 'pages/dropshipper_products.html', context)


@login_required
def dropshipper_orders(request):
    """Страница с заказами дропшипера"""
    status_filter = request.GET.get('status', '')
    
    # Базовый queryset
    orders = DropshipperOrder.objects.filter(dropshipper=request.user).prefetch_related('items__product')
    
    # Фильтрация по статусу
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Пагинация
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': DropshipperOrder.STATUS_CHOICES,
        'selected_status': status_filter,
    }
    
    return render(request, 'pages/dropshipper_orders.html', context)


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
    
    context = {
        'stats': stats,
        'monthly_stats': monthly_stats,
        'top_products': top_products,
    }
    
    return render(request, 'pages/dropshipper_statistics.html', context)


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
    }
    
    return render(request, 'pages/dropshipper_payouts.html', context)


@login_required
@require_http_methods(["POST"])
def create_dropshipper_order(request):
    """Создание нового заказа дропшипера"""
    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            # Создаем заказ
            order = DropshipperOrder.objects.create(
                dropshipper=request.user,
                client_name=data.get('client_name', ''),
                client_phone=data.get('client_phone', ''),
                client_np_address=data.get('client_np_address', ''),
                notes=data.get('notes', ''),
                status='draft'
            )
            
            # Добавляем товары
            total_drop_price = 0
            total_selling_price = 0
            
            for item_data in data.get('items', []):
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
                    drop_price=item_data.get('drop_price', product.drop_price),
                    selling_price=item_data.get('selling_price', product.recommended_price),
                    recommended_price=product.recommended_price
                )
                
                total_drop_price += order_item.total_drop_price
                total_selling_price += order_item.total_selling_price
            
            # Обновляем итоговые суммы заказа
            order.total_drop_price = total_drop_price
            order.total_selling_price = total_selling_price
            order.profit = total_selling_price - total_drop_price
            order.save()
            
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
        product = get_object_or_404(Product, id=product_id)
        color_variants = ProductColorVariant.objects.filter(product=product).prefetch_related('images')
        
        # Получаем доступные размеры
        sizes = []
        for variant in color_variants:
            if hasattr(variant, 'sizes') and variant.sizes:
                sizes.extend(variant.sizes.split(','))
        
        sizes = list(set(sizes))  # Убираем дубликаты
        
        data = {
            'id': product.id,
            'title': product.title,
            'description': product.description,
            'drop_price': float(product.drop_price),
            'recommended_price': float(product.recommended_price),
            'main_image': product.main_image.url if product.main_image else None,
            'color_variants': [
                {
                    'id': variant.id,
                    'color_name': variant.color.name if variant.color else 'Без кольору',
                    'primary_hex': variant.color.primary_hex if variant.color else '#000000',
                    'images': [img.image.url for img in variant.images.all()] if variant.images.exists() else []
                }
                for variant in color_variants
            ],
            'sizes': sizes
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Помилка при отриманні інформації про товар: {str(e)}'
        }, status=400)
