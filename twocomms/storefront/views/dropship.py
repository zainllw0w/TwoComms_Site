"""
Dropshipping views - Управление дропшиппингом.

Содержит views для:
- Управления заказами дропшипперов (DropshipperOrder)
- Обновления статусов заказов
- Получения и редактирования данных заказов
- Удаления заказов (только для staff)
"""

import logging
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required

from orders.models import DropshipperOrder
from orders.telegram_notifications import telegram_notifier

# Logger
dropship_logger = logging.getLogger('storefront.dropship')


# ==================== DROPSHIPPER ORDER MANAGEMENT ====================

@require_POST
@staff_member_required
def admin_update_dropship_status(request, order_id):
    """
    Обновление статуса заказа дропшипера (только для staff).
    
    Args:
        request: HTTP request with JSON body containing 'status'
        order_id: Dropshipper order ID
        
    Returns:
        JsonResponse: Success/error response
    """
    try:
        data = json.loads(request.body or '{}')
        new_status = data.get('status')
        
        # Валидные статусы
        allowed_statuses = ['draft', 'pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
        if new_status not in allowed_statuses:
            return JsonResponse({'success': False, 'error': 'Невірний статус'}, status=400)
        
        order = DropshipperOrder.objects.get(id=order_id)
        old_status = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        
        # Отправляем уведомление дропшиперу о изменении статуса
        try:
            telegram_notifier.send_order_status_update(order, old_status, new_status)
        except Exception as e:
            dropship_logger.warning(f'Ошибка отправки уведомления: {e}')
        
        return JsonResponse({
            'success': True,
            'message': f'Статус замовлення оновлено на {order.get_status_display()}'
        })
        
    except DropshipperOrder.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'}, status=404)
    except Exception as e:
        dropship_logger.exception(f'Error updating dropship status: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def admin_get_dropship_order(request, order_id):
    """
    Получение данных заказа дропшипера для редактирования.
    
    Args:
        request: HTTP request
        order_id: Dropshipper order ID
        
    Returns:
        JsonResponse: Order data or error
    """
    try:
        order = DropshipperOrder.objects.get(id=order_id)
        data = {
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'tracking_number': order.tracking_number or '',
            'client_name': order.client_name or '',
            'client_phone': order.client_phone or '',
            'client_np_address': order.client_np_address or '',
            'total_selling_price': float(order.total_selling_price),
            'total_drop_price': float(order.total_drop_price),
            'profit': float(order.profit),
        }
        return JsonResponse(data)
    except DropshipperOrder.DoesNotExist:
        return JsonResponse({'error': 'Замовлення не знайдено'}, status=404)
    except Exception as e:
        dropship_logger.exception(f'Error getting dropship order: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@staff_member_required
def admin_update_dropship_order(request, order_id):
    """
    Обновление данных заказа дропшипера (полное редактирование).
    
    Args:
        request: HTTP request with JSON body
        order_id: Dropshipper order ID
        
    Returns:
        JsonResponse: Success/error response
    """
    try:
        order = DropshipperOrder.objects.get(id=order_id)
        data = json.loads(request.body or '{}')
        
        old_status = order.status
        old_ttn = order.tracking_number
        
        # Обновляем поля
        if 'status' in data:
            order.status = data['status']
        if 'tracking_number' in data:
            order.tracking_number = data['tracking_number'].strip() or None
        if 'client_name' in data:
            order.client_name = data['client_name'].strip()
        if 'client_phone' in data:
            order.client_phone = data['client_phone'].strip()
        if 'client_np_address' in data:
            order.client_np_address = data['client_np_address'].strip()
        
        order.save()
        
        # Отправляем уведомления если изменился статус или добавился ТТН
        try:
            if old_status != order.status:
                telegram_notifier.send_order_status_update(order, old_status, order.status)
            
            # Если добавили ТТН - уведомляем дропшипера
            if not old_ttn and order.tracking_number:
                telegram_notifier.send_ttn_notification(order)
        except Exception as e:
            dropship_logger.warning(f'Ошибка отправки уведомления: {e}')
        
        return JsonResponse({
            'success': True,
            'message': 'Замовлення успішно оновлено'
        })
        
    except DropshipperOrder.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'}, status=404)
    except Exception as e:
        dropship_logger.exception(f'Error updating dropship order: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@staff_member_required
def admin_delete_dropship_order(request, order_id):
    """
    Удаление заказа дропшипера (админ может удалять любые заказы).
    
    Args:
        request: HTTP request
        order_id: Dropshipper order ID
        
    Returns:
        JsonResponse: Success/error response
    """
    try:
        order = DropshipperOrder.objects.get(id=order_id)
        
        # Админ может удалять любые заказы
        # Но показываем предупреждение для доставленных заказов в UI
        order_number = order.order_number
        dropshipper_name = order.dropshipper.username if order.dropshipper else 'Невідомий'
        
        order.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Замовлення {order_number} (дропшипер: {dropshipper_name}) видалено'
        })
        
    except DropshipperOrder.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'}, status=404)
    except Exception as e:
        dropship_logger.exception(f'Error deleting dropship order: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

