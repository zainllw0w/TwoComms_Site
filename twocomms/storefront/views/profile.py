"""
Profile views - Профиль пользователя и личный кабинет.

Содержит views для:
- Просмотра и редактирования профиля
- Истории заказов
- Избранных товаров
- Истории балов
- Настройки уведомлений
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User

from accounts.models import UserProfile, FavoriteProduct, UserPoints, PointsHistory
from orders.models import Order
from ..models import Product
from .auth import ProfileSetupForm


# ==================== PROFILE VIEWS ====================

@login_required
def profile(request):
    """
    Главная страница профиля пользователя.
    
    Показывает:
    - Основную информацию
    - Статистику заказов
    - Текущие баллы
    - Последние заказы
    """
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)
    
    # Статистика заказов
    orders = Order.objects.filter(user=request.user).order_by('-created')
    total_orders = orders.count()
    recent_orders = orders[:5]
    
    # Баллы
    try:
        user_points = request.user.points
    except (UserPoints.DoesNotExist, AttributeError):
        user_points = UserPoints.objects.create(user=request.user)
    
    # Избранное
    favorites_count = FavoriteProduct.objects.filter(user=request.user).count()
    
    return render(
        request,
        'pages/profile.html',
        {
            'user_profile': user_profile,
            'total_orders': total_orders,
            'recent_orders': recent_orders,
            'user_points': user_points,
            'favorites_count': favorites_count
        }
    )


@login_required
def edit_profile(request):
    """
    Редактирование профиля пользователя.
    
    Позволяет обновить:
    - ФИО
    - Телефон, Email
    - Адрес доставки
    - Способ оплаты
    - Аватар
    - УБД статус
    """
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Обновляем основные данные пользователя
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        # Обновляем профиль
        user_profile.full_name = request.POST.get('full_name', '')
        user_profile.phone = request.POST.get('phone', '')
        user_profile.email = request.POST.get('email', '')
        user_profile.telegram = request.POST.get('telegram', '')
        user_profile.instagram = request.POST.get('instagram', '')
        user_profile.city = request.POST.get('city', '')
        user_profile.np_office = request.POST.get('np_office', '')
        user_profile.pay_type = request.POST.get('pay_type', 'full')
        
        # Аватар
        if 'avatar' in request.FILES:
            user_profile.avatar = request.FILES['avatar']
        
        # УБД
        user_profile.is_ubd = 'is_ubd' in request.POST
        if 'ubd_doc' in request.FILES:
            user_profile.ubd_doc = request.FILES['ubd_doc']
        
        user_profile.save()
        
        return redirect('profile')
    
    return render(
        request,
        'pages/edit_profile.html',
        {'user_profile': user_profile}
    )


@login_required
def profile_setup(request):
    """
    Первоначальная настройка профиля после регистрации.
    
    Обязательные поля:
    - Телефон
    
    Опциональные:
    - ФИО, Email, Telegram, Instagram
    - Адрес доставки
    """
    try:
        prof = request.user.userprofile
    except UserProfile.DoesNotExist:
        prof = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, request.FILES)
        if form.is_valid():
            prof.full_name = form.cleaned_data.get('full_name', '')
            prof.phone = form.cleaned_data['phone']
            prof.email = form.cleaned_data.get('email', '')
            prof.telegram = form.cleaned_data.get('telegram', '')
            prof.instagram = form.cleaned_data.get('instagram', '')
            prof.city = form.cleaned_data.get('city', '')
            prof.np_office = form.cleaned_data.get('np_office', '')
            prof.pay_type = form.cleaned_data.get('pay_type', 'full')
            prof.is_ubd = form.cleaned_data.get('is_ubd', False)
            
            if form.cleaned_data.get('avatar'):
                prof.avatar = form.cleaned_data['avatar']
            if form.cleaned_data.get('ubd_doc'):
                prof.ubd_doc = form.cleaned_data['ubd_doc']
            
            prof.save()
            
            # Обновляем email пользователя
            if form.cleaned_data.get('email'):
                request.user.email = form.cleaned_data['email']
                request.user.save()
            
            return redirect('profile')
    else:
        initial = {
            'full_name': prof.full_name,
            'phone': prof.phone,
            'email': prof.email or request.user.email,
            'telegram': prof.telegram,
            'instagram': prof.instagram,
            'city': prof.city,
            'np_office': prof.np_office,
            'pay_type': prof.pay_type,
            'is_ubd': prof.is_ubd,
        }
        form = ProfileSetupForm(initial=initial)
    
    return render(request, 'pages/profile_setup.html', {'form': form})


@login_required
def order_history(request):
    """
    История заказов пользователя.
    
    Показывает все заказы с возможностью фильтрации по статусу.
    """
    status_filter = request.GET.get('status', '')
    
    orders = Order.objects.filter(user=request.user).order_by('-created')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    return render(
        request,
        'pages/order_history.html',
        {
            'orders': orders,
            'status_filter': status_filter
        }
    )


@login_required
def order_detail(request, order_number):
    """
    Детальная информация о заказе.
    
    Args:
        order_number (str): Номер заказа
    """
    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )
    
    return render(
        request,
        'pages/order_detail.html',
        {'order': order}
    )


def favorites(request):
    """
    Список избранных товаров пользователя.
    Поддерживает как авторизованных, так и неавторизованных пользователей.
    """
    if request.user.is_authenticated:
        # Для авторизованных пользователей - получаем из базы данных
        favorites = FavoriteProduct.objects.filter(
            user=request.user
        ).select_related('product', 'product__category')
    else:
        # Для неавторизованных пользователей - получаем из сессии
        session_favorites = request.session.get('favorites', [])
        favorites = []
        
        if session_favorites:
            # Получаем товары по ID из сессии
            products = Product.objects.filter(
                id__in=session_favorites
            ).select_related('category')
            
            # Создаем объекты, похожие на FavoriteProduct
            for product in products:
                favorite = type('FavoriteProduct', (), {
                    'product': product,
                    'color_variants_data': []
                })()
                favorites.append(favorite)
    
    # Получаем варианты цветов для избранных товаров
    for favorite in favorites:
        try:
            from productcolors.models import ProductColorVariant
            variants = ProductColorVariant.objects.select_related('color').filter(
                product=favorite.product
            )
            # Создаем список словарей с данными о цветах
            color_variants_data = [
                {
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                }
                for v in variants
            ]
            # Добавляем как атрибут к объекту favorite
            favorite.color_variants_data = color_variants_data
        except Exception:
            favorite.color_variants_data = []
    
    return render(request, 'pages/favorites.html', {
        'favorites': favorites,
        'title': 'Обрані товари'
    })


# Алиас для обратной совместимости
favorites_list = favorites


def toggle_favorite(request, product_id):
    """
    Добавить/удалить товар из избранного.
    Универсальная функция для авторизованных и неавторизованных пользователей.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        
        if request.user.is_authenticated:
            # Для авторизованных пользователей - используем базу данных
            favorite, created = FavoriteProduct.objects.get_or_create(
                user=request.user,
                product=product
            )
            
            if not created:
                # Если запись уже существует, удаляем её
                favorite.delete()
                is_favorite = False
                message = 'Товар видалено з обраного'
            else:
                is_favorite = True
                message = 'Товар додано до обраного'
        else:
            # Для неавторизованных пользователей - используем сессии
            session_favorites = request.session.get('favorites', [])
            # Преобразуем product_id в int для корректного сравнения
            product_id_int = int(product_id)
            
            if product_id_int in session_favorites:
                # Удаляем из избранного
                session_favorites.remove(product_id_int)
                is_favorite = False
                message = 'Товар видалено з обраного'
            else:
                # Добавляем в избранное
                session_favorites.append(product_id_int)
                is_favorite = True
                message = 'Товар додано до обраного'
            
            # Сохраняем в сессии
            request.session['favorites'] = session_favorites
            request.session.modified = True
        
        # Подсчитываем общее количество избранных товаров
        if request.user.is_authenticated:
            favorites_count_val = FavoriteProduct.objects.filter(user=request.user).count()
        else:
            favorites_count_val = len(request.session.get('favorites', []))
        
        return JsonResponse({
            'success': True,
            'is_favorite': is_favorite,
            'message': message,
            'favorites_count': favorites_count_val
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Помилка: ' + str(e)
        }, status=400)


