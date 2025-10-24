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


# ==================== USER POINTS & REWARDS ====================

@login_required
def user_points(request):
    """
    Страница баллов пользователя.
    Показывает текущий баланс и историю начислений/списаний.
    """
    from accounts.models import UserPoints, PointsHistory
    
    # Получаем или создаем объект баллов пользователя
    try:
        user_points_obj = UserPoints.get_or_create_points(request.user)
    except AttributeError:
        # Если метод get_or_create_points не существует, используем get_or_create
        user_points_obj, _ = UserPoints.objects.get_or_create(user=request.user)
    
    # Получаем историю баллов (последние 20 записей)
    history = PointsHistory.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    return render(request, 'pages/user_points.html', {
        'user_points': user_points_obj,
        'history': history
    })


@login_required
def my_promocodes(request):
    """
    Страница промокодов пользователя.
    Показывает использованные промокоды в заказах.
    """
    from orders.models import Order
    
    # Получаем все заказы пользователя с промокодами
    orders_with_promocodes = Order.objects.filter(
        user=request.user,
        promo_code__isnull=False
    ).select_related('promo_code').order_by('-created_at')
    
    # Создаем список использованных промокодов
    used_promocodes = []
    for order in orders_with_promocodes:
        if order.promo_code:
            used_promocodes.append({
                'promo_code': order.promo_code,
                'order': order,
                'used_date': order.created_at,
                'discount_amount': order.discount_amount,
                'order_total': order.total_sum
            })
    
    return render(request, 'pages/my_promocodes.html', {
        'used_promocodes': used_promocodes
    })


@login_required
def buy_with_points(request):
    """
    Страница покупки за баллы.
    Показывает доступные товары/услуги за баллы лояльности.
    """
    from accounts.models import UserPoints
    
    # Получаем баллы пользователя
    try:
        user_points_obj = UserPoints.objects.get(user=request.user)
        current_points = user_points_obj.points
    except UserPoints.DoesNotExist:
        current_points = 0
    
    # Определяем доступные товары за баллы
    available_items = [
        {
            'id': 'promo_10',
            'name': 'Промокод на знижку 10%',
            'description': 'Отримайте промокод на знижку 10% від суми замовлення',
            'points_cost': 100,
            'type': 'promo',
            'icon': 'M21.41 11.58l-9-9C12.05 2.22 11.55 2 11 2H4c-1.1 0-2 .9-2 2v7c0 .55.22 1.05.59 1.42l9 9c.36.36.86.58 1.41.58.55 0 1.05-.22 1.41-.59l7-7c.37-.36.59-.86.59-1.41 0-.55-.23-1.06-.59-1.42zM5.5 7C4.67 7 4 6.33 4 5.5S4.67 4 5.5 4 7 4.67 7 5.5 6.33 7 5.5 7z',
            'color': 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            'can_afford': current_points >= 100
        },
        {
            'id': 'donate_zsu',
            'name': 'Донат на ЗСУ',
            'description': 'Пожертвуйте всі ваші бали на підтримку Збройних Сил України',
            'points_cost': current_points,
            'type': 'donate',
            'icon': 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
            'color': 'linear-gradient(135deg, #dc2626, #991b1b)',
            'can_afford': current_points > 0
        }
    ]
    
    return render(request, 'pages/buy_with_points.html', {
        'current_points': current_points,
        'available_items': available_items
    })


