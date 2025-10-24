"""
Admin Panel Views
Адміністративна панель

Відповідальність:
- Головна панель адміністратора з усіма секціями
- Управління товарами (CRUD, кольори, зображення)
- Управління категоріями (CRUD)
- Управління промокодами (CRUD)
- Управління замовленнями (статуси, оплата)
- Управління користувачами (права, бали)
- Управління принтами (статуси, нагороди)
- Управління накладними

Основні секції admin_panel:
- users: Список користувачів з детальною статистикою
- catalogs: Управління категоріями та товарами
- promocodes: Управління промокодами
- offline_stores: Управління оффлайн магазинами
- print_proposals: Пропозиції принтів від користувачів
- orders: Замовлення з фільтрами
- collaboration: Оптові та дропшип замовлення
"""

import json
import random
import string
from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from ..models import (
    Product, ProductImage, Category, PromoCode, 
    PrintProposal, UserProfile
)
from ..forms import ProductForm, CategoryForm, PrintProposalForm
from .utils import unique_slugify
from productcolors.models import Color, ProductColorVariant, ProductColorImage


# ==================== ГОЛОВНА ПАНЕЛЬ АДМІНІСТРАТОРА ====================

@login_required
def admin_panel(request):
    """Головна панель адміністратора з усіма секціями"""
    if not request.user.is_staff:
        return redirect('home')
    section = request.GET.get('section', 'stats')
    ctx = {'section': section}
    
    # Перевіряємо, чи є параметр примусового оновлення
    force_refresh = request.GET.get('_t')
    if force_refresh:
        # Очищаємо кеш для примусового оновлення
        cache.clear()
    
    # Імпорти для всіх секцій
    if section == 'users':
        # Оптимізований запит з select_related та prefetch_related
        users = User.objects.select_related('userprofile').prefetch_related('points', 'orders').order_by('username')
        from accounts.models import UserPoints
        from orders.models import Order
        
        user_data = []
        for user in users:
            profile = getattr(user, 'userprofile', None)
            points = getattr(user, 'points', None)
            
            # Отримуємо замовлення користувача (вже завантажені через prefetch_related)
            user_orders = user.orders.all()
            total_orders = user_orders.count()
            
            # Підраховуємо замовлення по статусам
            order_status_counts = {}
            for status_code, status_name in Order.STATUS_CHOICES:
                order_status_counts[status_code] = user_orders.filter(status=status_code).count()
            
            # Підраховуємо замовлення по статусам оплати
            payment_status_counts = {}
            for payment_status_code, payment_status_name in [
                ('unpaid', 'Не оплачено'),
                ('checking', 'На перевірці'),
                ('partial', 'Внесена передплата'),
                ('paid', 'Оплачено повністю')
            ]:
                payment_status_counts[payment_status_code] = user_orders.filter(payment_status=payment_status_code).count()
            
            # Загальна сума замовлень (включаючи передоплати та часткові оплати)
            total_spent = user_orders.exclude(payment_status='unpaid').aggregate(
                total=Sum('total_sum')
            )['total'] or 0
            
            # Витрачені бали
            points_spent = points.total_spent if points else 0
            
            # Отримуємо промокоди користувача (включаючи використані)
            try:
                # Промокоди, видані користувачу
                user_promocodes = PromoCode.objects.filter(user=user).order_by('-created_at')
                # Промокоди, використані в замовленнях користувача
                used_promocodes = []
                for order in user_orders:
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
                'total_orders': total_orders,
                'order_status_counts': order_status_counts,
                'payment_status_counts': payment_status_counts,
                'total_spent': total_spent,
                'points_spent': points_spent,
                'promocodes': user_promocodes,
                'used_promocodes': used_promocodes
            })
        
        ctx.update({'user_data': user_data})
    elif section == 'catalogs':
        categories = Category.objects.select_related().filter(is_active=True).order_by('order','name') if hasattr(Category, 'order') else Category.objects.select_related().filter(is_active=True).order_by('name')
        products = Product.objects.select_related('category').order_by('-id')
        ctx.update({'categories': categories, 'products': products})
    elif section == 'promocodes':
        promocodes = PromoCode.objects.all()
        total_promocodes = promocodes.count()
        active_promocodes = promocodes.filter(is_active=True).count()
        ctx.update({
            'promocodes': promocodes,
            'total_promocodes': total_promocodes,
            'active_promocodes': active_promocodes
        })
    elif section == 'offline_stores':
        from ..models import OfflineStore
        stores = OfflineStore.objects.all()
        total_stores = stores.count()
        active_stores = stores.filter(is_active=True).count()
        ctx.update({
            'stores': stores,
            'total_stores': total_stores,
            'active_stores': active_stores
        })
    elif section == 'print_proposals':
        proposals = PrintProposal.objects.select_related('user', 'user__userprofile', 'awarded_promocode').order_by('-created_at')
        total_proposals = proposals.count()
        pending_proposals = proposals.filter(status='pending').count()
        ctx.update({
            'print_proposals': proposals,
            'total_proposals': total_proposals,
            'pending_proposals': pending_proposals
        })
    elif section == 'orders':
        # реальні замовлення
        try:
            from orders.models import Order
            
            # Отримуємо параметри фільтрації
            status_filter = request.GET.get('status', 'all')
            payment_filter = request.GET.get('payment', 'all')
            user_id_filter = request.GET.get('user_id', None)
            
            
            # Базовий queryset
            orders = Order.objects.select_related('user').prefetch_related('items','items__product')
            
            # Застосовуємо фільтри
            if status_filter != 'all':
                orders = orders.filter(status=status_filter)
            
            if payment_filter != 'all':
                orders = orders.filter(payment_status=payment_filter)
            
            # Фільтр по конкретному користувачу
            user_filter_info = None
            if user_id_filter:
                orders = orders.filter(user_id=user_id_filter)
                
                # Отримуємо інформацію про користувача для відображення
                try:
                    user_obj = User.objects.get(id=user_id_filter)
                    
                    # Перевіряємо, чи є у користувача профіль
                    full_name = None
                    if hasattr(user_obj, 'userprofile') and user_obj.userprofile:
                        try:
                            full_name = user_obj.userprofile.full_name
                        except:
                            full_name = None
                    
                    user_filter_info = {
                        'username': user_obj.username,
                        'full_name': full_name
                    }
                except User.DoesNotExist:
                    pass
                    user_filter_info = None
            
            # Отримуємо відфільтровані замовлення
            orders = orders.all()
            
            # Підрахунок замовлень по статусам
            status_counts = {}
            for status_code, status_name in Order.STATUS_CHOICES:
                status_counts[status_code] = Order.objects.select_related('user').filter(status=status_code).count()
            
            # Підрахунок замовлень по статусам оплати
            payment_status_counts = {}
            for payment_status_code, payment_status_name in [
                ('unpaid', 'Не оплачено'),
                ('checking', 'На перевірці'),
                ('partial', 'Внесена передплата'),
                ('paid', 'Оплачено повністю')
            ]:
                payment_status_counts[payment_status_code] = Order.objects.select_related('user').filter(payment_status=payment_status_code).count()
            
            # Загальна кількість замовлень
            total_orders = Order.objects.count()
            
        except Exception:
            orders = []
            status_counts = {}
            payment_status_counts = {}
            total_orders = 0
        
        ctx.update({
            'orders': orders,
            'status_counts': status_counts,
            'payment_status_counts': payment_status_counts,
            'total_orders': total_orders,
            'status_filter': status_filter,
            'payment_filter': payment_filter,
            'user_filter_info': user_filter_info
        })
    elif section == 'collaboration':
        try:
            from orders.models import WholesaleInvoice, DropshipperOrder, DropshipperStats, DropshipperPayout
            from django.db.models import Q
            
            # Накладні оптовиків
            invoices = WholesaleInvoice.objects.filter(
                status__in=['pending', 'processing', 'shipped', 'delivered', 'cancelled']
            ).order_by('-created_at')[:50]
            
            # Замовлення дропшипперів
            dropship_orders = DropshipperOrder.objects.select_related(
                'dropshipper', 'dropshipper__userprofile'
            ).prefetch_related('items').order_by('-created_at')[:50]
            
            # Статистика дропшипперів
            dropshipper_stats = DropshipperStats.objects.select_related(
                'dropshipper', 'dropshipper__userprofile'
            ).filter(total_orders__gt=0).order_by('-total_profit')[:20]
            
            # Виплати дропшипперів (із захистом від помилок)
            try:
                payouts = DropshipperPayout.objects.select_related(
                    'dropshipper', 'dropshipper__userprofile'
                ).order_by('-requested_at')[:50]
                
                pending_payouts = DropshipperPayout.objects.filter(
                    status='pending'
                ).count()
            except Exception as e:
                print(f"Error loading payouts: {e}")
                payouts = []
                pending_payouts = 0
            
            # Загальна статистика
            total_dropship_orders = DropshipperOrder.objects.count()
            total_dropship_revenue = DropshipperOrder.objects.aggregate(
                total=Sum('total_selling_price')
            )['total'] or 0
            total_dropship_profit = DropshipperOrder.objects.aggregate(
                total=Sum('profit')
            )['total'] or 0
            pending_orders = DropshipperOrder.objects.filter(
                status__in=['draft', 'pending']
            ).count()
            
            ctx.update({
                'invoices': invoices,
                'dropship_orders': dropship_orders,
                'dropshipper_stats': dropshipper_stats,
                'payouts': payouts,
                'pending_payouts': pending_payouts,
                'total_dropship_orders': total_dropship_orders,
                'total_dropship_revenue': total_dropship_revenue,
                'total_dropship_profit': total_dropship_profit,
                'pending_orders': pending_orders,
            })
        except Exception as e:
            print(f"Error loading collaboration data: {e}")
            invoices = []
            ctx.update({'invoices': invoices})
    
    return render(request, 'pages/admin_panel.html', ctx)


