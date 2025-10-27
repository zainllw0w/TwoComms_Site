"""
Promo codes views - Управление промокодами.

Содержит views для:
- Админ-панели промокодов
- Управления группами промокодов
- Создания/редактирования/удаления промокодов
- Статистики использования
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django import forms

from ..models import PromoCode, PromoCodeGroup, PromoCodeUsage


# ==================== FORMS ====================

class PromoCodeGroupForm(forms.ModelForm):
    """Форма для создания/редактирования группы промокодов"""
    class Meta:
        model = PromoCodeGroup
        fields = ['name', 'description', 'one_per_account', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Назва групи (наприклад, "Instagram реклама")'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control bg-elevate',
                'rows': 3,
                'placeholder': 'Опис групи промокодів'
            }),
            'one_per_account': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PromoCodeForm(forms.ModelForm):
    """Форма для создания/редактирования промокода"""
    class Meta:
        model = PromoCode
        fields = [
            'code', 'promo_type', 'discount_type', 'discount_value', 
            'description', 'group', 'max_uses', 'one_time_per_user',
            'min_order_amount', 'valid_from', 'valid_until', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Введіть код або залиште порожнім для автогенерації'
            }),
            'promo_type': forms.Select(attrs={'class': 'form-select bg-elevate'}),
            'discount_type': forms.Select(attrs={'class': 'form-select bg-elevate'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'step': '0.01',
                'min': '0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control bg-elevate',
                'rows': 3,
                'placeholder': 'Опис промокоду (необов\'язково)'
            }),
            'group': forms.Select(attrs={'class': 'form-select bg-elevate'}),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'min': '0',
                'placeholder': '0 = безліміт'
            }),
            'one_time_per_user': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_order_amount': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Мінімальна сума (необов\'язково)'
            }),
            'valid_from': forms.DateTimeInput(attrs={
                'class': 'form-control bg-elevate',
                'type': 'datetime-local'
            }),
            'valid_until': forms.DateTimeInput(attrs={
                'class': 'form-control bg-elevate',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        """Позволяет оставить поле code пустым для автоматической генерации"""
        code = self.cleaned_data.get('code', '').strip()
        
        # Если код пустой, это нормально - он будет сгенерирован автоматически
        if not code:
            return ''
        
        # Если код указан, проверяем его уникальность
        if PromoCode.objects.filter(code=code).exists():
            if self.instance and self.instance.pk:
                # При редактировании исключаем текущий промокод
                if not PromoCode.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                    return code
            raise forms.ValidationError("Промокод з таким кодом вже існує")
        
        return code


# ==================== HELPER FUNCTIONS ====================

def get_promo_admin_context(request):
    """Функція для отримання контексту промокодів для адмін-панелі"""
    from django.db.models import Q, Count
    
    # Получаем текущий таб
    promo_tab = request.GET.get('tab', 'promocodes')
    
    # Получаем параметры фильтрации для промокодов
    view_type = request.GET.get('view', 'all')
    group_id = request.GET.get('group')
    
    # ===== ТАБ 1: ПРОМОКОДЫ =====
    promocodes = PromoCode.objects.select_related('group').prefetch_related('usages').all()
    
    # Фильтрация по типу
    if view_type == 'vouchers':
        promocodes = promocodes.filter(promo_type='voucher')
    elif view_type == 'grouped':
        promocodes = promocodes.filter(promo_type='grouped', group__isnull=False)
    elif view_type == 'regular':
        promocodes = promocodes.filter(promo_type='regular')
    
    # Фильтрация по группе
    if group_id:
        promocodes = promocodes.filter(group_id=group_id)
    
    # ===== ТАБ 2: ГРУППЫ =====
    groups = PromoCodeGroup.objects.prefetch_related('promo_codes').annotate(
        codes_count=Count('promo_codes'),
        active_codes_count=Count('promo_codes', filter=Q(promo_codes__is_active=True)),
        total_usages=Count('usages')
    )
    
    # ===== ТАБ 3: СТАТИСТИКА =====
    # Последние использования
    recent_usages = PromoCodeUsage.objects.select_related(
        'user', 'promo_code', 'group', 'order'
    ).order_by('-used_at')[:50]
    
    # Топ промокодов
    top_promos = PromoCode.objects.annotate(
        usage_count=Count('usages')
    ).filter(usage_count__gt=0).order_by('-usage_count')[:10]
    
    # Топ групп
    top_groups = PromoCodeGroup.objects.annotate(
        usage_count=Count('usages')
    ).filter(usage_count__gt=0).order_by('-usage_count')[:10]
    
    # ===== ОБЩАЯ СТАТИСТИКА =====
    total_promocodes = PromoCode.objects.count()
    active_promocodes = PromoCode.objects.filter(is_active=True).count()
    total_vouchers = PromoCode.objects.filter(promo_type='voucher').count()
    total_groups = groups.count()
    total_usages = PromoCodeUsage.objects.count()
    unique_users = PromoCodeUsage.objects.values('user').distinct().count()
    
    return {
        # Навигация
        'promo_tab': promo_tab,
        'view_type': view_type,
        'current_group_id': int(group_id) if group_id else None,
        
        # Таб 1: Промокоды
        'promocodes': promocodes,
        
        # Таб 2: Группы
        'groups': groups,
        
        # Таб 3: Статистика
        'recent_usages': recent_usages,
        'top_promos': top_promos,
        'top_groups': top_groups,
        
        # Общая статистика
        'total_promocodes': total_promocodes,
        'active_promocodes': active_promocodes,
        'total_vouchers': total_vouchers,
        'total_groups': total_groups,
        'total_usages': total_usages,
        'unique_users': unique_users,
    }


# ==================== ADMIN VIEWS ====================

@login_required
def admin_promocodes(request):
    """
    DEPRECATED: Ця view більше не використовується.
    Промокоди тепер в головній адмін-панелі через ?section=promocodes
    Редирект для backward compatibility
    """
    return redirect('/admin-panel/?section=promocodes')


@login_required
def admin_promocode_create(request):
    """Создание нового промокода (поддержка AJAX)"""
    if not request.user.is_staff:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
        return redirect('home')
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promocode = form.save(commit=False)
            
            # Если код не указан или пустой, генерируем автоматически
            if not promocode.code or promocode.code.strip() == '':
                promocode.code = PromoCode.generate_code()
            
            promocode.save()
            
            # AJAX ответ
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Промокод успішно створено',
                    'promo_id': promocode.id,
                    'promo_code': promocode.code
                })
            
            return redirect('/admin-panel/?section=promocodes&tab=promocodes')
        else:
            # AJAX ответ с ошибками
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Помилка валідації',
                    'errors': form.errors
                }, status=400)
    else:
        form = PromoCodeForm()
    
    return render(request, 'pages/admin_promocode_form.html', {
        'form': form,
        'mode': 'create',
        'section': 'promocodes'
    })


@login_required
def admin_promocode_edit(request, pk):
    """Редактирование промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST, instance=promocode)
        if form.is_valid():
            edited_promocode = form.save(commit=False)
            
            # Если код не указан или пустой, генерируем автоматически
            if not edited_promocode.code or edited_promocode.code.strip() == '':
                edited_promocode.code = PromoCode.generate_code()
            
            edited_promocode.save()
            return redirect('/admin-panel/?section=promocodes&tab=promocodes')
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
    """Активация/деактивация промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.is_active = not promocode.is_active
    promocode.save()
    
    return redirect('/admin-panel/?section=promocodes&tab=promocodes')


@login_required
def admin_promocode_delete(request, pk):
    """Удаление промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.delete()
    
    return redirect('/admin-panel/?section=promocodes&tab=promocodes')


