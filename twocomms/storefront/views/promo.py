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


# ==================== ADMIN VIEWS ====================

@login_required
def admin_promocodes(request):
    """Список промокодов с поддержкой групп и фильтрации"""
    if not request.user.is_staff:
        return redirect('home')
    
    # Получаем параметры фильтрации
    view_type = request.GET.get('view', 'all')  # all, groups, vouchers
    group_id = request.GET.get('group')
    
    # Базовый запрос
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
    
    # Получаем все группы
    groups = PromoCodeGroup.objects.prefetch_related('promo_codes').annotate(
        codes_count=Count('promo_codes'),
        active_codes_count=Count('promo_codes', filter=Q(promo_codes__is_active=True))
    )
    
    # Подсчитываем статистику
    total_promocodes = PromoCode.objects.count()
    active_promocodes = PromoCode.objects.filter(is_active=True).count()
    total_vouchers = PromoCode.objects.filter(promo_type='voucher').count()
    total_groups = groups.count()
    total_usages = PromoCodeUsage.objects.count()
    
    return render(request, 'pages/admin_promocodes.html', {
        'promocodes': promocodes,
        'groups': groups,
        'total_promocodes': total_promocodes,
        'active_promocodes': active_promocodes,
        'total_vouchers': total_vouchers,
        'total_groups': total_groups,
        'total_usages': total_usages,
        'view_type': view_type,
        'current_group_id': int(group_id) if group_id else None,
        'section': 'promocodes'
    })


@login_required
def admin_promocode_create(request):
    """Создание нового промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promocode = form.save(commit=False)
            
            # Если код не указан или пустой, генерируем автоматически
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
    """Активация/деактивация промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.is_active = not promocode.is_active
    promocode.save()
    
    return redirect('admin_promocodes')


@login_required
def admin_promocode_delete(request, pk):
    """Удаление промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.delete()
    
    return redirect('admin_promocodes')


# ==================== PROMO CODE GROUPS ====================

@login_required
def admin_promo_groups(request):
    """Список групп промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    groups = PromoCodeGroup.objects.prefetch_related('promo_codes').annotate(
        codes_count=Count('promo_codes'),
        active_codes_count=Count('promo_codes', filter=Q(promo_codes__is_active=True)),
        total_usages=Count('usages')
    )
    
    return render(request, 'pages/admin_promo_groups.html', {
        'groups': groups,
        'section': 'promocodes'
    })


@login_required
def admin_promo_group_create(request):
    """Создание новой группы промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    if request.method == 'POST':
        form = PromoCodeGroupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_promo_groups')
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
            return redirect('admin_promo_groups')
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
    
    return redirect('admin_promo_groups')


# ==================== STATISTICS ====================

@login_required
def admin_promo_stats(request):
    """Статистика использования промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    # Последние использования
    recent_usages = PromoCodeUsage.objects.select_related(
        'user', 'promo_code', 'group', 'order'
    ).order_by('-used_at')[:50]
    
    # Топ промокодов по использованию
    top_promos = PromoCode.objects.annotate(
        usage_count=Count('usages')
    ).order_by('-usage_count')[:10]
    
    # Топ групп по использованию
    top_groups = PromoCodeGroup.objects.annotate(
        usage_count=Count('usages')
    ).order_by('-usage_count')[:10]
    
    # Общая статистика
    total_usages = PromoCodeUsage.objects.count()
    unique_users = PromoCodeUsage.objects.values('user').distinct().count()
    
    return render(request, 'pages/admin_promo_stats.html', {
        'recent_usages': recent_usages,
        'top_promos': top_promos,
        'top_groups': top_groups,
        'total_usages': total_usages,
        'unique_users': unique_users,
        'section': 'promocodes'
    })