# ==================== УПРАВЛІННЯ КОРИСТУВАЧАМИ ====================

@login_required
def admin_update_user(request):
    """Оновлення даних користувача (права, бали)"""
    if not request.user.is_staff:
        return redirect('home')
    if request.method != 'POST':
        return redirect('admin_panel')
    user_id = request.POST.get('user_id')
    is_staff = True if request.POST.get('is_staff') == 'on' else False
    is_superuser_req = True if request.POST.get('is_superuser') == 'on' else False
    
    # Обробка балів
    points_adjustment = request.POST.get('points_adjustment')
    points_reason = request.POST.get('points_reason', '')

    try:
        u = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect('admin_panel')

    if not request.user.is_superuser:
        is_superuser_req = u.is_superuser

    u.is_staff = is_staff
    u.is_superuser = is_superuser_req
    u.save()
    
    # Оновлюємо бали якщо вказано
    if points_adjustment:
        try:
            points_change = int(points_adjustment)
            if points_change != 0:
                from accounts.models import UserPoints
                user_points = UserPoints.get_or_create_points(u)
                
                if points_change > 0:
                    user_points.add_points(points_change, f'Коригування адміністратором: {points_reason}')
                else:
                    user_points.spend_points(abs(points_change), f'Коригування адміністратором: {points_reason}')
        except ValueError:
            pass
    
    return redirect('/admin-panel/?section=users')


