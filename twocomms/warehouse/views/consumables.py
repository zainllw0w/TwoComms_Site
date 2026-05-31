"""Views для управління розхідними матеріалами — БЛОК 4."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from warehouse.models import ConsumableItem
from warehouse.services import consumables as consumables_service


@login_required
def consumables_list(request):
    """Список всіх розхідних матеріалів."""
    qs = ConsumableItem.objects.all().order_by('category', 'name')

    # Фільтр по категорії
    category = request.GET.get('category')
    if category:
        qs = qs.filter(category=category)

    # Фільтр по низьким залишкам
    low_stock = request.GET.get('low_stock')
    if low_stock == '1':
        qs = qs.filter(quantity__lte=F('min_stock_alert'))

    # Статистика
    total_value = consumables_service.consumables_total_value()
    low_stock_items = ConsumableItem.objects.filter(
        quantity__lte=F('min_stock_alert')
    ).count()

    return render(request, 'warehouse/consumables_list.html', {
        'consumables': qs,
        'total_value': total_value,
        'low_stock_count': low_stock_items,
        'categories': ConsumableItem.CATEGORY_CHOICES,
        'current_category': category,
        'show_low_stock': low_stock == '1',
    })


@login_required
def consumable_detail(request, pk):
    """Детальна інформація про розхідний матеріал."""
    consumable = get_object_or_404(ConsumableItem, pk=pk)

    # Історія руху
    from django.contrib.contenttypes.models import ContentType
    from warehouse.models import StockMovement

    movements = StockMovement.objects.filter(
        content_type=ContentType.objects.get_for_model(ConsumableItem),
        object_id=consumable.pk
    ).select_related('created_by', 'order').order_by('-created_at')[:50]

    return render(request, 'warehouse/consumable_detail.html', {
        'consumable': consumable,
        'movements': movements,
    })


@login_required
def consumable_create(request):
    """Створення нового розхідного матеріалу."""
    if request.method == 'POST':
        try:
            consumable = ConsumableItem.objects.create(
                category=request.POST['category'],
                name=request.POST['name'],
                quantity=Decimal(request.POST.get('quantity', '0')),
                unit=request.POST.get('unit', 'шт'),
                cost_per_unit=Decimal(request.POST.get('cost_per_unit', '0')),
                total_cost=Decimal(request.POST.get('quantity', '0')) * Decimal(request.POST.get('cost_per_unit', '0')),
                purchase_date=request.POST['purchase_date'],
                min_stock_alert=Decimal(request.POST.get('min_stock_alert', '0')),
                notes=request.POST.get('notes', ''),
            )

            # Якщо вказано постачальника
            supplier_id = request.POST.get('supplier_id')
            if supplier_id:
                from finance.models import Counterparty
                consumable.supplier_id = supplier_id
                consumable.save()

            messages.success(request, f'Розхідник "{consumable.name}" створено')
            return redirect('warehouse:consumable_detail', pk=consumable.pk)
        except Exception as e:
            messages.error(request, f'Помилка: {e}')

    # Список постачальників для вибору
    from finance.models import Counterparty
    suppliers = Counterparty.objects.filter(type='supplier').order_by('name')

    return render(request, 'warehouse/consumable_form.html', {
        'categories': ConsumableItem.CATEGORY_CHOICES,
        'suppliers': suppliers,
        'is_create': True,
    })


@login_required
def consumable_edit(request, pk):
    """Редагування розхідного матеріалу."""
    consumable = get_object_or_404(ConsumableItem, pk=pk)

    if request.method == 'POST':
        try:
            consumable.category = request.POST['category']
            consumable.name = request.POST['name']
            consumable.unit = request.POST.get('unit', 'шт')
            consumable.cost_per_unit = Decimal(request.POST.get('cost_per_unit', '0'))
            consumable.min_stock_alert = Decimal(request.POST.get('min_stock_alert', '0'))
            consumable.notes = request.POST.get('notes', '')

            supplier_id = request.POST.get('supplier_id')
            if supplier_id:
                consumable.supplier_id = supplier_id
            else:
                consumable.supplier = None

            consumable.save()
            messages.success(request, f'Розхідник "{consumable.name}" оновлено')
            return redirect('warehouse:consumable_detail', pk=consumable.pk)
        except Exception as e:
            messages.error(request, f'Помилка: {e}')

    from finance.models import Counterparty
    suppliers = Counterparty.objects.filter(type='supplier').order_by('name')

    return render(request, 'warehouse/consumable_form.html', {
        'consumable': consumable,
        'categories': ConsumableItem.CATEGORY_CHOICES,
        'suppliers': suppliers,
        'is_create': False,
    })


@require_POST
@login_required
def consumable_adjust(request, pk):
    """Коригування кількості розхідного матеріалу."""
    consumable = get_object_or_404(ConsumableItem, pk=pk)

    try:
        action = request.POST.get('action')  # 'add' або 'use'
        quantity = Decimal(request.POST['quantity'])
        comment = request.POST.get('comment', '')

        if action == 'add':
            cost_per_unit = Decimal(request.POST.get('cost_per_unit', consumable.cost_per_unit))
            consumables_service.add_consumable_stock(
                consumable=consumable,
                quantity=quantity,
                cost_per_unit=cost_per_unit,
                user=request.user,
                comment=comment,
            )
            messages.success(request, f'Додано {quantity} {consumable.unit}')
        elif action == 'use':
            consumables_service.use_consumable(
                consumable=consumable,
                quantity=quantity,
                user=request.user,
                comment=comment,
            )
            messages.success(request, f'Списано {quantity} {consumable.unit}')
        else:
            messages.error(request, 'Невідома дія')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Помилка: {e}')

    return redirect('warehouse:consumable_detail', pk=consumable.pk)


@login_required
def consumables_low_stock_api(request):
    """API для отримання розхідників з низьким залишком."""
    low_stock = consumables_service.get_low_stock_consumables()

    data = [{
        'id': c.id,
        'name': c.name,
        'category': c.get_category_display(),
        'quantity': float(c.quantity),
        'unit': c.unit,
        'min_stock_alert': float(c.min_stock_alert),
    } for c in low_stock]

    return JsonResponse({'items': data})