@login_required
@require_POST
def purchase_with_points(request):
    """
    Обработка покупки за баллы.
    Списывает баллы и выдает соответствующую награду.
    """
    from accounts.models import UserPoints
    from django.contrib import messages
    
    item_id = request.POST.get('item_id')
    
    try:
        user_points_obj = UserPoints.objects.get(user=request.user)
    except UserPoints.DoesNotExist:
        messages.error(request, 'У вас немає балів для покупки')
        return redirect('buy_with_points')
    
    if item_id == 'promo_10':
        # Покупка промокода на 10% скидки
        if user_points_obj.points >= 100:
            # Здесь будет логика создания промокода
            # Пока что просто списываем баллы
            try:
                user_points_obj.spend_points(100, 'Покупка промокода на знижку 10%')
                messages.success(
                    request,
                    'Промокод на знижку 10% успішно придбано! Код: POINTS10'
                )
            except Exception as e:
                messages.error(request, f'Помилка при списанні балів: {e}')
        else:
            messages.error(request, 'Недостатньо балів для покупки промокода')
    
    elif item_id == 'donate_zsu':
        # Донат на ЗСУ
        if user_points_obj.points > 0:
            points_to_donate = user_points_obj.points
            try:
                user_points_obj.spend_points(points_to_donate, 'Донат на ЗСУ')
                messages.success(
                    request,
                    f'Дякуємо за підтримку ЗСУ! Пожертвовано {points_to_donate} балів'
                )
            except Exception as e:
                messages.error(request, f'Помилка при пожертвуванні: {e}')
        else:
            messages.error(request, 'У вас немає балів для пожертвування')
    
    else:
        messages.error(request, 'Невідомий товар')
    
    return redirect('buy_with_points')


@login_required
def profile_setup_db(request):
    """
    Налаштування профілю користувача з БД.
    
    Дозволяє редагувати:
    - Особисті дані (ім'я, телефон, email)
    - Соціальні мережі (telegram, instagram)
    - Дані доставки (місто, відділення НП)
    - Тип оплати
    - УБД статус та документи
    - Аватар
    """
    # Профиль в БД
    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    initial = {
        'full_name': getattr(prof, 'full_name', ''),
        'phone': prof.phone or '',
        'email': prof.email or '',
        'telegram': prof.telegram or '',
        'instagram': prof.instagram or '',
        'city': prof.city or '',
        'np_office': prof.np_office or '',
        'pay_type': prof.pay_type or '',
        'is_ubd': prof.is_ubd,
    }
    form = ProfileSetupForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        prof.full_name = form.cleaned_data.get('full_name') or ''
        prof.phone = form.cleaned_data.get('phone') or ''
        prof.email = form.cleaned_data.get('email') or ''
        prof.telegram = form.cleaned_data.get('telegram') or ''
        prof.instagram = form.cleaned_data.get('instagram') or ''
        prof.city = form.cleaned_data.get('city') or ''
        prof.np_office = form.cleaned_data.get('np_office') or ''
        prof.pay_type = form.cleaned_data.get('pay_type') or ''
        prof.is_ubd = bool(form.cleaned_data.get('is_ubd'))
        
        # Отладочная информация для аватара
        if form.cleaned_data.get('avatar'):
            prof.avatar = form.cleaned_data['avatar']
            
        if prof.is_ubd and form.cleaned_data.get('ubd_doc'):
            prof.ubd_doc = form.cleaned_data['ubd_doc']
        prof.save()
        # Обновим сессию (не обязательно, но пусть будет телефон под рукой)
        request.session['profile_phone'] = prof.phone
        if prof.avatar:
            request.session['profile_avatar'] = prof.avatar.name
        request.session.modified = True
        return redirect('home')
    return render(request, 'pages/auth_profile_setup.html', {'form': form, 'profile': prof})


def favorites_list_view(request):
    """
    Сторінка з обраними товарами.
    
    Функціонал:
    - Для авторизованих: список з БД
    - Для гостей: список з сесії
    - Варіанти кольорів для кожного товару
    - Підтримка ProductColorVariant
    """
    if request.user.is_authenticated:
        # Для авторизованых пользователей - получаем из базы данных
        favorites = FavoriteProduct.objects.select_related('category').filter(user=request.user).select_related('product', 'product__category')
    else:
        # Для неавторизованных пользователей - получаем из сессии
        session_favorites = request.session.get('favorites', [])
        favorites = []
        
        if session_favorites:
            # Получаем товары по ID из сессии
            products = Product.objects.select_related('category').filter(id__in=session_favorites).select_related('category')
            
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
            variants = ProductColorVariant.objects.select_related('color').filter(product=favorite.product)
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
        except:
            favorite.color_variants_data = []
    
    return render(request, 'pages/favorites.html', {
        'favorites': favorites,
        'title': 'Обрані товари'
    })