# ==================== УПРАВЛІННЯ ЗАМОВЛЕННЯМИ ====================

@login_required
def admin_order_update(request):
    """Оновлення статусу замовлення"""
    if not request.user.is_staff:
        return redirect('home')
    if request.method != 'POST':
        return redirect('/admin-panel/?section=orders')
    
    from orders.models import Order
    
    oid = request.POST.get('order_id')
    status = request.POST.get('status')
    tracking_number = request.POST.get('tracking_number', '').strip()
    
    try:
        o = Order.objects.get(pk=oid)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    old_status = o.status
    if status in dict(Order.STATUS_CHOICES):
        o.status = status
        
        # Оновлюємо ТТН якщо надано
        if tracking_number:
            o.tracking_number = tracking_number
        
        o.save()
        
        # Обробляємо бали при зміні статусу
        if o.user:  # Тільки для авторизованих користувачів
            from accounts.models import UserPoints
            user_points = UserPoints.get_or_create_points(o.user)
            
            # Розраховуємо бали за замовлення
            total_points = 0
            for item in o.items.all():
                if item.product.points_reward > 0:
                    total_points += item.product.points_reward * item.qty
            
            # Статуси, при яких нараховуються бали
            points_awarding_statuses = ['prep', 'ship', 'done']  # 'готується до відправки', 'відправлено', 'отримано'
            
            # Статуси, при яких скасовуються бали
            points_cancelling_statuses = ['cancelled']  # 'скасовано'
            
            # Якщо переходимо до статусу нарахування балів і бали ще не нараховані
            if status in points_awarding_statuses and old_status not in points_awarding_statuses and not o.points_awarded:
                if total_points > 0:
                    user_points.add_points(total_points, f'Замовлення #{o.order_number} {o.get_status_display()}')
                    o.points_awarded = True
                    o.save(update_fields=['points_awarded'])
            
            # Якщо переходимо до статусу скасування балів і бали були нараховані
            elif status in points_cancelling_statuses and old_status not in points_cancelling_statuses and o.points_awarded:
                if total_points > 0:
                    user_points.spend_points(total_points, f'Скасування замовлення #{o.order_number}')
                    o.points_awarded = False
                    o.save(update_fields=['points_awarded'])
        
        # Формуємо повідомлення про успіх
        status_display = dict(Order.STATUS_CHOICES).get(status, status)
        message = f'Статус замовлення змінено на "{status_display}"'
        if tracking_number:
            message += f' з ТТН: {tracking_number}'
        
        return JsonResponse({
            'success': True, 
            'message': message,
            'status': status,
            'tracking_number': tracking_number
        })
    
    return JsonResponse({'success': False, 'error': 'Невірний статус'})


