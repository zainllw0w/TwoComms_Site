from cache_utils import get_cache

def orders_processing_count(request):
    """
    Контекстный процессор для добавления счетчика заказов в обработке
    """
    if request.user.is_authenticated and request.user.is_staff:
        try:
            cache_key = 'orders_processing_count'
            cache_backend = get_cache('fragments')
            processing_count = cache_backend.get(cache_key)
            if processing_count is None:
                from orders.models import Order
                processing_count = Order.get_processing_count()
                cache_backend.set(cache_key, processing_count, 60)
        except Exception:
            processing_count = 0
    else:
        processing_count = 0
    
    return {
        'orders_processing_count': processing_count
    }