# ==================== PROMO CODE GROUPS ====================

@login_required
def admin_promo_groups(request):
    """Редирект на единую панель промокодов (таб Групи)"""
    return redirect('/admin-panel/?section=promocodes&tab=groups')


@login_required
def admin_promo_group_create(request):
    """Создание новой группы промокодов (поддержка AJAX)"""
    if not request.user.is_staff:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
        return redirect('home')
    
    if request.method == 'POST':
        form = PromoCodeGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            
            # AJAX ответ
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Групу успішно створено',
                    'group_id': group.id,
                    'group_name': group.name
                })
            
            return redirect('/admin-panel/?section=promocodes&tab=groups')
        else:
            # AJAX ответ с ошибками
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Помилка валідації',
                    'errors': form.errors
                }, status=400)
    else:
        form = PromoCodeGroupForm()
    
    return render(request, 'pages/admin_promo_group_form.html', {
        'form': form,
        'mode': 'create',
        'section': 'promocodes'
    })


@login_required
def admin_promo_group_edit(request, pk):
    """Редактирование группы промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    group = get_object_or_404(PromoCodeGroup, pk=pk)
    
    if request.method == 'POST':
        form = PromoCodeGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            return redirect('/admin-panel/?section=promocodes&tab=groups')
    else:
        form = PromoCodeGroupForm(instance=group)
    
    # Получаем промокоды этой группы
    promocodes = PromoCode.objects.filter(group=group)
    
    return render(request, 'pages/admin_promo_group_form.html', {
        'form': form,
        'mode': 'edit',
        'group': group,
        'promocodes': promocodes,
        'section': 'promocodes'
    })


@login_required
def admin_promo_group_delete(request, pk):
    """Удаление группы промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    group = get_object_or_404(PromoCodeGroup, pk=pk)
    
    # При удалении группы, промокоды остаются, но теряют связь с группой
    PromoCode.objects.filter(group=group).update(group=None)
    
    group.delete()
    
    return redirect('/admin-panel/?section=promocodes&tab=groups')