@login_required
def admin_update_payment_status(request):
    """Оновлення статусу оплати замовлення"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    from orders.models import Order
    
    order_id = request.POST.get('order_id')
    payment_status = request.POST.get('payment_status')
    
    if not order_id or not payment_status:
        return JsonResponse({'success': False, 'error': 'Відсутні необхідні дані'})
    
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    # Перевіряємо валідність статусу оплати
    valid_payment_statuses = ['unpaid', 'checking', 'partial', 'paid']
    if payment_status not in valid_payment_statuses:
        return JsonResponse({'success': False, 'error': 'Невірний статус оплати'})
    
    # Оновлюємо статус оплати
    order.payment_status = payment_status
    order.save()
    
    # Формуємо повідомлення про успіх
    payment_status_display = {
        'unpaid': 'Не оплачено',
        'checking': 'На перевірці',
        'partial': 'Внесена передплата',
        'paid': 'Оплачено повністю'
    }.get(payment_status, payment_status)
    
    return JsonResponse({
        'success': True,
        'message': f'Статус оплати змінено на "{payment_status_display}"',
        'payment_status': payment_status
    })


@login_required
def admin_approve_payment(request):
    """Підтвердження або відхилення оплати замовлення"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    from orders.models import Order
    
    order_id = request.POST.get('order_id')
    action = request.POST.get('action')  # 'approve' або 'reject'
    
    if not order_id or not action:
        return JsonResponse({'success': False, 'error': 'Відсутні необхідні дані'})
    
    if action not in ['approve', 'reject']:
        return JsonResponse({'success': False, 'error': 'Невірна дія'})
    
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    if action == 'approve':
        # Підтверджуємо оплату
        order.payment_status = 'paid'
        message = 'Оплату підтверджено'
        new_status = 'paid'
    else:
        # Відхиляємо оплату
        order.payment_status = 'unpaid'
        message = 'Оплату відхилено'
        new_status = 'unpaid'
    
    order.save()
    
    return JsonResponse({
        'success': True,
        'message': message,
        'new_status': new_status
    })


@login_required
def admin_order_delete(request, pk: int):
    """Видалення замовлення"""
    if not request.user.is_staff:
        return redirect('home')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        from orders.models import Order
        order = Order.objects.get(pk=pk)
        order.delete()
        if is_ajax:
            return JsonResponse({'ok': True, 'removed_id': pk})
        from django.contrib import messages
        messages.success(request, f"Замовлення #{order.order_number} видалено")
    except Exception as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        from django.contrib import messages
        messages.error(request, f"Помилка видалення: {e}")
    return redirect('admin_panel')


# ==================== УПРАВЛІННЯ НАКЛАДНИМИ ====================

@require_POST
@login_required
def admin_update_invoice_status(request, invoice_id):
    """Оновлення статусу накладної (тільки для staff)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        from orders.models import WholesaleInvoice
        from orders.telegram_notifications import telegram_notifier
        
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        invoice = WholesaleInvoice.objects.get(id=invoice_id)
        old_status = invoice.status
        invoice.status = new_status
        invoice.save()
        
        # Відправляємо повідомлення в Telegram при відправці накладної на перевірку
        if new_status == 'pending' and old_status == 'draft':
            try:
                # Відправляємо повідомлення про нову накладну
                telegram_notifier.send_invoice_notification(invoice)
                
                # Якщо є файл накладної, відправляємо його теж
                if invoice.file_path:
                    import os
                    if os.path.exists(invoice.file_path):
                        telegram_notifier.send_document(
                            invoice.file_path,
                            caption=f"Накладна #{invoice.id} від {invoice.user.username}"
                        )
            except Exception as e:
                print(f"Error sending Telegram notification: {e}")
        
        return JsonResponse({
            'success': True,
            'message': f'Статус накладної оновлено на "{new_status}"'
        })
        
    except WholesaleInvoice.DoesNotExist:
        return JsonResponse({'error': 'Накладна не знайдена'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ==================== УПРАВЛІННЯ ПРИНТАМИ ====================

@login_required
def admin_print_proposal_update_status(request):
    """Оновлення статусу пропозиції принта"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        status = request.POST.get('status')
        
        if not proposal_id or not status:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        proposal.status = status
        proposal.save()
        
        status_text = dict(PrintProposal.STATUS_CHOICES)[status]
        
        return JsonResponse({
            'success': True, 
            'message': f'Статус принта оновлено на "{status_text}"',
            'new_status_text': status_text
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})