# Алиасы для обратной совместимости с разными API
@login_required
@require_POST
def add_to_favorites(request, product_id):
    """Добавление товара в избранное (только для авторизованных)."""
    try:
        product = Product.objects.get(id=product_id)
        favorite, created = FavoriteProduct.objects.get_or_create(
            user=request.user,
            product=product
        )
        if created:
            return JsonResponse({
                'success': True,
                'message': f'Товар "{product.title}" додано до обраного'
            })
        else:
            return JsonResponse({
                'success': True,
                'message': 'Товар вже в обраному'
            })
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Товар не знайдено'
        }, status=404)


@login_required
@require_POST
def remove_from_favorites(request, product_id):
    """Удаление товара из избранного (только для авторизованных)."""
    try:
        favorite = FavoriteProduct.objects.get(
            user=request.user,
            product_id=product_id
        )
        favorite.delete()
        return JsonResponse({
            'success': True,
            'message': 'Товар видалено з обраного'
        })
    except FavoriteProduct.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Товар не знайдено в обраному'
        }, status=404)


def check_favorite_status(request, product_id):
    """Проверить статус избранного для товара."""
    try:
        if request.user.is_authenticated:
            # Для авторизованных пользователей - проверяем в базе данных
            is_favorite = FavoriteProduct.objects.filter(
                user=request.user,
                product_id=product_id
            ).exists()
        else:
            # Для неавторизованных пользователей - проверяем в сессии
            session_favorites = request.session.get('favorites', [])
            product_id_int = int(product_id)
            is_favorite = product_id_int in session_favorites
        
        return JsonResponse({'is_favorite': is_favorite})
    except Exception:
        return JsonResponse({'is_favorite': False})


def favorites_count(request):
    """Получить количество товаров в избранном."""
    try:
        if request.user.is_authenticated:
            # Для авторизованных пользователей - считаем в базе данных
            count = FavoriteProduct.objects.filter(user=request.user).count()
        else:
            # Для неавторизованных пользователей - считаем в сессии
            session_favorites = request.session.get('favorites', [])
            count = len(session_favorites)
        
        return JsonResponse({'count': count})
    except Exception as e:
        return JsonResponse({'count': 0, 'error': str(e)})


@login_required
def points_history(request):
    """
    История транзакций балов пользователя.
    """
    try:
        user_points = request.user.points
    except (UserPoints.DoesNotExist, AttributeError):
        user_points = UserPoints.objects.create(user=request.user)
    
    history = PointsHistory.objects.filter(user=request.user).order_by('-created_at')
    
    return render(
        request,
        'pages/points_history.html',
        {
            'user_points': user_points,
            'history': history
        }
    )


@login_required
def settings(request):
    """
    Настройки аккаунта.
    
    Позволяет изменить:
    - Пароль
    - Email
    - Уведомления
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Пароль успішно змінено'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Невірний старий пароль'
                }, status=400)
    
    return render(request, 'pages/settings.html')