# ==================== STATISTICS ====================

@login_required
def admin_promo_stats(request):
    """Редирект на единую панель промокодов (таб Статистика)"""
    return redirect('/admin-panel/?section=promocodes&tab=stats')


# ==================== AJAX ENDPOINTS ====================

@login_required
def admin_promocode_get_form(request, pk):
    """
    AJAX endpoint: Получить данные промокода для формы редактирования
    GET /admin-panel/promocode/<id>/get-form/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Тільки AJAX запити'}, status=400)
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    groups = PromoCodeGroup.objects.filter(is_active=True)
    
    # Преобразуем даты в ISO формат для datetime-local input
    valid_from = promocode.valid_from.strftime('%Y-%m-%dT%H:%M') if promocode.valid_from else ''
    valid_until = promocode.valid_until.strftime('%Y-%m-%dT%H:%M') if promocode.valid_until else ''
    
    return JsonResponse({
        'success': True,
        'promo': {
            'id': promocode.id,
            'code': promocode.code,
            'promo_type': promocode.promo_type,
            'discount': float(promocode.discount) if promocode.discount else None,
            'fixed_amount': float(promocode.fixed_amount) if promocode.fixed_amount else None,
            'description': promocode.description or '',
            'group_id': promocode.group.id if promocode.group else None,
            'min_order_amount': float(promocode.min_order_amount) if promocode.min_order_amount else None,
            'usage_limit': promocode.usage_limit,
            'one_time_per_user': promocode.one_time_per_user,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'is_active': promocode.is_active,
        },
        'groups': [{'id': g.id, 'name': g.name} for g in groups]
    })


@login_required
def admin_promocode_edit_ajax(request, pk):
    """
    AJAX endpoint: Обновить промокод
    POST /admin-panel/promocode/<id>/edit-ajax/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Тільки AJAX запити'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Тільки POST запити'}, status=405)
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    form = PromoCodeForm(request.POST, instance=promocode)
    
    if form.is_valid():
        updated_promo = form.save(commit=False)
        
        # Если код пустой, генерируем
        if not updated_promo.code or updated_promo.code.strip() == '':
            updated_promo.code = PromoCode.generate_code()
        
        updated_promo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Промокод успішно оновлено',
            'promo_id': updated_promo.id,
            'promo_code': updated_promo.code
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Помилка валідації',
            'errors': form.errors
        }, status=400)


@login_required
def admin_promo_group_get_form(request, pk):
    """
    AJAX endpoint: Получить данные группы для формы редактирования
    GET /admin-panel/promo-group/<id>/get-form/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Тільки AJAX запити'}, status=400)
    
    group = get_object_or_404(PromoCodeGroup, pk=pk)
    promocodes = PromoCode.objects.filter(group=group).order_by('-created_at')
    
    return JsonResponse({
        'success': True,
        'group': {
            'id': group.id,
            'name': group.name,
            'description': group.description or '',
            'one_per_account': group.one_per_account,
            'is_active': group.is_active,
        },
        'promocodes': [{
            'id': p.id,
            'code': p.code,
            'is_active': p.is_active,
            'times_used': p.times_used,
            'usage_limit': p.usage_limit,
            'promo_type': p.promo_type,
        } for p in promocodes]
    })


@login_required
def admin_promo_group_edit_ajax(request, pk):
    """
    AJAX endpoint: Обновить группу промокодов
    POST /admin-panel/promo-group/<id>/edit-ajax/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Тільки AJAX запити'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Тільки POST запити'}, status=405)
    
    group = get_object_or_404(PromoCodeGroup, pk=pk)
    form = PromoCodeGroupForm(request.POST, instance=group)
    
    if form.is_valid():
        updated_group = form.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Групу успішно оновлено',
            'group_id': updated_group.id,
            'group_name': updated_group.name
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Помилка валідації',
            'errors': form.errors
        }, status=400)


@login_required
def admin_promocode_change_group(request, pk):
    """
    AJAX endpoint: Змінити групу промокода (Drag & Drop)
    POST /admin-panel/promocode/<id>/change-group/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)
    
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Тільки AJAX запити'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Тільки POST запити'}, status=405)
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    
    try:
        import json
        data = json.loads(request.body)
        group_id = data.get('group_id')
        
        if group_id:
            group = get_object_or_404(PromoCodeGroup, pk=group_id)
            promocode.group = group
            promocode.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Промокод переміщено до групи "{group.name}"',
                'group_id': group.id,
                'group_name': group.name
            })
        else:
            # Прибрати з групи
            promocode.group = None
            promocode.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Промокод прибрано з групи',
                'group_id': None,
                'group_name': None
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невірний JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