@login_required
def admin_print_proposal_award_points(request):
    """Нарахування балів за пропозицію принта"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        points = int(request.POST.get('points', 0))
        
        if not proposal_id or points <= 0:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри або невірна кількість балів'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        proposal.awarded_points = points
        proposal.save()
        
        # Додаємо бали користувачу
        from accounts.models import UserPoints
        user_points, created = UserPoints.objects.get_or_create(user=proposal.user)
        user_points.total_earned += points
        user_points.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Користувачу {proposal.user.username} нараховано {points} балів'
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Невірна кількість балів'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})


@login_required
def admin_print_proposal_award_promocode(request):
    """Видача промокоду за пропозицію принта"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        amount = int(request.POST.get('amount', 0))
        
        if not proposal_id or amount <= 0:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри або невірна сума'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        
        # Створюємо промокод
        # Генеруємо унікальний код
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not PromoCode.objects.filter(code=code).exists():
                break
        
        promocode = PromoCode.objects.create(
            code=code,
            discount_type='fixed',
            discount_amount=amount,
            user=proposal.user,
            is_active=True,
            description=f'Промокод за принт від {proposal.user.username}'
        )
        
        proposal.awarded_promocode = promocode
        proposal.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Користувачу {proposal.user.username} видано промокод {code} на суму {amount}₴'
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Невірна сума промокоду'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})


# ==================== УПРАВЛІННЯ КАТЕГОРІЯМИ ====================

@login_required
def admin_category_new(request):
    """Створення нової категорії"""
    if not request.user.is_staff:
        return redirect('home')
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('/admin-panel/?section=catalogs')
    return render(request, 'pages/admin_category_form.html', {'form': form, 'mode': 'new'})


@login_required
def admin_category_edit(request, pk):
    """Редагування категорії"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('/admin-panel/?section=catalogs')
    return render(request, 'pages/admin_category_form.html', {'form': form, 'mode': 'edit', 'obj': obj})


@login_required
def admin_category_delete(request, pk):
    """Видалення категорії"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Category, pk=pk)
    obj.delete()
    return redirect('/admin-panel/?section=catalogs')


# ==================== УПРАВЛІННЯ ТОВАРАМИ ====================

@login_required
def admin_product_colors(request, pk):
    """Управління кольоровими варіантами товару"""
    if not request.user.is_staff:
        return redirect('home')
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action') or 'add'
        if action == 'add':
            # Можна вибрати існуючий колір або задати hex
            color_id = request.POST.get('color_id')
            primary_hex = (request.POST.get('primary_hex') or '').strip() or '#000000'
            secondary_hex = (request.POST.get('secondary_hex') or '').strip() or None
            is_default = bool(request.POST.get('is_default'))
            # Якщо вибрали існуючий
            if color_id:
                color = get_object_or_404(Color, pk=color_id)
            else:
                color, _ = Color.objects.get_or_create(primary_hex=primary_hex, secondary_hex=secondary_hex)
            # Створюємо варіант
            variant = ProductColorVariant.objects.create(product=product, color=color, is_default=is_default, order=int(request.POST.get('order') or 0))
            # Завантажуємо зображення
            for f in request.FILES.getlist('images'):
                ProductColorImage.objects.create(variant=variant, image=f)
        elif action == 'delete_variant':
            vid = request.POST.get('variant_id')
            try:
                v = ProductColorVariant.objects.get(pk=vid, product=product)
                v.delete()
            except ProductColorVariant.DoesNotExist:
                pass
        elif action == 'delete_image':
            iid = request.POST.get('image_id')
            try:
                img = ProductColorImage.objects.filter(variant__product=product).get(pk=iid)
                img.delete()
            except ProductColorImage.DoesNotExist:
                pass
        return redirect('admin_product_colors', pk=product.id)

    # Довідник раніше використаних кольорів
    used_colors = Color.objects.order_by('primary_hex','secondary_hex').all()
    variants = (ProductColorVariant.objects.select_related('color')
                .prefetch_related('images')
                .filter(product=product).order_by('order','id'))
    return render(request, 'pages/admin_product_colors.html', {
        'product': product,
        'used_colors': used_colors,
        'variants': variants
    })


@login_required
def admin_product_new(request):
    """Створення нового товару"""
    if not request.user.is_staff:
        return redirect('home')
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Обробка форми товару
        if form_type == 'product':
            if form.is_valid():
                prod = form.save()
                
                # Якщо це AJAX запит, повертаємо JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({
                        'success': True,
                        'product_id': prod.id,
                        'message': 'Товар успішно створено!'
                    })
                
                return redirect('/admin-panel/?section=catalogs')
            else:
                # Якщо це AJAX запит з помилками, повертаємо JSON з помилками
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({
                        'success': False,
                        'errors': form.errors,
                        'message': 'Помилка валідації форми'
                    })
        
        # Обробка форми кольору
        elif form_type == 'color':
            product_id = request.POST.get('product_id')
            if not product_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Не вказано ID товару'
                })
            
            try:
                product = Product.objects.get(id=product_id)
                
                color_name = request.POST.get('color_name')
                primary_hex = request.POST.get('primary_hex')
                secondary_hex = request.POST.get('secondary_hex', '')
                color_images = request.FILES.getlist('color_images')
                
                if color_name and primary_hex and color_images:
                    
                    # Перевіряємо, чи існує вже такий колір
                    color = Color.objects.filter(
                        primary_hex=primary_hex,
                        secondary_hex=secondary_hex if secondary_hex else None
                    ).first()
                    
                    
                    if color:
                        # Якщо колір існує, оновлюємо його назву
                        color.name = color_name
                        color.save()
                    else:
                        # Створюємо новий колір з HEX кодами
                        color = Color.objects.create(
                            name=color_name,
                            primary_hex=primary_hex,
                            secondary_hex=secondary_hex if secondary_hex else None
                        )
                    
                    # Перевіряємо, чи не існує вже такий варіант кольору для цього товару
                    color_variant, created = ProductColorVariant.objects.get_or_create(
                        product=product,
                        color=color
                    )
                    
                    
                    # Додаємо зображення (завжди, якщо вони є)
                    if color_images:
                        for i, image_file in enumerate(color_images):
                            ProductColorImage.objects.create(
                                color_variant=color_variant,
                                image=image_file
                            )
                    
                    if created:
                        message = 'Колір успішно додано!'
                    else:
                        message = 'Колір вже існує для цього товару, але зображення додано!'
                    
                    return JsonResponse({
                        'success': True,
                        'color': {
                            'id': color.id,
                            'name': color.name,
                            'image_url': color_variant.images.first().image.url if color_variant.images.exists() else ''
                        },
                        'message': message
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Не всі обов\'язкові поля заповнені'
                    })
                    
            except Product.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Товар не знайдено'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Помилка створення кольору: {str(e)}'
                })
        
    return render(request, 'pages/admin_product_new.html', {'form': form})


@login_required
def admin_product_edit(request, pk):
    """Редагування товару (стара версія з підтримкою кольорів)"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Product, pk=pk)
    
    # Якщо прийшла дія з кольорами — обробляємо і повертаємося на цю ж сторінку
    action = (request.POST.get('action') or '').strip() if request.method == 'POST' else ''
    
    # Якщо це POST запит для кольорів, обробляємо його
    if action and request.method == 'POST':
        if action == 'add':
            color_id = request.POST.get('color_id')
            primary_hex = (request.POST.get('primary_hex') or '').strip() or '#000000'
            secondary_hex = (request.POST.get('secondary_hex') or '').strip() or None
            is_default = bool(request.POST.get('is_default'))
            order = int(request.POST.get('order') or 0)

            if color_id:
                color = get_object_or_404(Color, pk=color_id)
            else:
                color, _ = Color.objects.get_or_create(primary_hex=primary_hex, secondary_hex=secondary_hex)
            variant = ProductColorVariant.objects.create(product=obj, color=color, is_default=is_default, order=order)
            for f in request.FILES.getlist('images'):
                ProductColorImage.objects.create(variant=variant, image=f)
        elif action == 'delete_variant':
            vid = request.POST.get('variant_id')
            try:
                v = ProductColorVariant.objects.get(pk=vid, product=obj)
                v.delete()
            except ProductColorVariant.DoesNotExist:
                pass
        elif action == 'delete_image':
            iid = request.POST.get('image_id')
            try:
                img = ProductColorImage.objects.filter(variant__product=obj).get(pk=iid)
                img.delete()
            except ProductColorImage.DoesNotExist:
                pass
        return redirect('admin_product_edit', pk=obj.id)

    # Основна форма товару
    form = ProductForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST':
        
        # Перевіряємо, що це не запит для кольорів
        if not request.POST.get('action'):
            
            if form.is_valid():
                product = form.save(commit=False)
                # Автогенерація slug, якщо порожній
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                product.save()
                return redirect('/admin-panel/?section=catalogs')

    # Дані для блоку «Кольори»
    used_colors = Color.objects.order_by('primary_hex', 'secondary_hex').all()
    variants = (ProductColorVariant.objects.select_related('color')
                .prefetch_related('images')
                .filter(product=obj).order_by('order', 'id'))

    return render(
        request,
        'pages/admin_product_form.html',
        {'form': form, 'mode': 'edit', 'obj': obj, 'used_colors': used_colors, 'variants': variants}
    )


@login_required
def admin_product_edit_unified(request, pk):
    """Універсальне редагування товару з усіма налаштуваннями"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'product':
            form = ProductForm(request.POST, request.FILES, instance=obj)
            
            if form.is_valid():
                product = form.save(commit=False)
                
                # Автогенерація slug, якщо порожній
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                
                # Якщо головне зображення не вибрано, використовуємо першу фотографію першого кольору
                if not product.main_image:
                    first_color_variant = product.color_variants.first()
                    if first_color_variant:
                        first_image = first_color_variant.images.first()
                        if first_image:
                            product.main_image = first_image.image
                
                product.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Товар успішно збережено!'})
                return redirect('/admin-panel/?section=catalogs')
            else:
                # Повертаємо форму з помилками для відображення користувачу
                return render(request, 'pages/admin_product_edit_unified.html', {
                    'form': form, 
                    'obj': obj
                })
        
        elif form_type == 'color':
            color_name = request.POST.get('color_name')
            primary_hex = request.POST.get('primary_hex')
            secondary_hex = request.POST.get('secondary_hex', '')
            color_images = request.FILES.getlist('color_images')
            
            if color_name and primary_hex and color_images:
                # Створюємо колір з HEX кодами
                color = Color.objects.create(
                    name=color_name,
                    primary_hex=primary_hex,
                    secondary_hex=secondary_hex if secondary_hex else None
                )
                
                # Створюємо варіант кольору для товару
                color_variant = ProductColorVariant.objects.create(
                    product=obj,
                    color=color
                )
                
                # Створюємо зображення для варіанту кольору
                for i, image in enumerate(color_images):
                    ProductColorImage.objects.create(
                        variant=color_variant,
                        image=image,
                        order=i  # Зберігаємо порядок зображень
                    )
                
                # Якщо у товару немає головного зображення, використовуємо першу фотографію цього кольору
                if not obj.main_image and color_images:
                    obj.main_image = color_images[0]
                    obj.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': f'Колір успішно додано з {len(color_images)} зображеннями!'})
                return redirect(request.path)
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Колір успішно додано!'})
                return redirect(request.path)
        
        elif form_type == 'image':
            # Підтримка завантаження одного або кількох зображень
            files = []
            one = request.FILES.get('additional_image')
            many = request.FILES.getlist('additional_image')
            if many:
                files = many
            elif one:
                files = [one]
            
            created = 0
            for f in files:
                try:
                    ProductImage.objects.create(product=obj, image=f)
                    created += 1
                except Exception:
                    continue
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Додано зображень: {created}'})
            return redirect(request.path)
    
    form = ProductForm(instance=obj)
    
    return render(request, 'pages/admin_product_edit_unified.html', {
        'form': form, 
        'obj': obj
    })


@login_required
def admin_product_edit_simple(request, pk):
    """Спрощене редагування товару без кольорів"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            product = form.save(commit=False)
            # Автогенерація slug, якщо порожній
            if not getattr(product, 'slug', None):
                base = slugify(product.title or '')
                product.slug = unique_slugify(Product, base)
            product.save()
            return redirect('/admin-panel/?section=catalogs')
    else:
        form = ProductForm(instance=obj)
    
    return render(request, 'pages/admin_product_edit_simple.html', {
        'form': form, 
        'obj': obj
    })


@login_required
def admin_product_color_delete(request, product_pk, color_pk):
    """Видалення кольору товару"""
    if not request.user.is_staff:
        return redirect('home')
    product = get_object_or_404(Product, pk=product_pk)
    color_variant = get_object_or_404(ProductColorVariant, pk=color_pk, product=product)
    color_variant.delete()
    return redirect(f'/admin-panel/product/{product_pk}/edit-unified/')


@login_required
def admin_product_image_delete(request, product_pk, image_pk):
    """Видалення додаткового зображення товару"""
    if not request.user.is_staff:
        return redirect('home')
    product = get_object_or_404(Product, pk=product_pk)
    image = get_object_or_404(ProductImage, pk=image_pk, product=product)
    image.delete()
    return redirect(f'/admin-panel/product/{product_pk}/edit-unified/')


@login_required
def admin_product_delete(request, pk):
    """Видалення товару"""
    if not request.user.is_staff:
        return redirect('home')
    obj = get_object_or_404(Product, pk=pk)
    obj.delete()
    return redirect('/admin-panel/?section=catalogs')


# ==================== УПРАВЛІННЯ ПРОМОКОДАМИ ====================

class PromoCodeForm(forms.ModelForm):
    """Форма для створення/редагування промокодів"""
    class Meta:
        model = PromoCode
        fields = ['code', 'discount_type', 'discount_value', 'max_uses', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Введіть код або залиште порожнім для автогенерації'
            }),
            'discount_type': forms.Select(attrs={'class': 'form-select bg-elevate'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'step': '0.01',
                'min': '0'
            }),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'min': '0',
                'placeholder': '0 = безліміт'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        """Дозволяє залишити поле code порожнім для автоматичної генерації"""
        code = self.cleaned_data.get('code', '').strip()
        
        # Якщо код порожній, це нормально - він буде згенерований автоматично
        if not code:
            return ''
        
        # Якщо код вказаний, перевіряємо його унікальність
        if PromoCode.objects.filter(code=code).exists():
            if self.instance and self.instance.pk:
                # При редагуванні виключаємо поточний промокод
                if not PromoCode.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                    return code
            raise forms.ValidationError("Промокод з таким кодом вже існує")
        
        return code


@login_required
def admin_promocodes(request):
    """Список промокодів"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocodes = PromoCode.objects.all()
    
    # Підраховуємо статистику
    total_promocodes = promocodes.count()
    active_promocodes = promocodes.filter(is_active=True).count()
    
    return render(request, 'pages/admin_promocodes.html', {
        'promocodes': promocodes,
        'total_promocodes': total_promocodes,
        'active_promocodes': active_promocodes,
        'section': 'promocodes'
    })


@login_required
def admin_promocode_create(request):
    """Створення нового промокоду"""
    if not request.user.is_staff:
        return redirect('home')
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promocode = form.save(commit=False)
            
            # Якщо код не вказаний або порожній, генеруємо автоматично
            if not promocode.code or promocode.code.strip() == '':
                promocode.code = PromoCode.generate_code()
            
            promocode.save()
            return redirect('admin_promocodes')
    else:
        form = PromoCodeForm()
    
    return render(request, 'pages/admin_promocode_form.html', {
        'form': form,
        'mode': 'create',
        'section': 'promocodes'
    })


@login_required
def admin_promocode_edit(request, pk):
    """Редагування промокоду"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST, instance=promocode)
        if form.is_valid():
            edited_promocode = form.save(commit=False)
            
            # Якщо код не вказаний або порожній, генеруємо автоматично
            if not edited_promocode.code or edited_promocode.code.strip() == '':
                edited_promocode.code = PromoCode.generate_code()
            
            edited_promocode.save()
            return redirect('admin_promocodes')
    else:
        form = PromoCodeForm(instance=promocode)
    
    return render(request, 'pages/admin_promocode_form.html', {
        'form': form,
        'mode': 'edit',
        'promocode': promocode,
        'section': 'promocodes'
    })


@login_required
def admin_promocode_toggle(request, pk):
    """Активація/деактивація промокоду"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.is_active = not promocode.is_active
    promocode.save()
    
    return redirect('admin_promocodes')


@login_required
def admin_promocode_delete(request, pk):
    """Видалення промокоду"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.delete()
    
    return redirect('admin_promocodes')


# ==================== СТАРІ ФУНКЦІЇ (БАЗОВІ ЗАГЛУШКИ) ====================
# Ці функції вже є в поточному admin.py, залишаємо як є

@staff_member_required
def admin_dashboard(request):
    """Головна сторінка адміністративної панелі"""
    from orders.models import Order
    from datetime import timedelta
    from django.utils import timezone
    
    # Статистика за останні 30 днів
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
    
    # Останні замовлення
    recent_orders = Order.objects.order_by('-created')[:10]
    
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
    """Список всіх товарів з можливістю фільтрації"""
    products = Product.objects.select_related('category').order_by('-id')
    
    # Фільтри
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
    """Додавання нового товару через уніфікований інтерфейс"""
    # Перенаправляємо на admin_product_new
    return admin_product_new(request)


@login_required
def add_category(request):
    """Додавання нової категорії"""
    # Перенаправляємо на admin_category_new
    return admin_category_new(request)


def add_print(request):
    """Сторінка пропозиції принтів від користувачів"""
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
    """Адміністративна панель для управління пропозиціями принтів"""
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
    """Управління промокодами"""
    # Перенаправляємо на admin_promocodes
    return admin_promocodes(request)


@staff_member_required
def generate_seo_content(request):
    """Генерація SEO контенту з допомогою AI (OpenAI)"""
    # TODO: Повна реалізація AI генерації
    return render(request, 'admin/generate_seo.html')


@staff_member_required
def generate_alt_texts(request):
    """Генерація ALT текстів для зображень"""
    # TODO: Реалізувати генерацію alt текстів
    return render(request, 'admin/generate_alt_texts.html')


@staff_member_required
def manage_orders(request):
    """Управління замовленнями"""
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
    """Статистика продажів"""
    # TODO: Реалізувати детальну статистику
    return render(request, 'admin/sales_statistics.html')


@staff_member_required
def inventory_management(request):
    """Управління складом"""
    # TODO: Реалізувати управління складом
    return render(request, 'admin/inventory.html')
