"""
Система мониторинга производительности
"""
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
import time
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Мониторинг производительности приложения
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.queries_count = len(connection.queries)
    
    def get_metrics(self):
        """
        Получает метрики производительности
        """
        end_time = time.time()
        execution_time = end_time - self.start_time
        queries_executed = len(connection.queries) - self.queries_count
        
        return {
            'execution_time': execution_time,
            'queries_count': queries_executed,
            'timestamp': timezone.now(),
        }
    
    def log_slow_request(self, request, threshold=1.0):
        """
        Логирует медленные запросы
        """
        metrics = self.get_metrics()
        
        if metrics['execution_time'] > threshold:
            logger.warning(
                f"Slow request detected: {request.path} - "
                f"{metrics['execution_time']:.2f}s, "
                f"{metrics['queries_count']} queries"
            )
    
    def cache_performance_metrics(self, view_name, metrics):
        """
        Кэширует метрики производительности
        """
        cache_key = f"perf_metrics_{view_name}_{timezone.now().strftime('%Y%m%d%H')}"
        cache.set(cache_key, metrics, 3600)  # 1 час

def performance_middleware(get_response):
    """
    Middleware для мониторинга производительности
    """
    def middleware(request):
        monitor = PerformanceMonitor()
        
        response = get_response(request)
        
        # Логируем медленные запросы
        monitor.log_slow_request(request)
        
        # Добавляем заголовки производительности
        metrics = monitor.get_metrics()
        response['X-Execution-Time'] = f"{metrics['execution_time']:.3f}"
        response['X-Query-Count'] = str(metrics['queries_count'])
        
        return response
    
    return middleware

class DatabaseOptimizer:
    """
    Оптимизатор базы данных
    """
    
    @staticmethod
    def get_slow_queries(threshold=0.1):
        """
        Получает медленные запросы
        """
        slow_queries = []
        
        for query in connection.queries:
            if float(query['time']) > threshold:
                slow_queries.append({
                    'sql': query['sql'],
                    'time': query['time']
                })
        
        return slow_queries
    
    @staticmethod
    def analyze_query_performance():
        """
        Анализирует производительность запросов
        """
        total_time = sum(float(q['time']) for q in connection.queries)
        total_queries = len(connection.queries)
        
        return {
            'total_time': total_time,
            'total_queries': total_queries,
            'average_time': total_time / total_queries if total_queries > 0 else 0,
            'slow_queries': DatabaseOptimizer.get_slow_queries()
        }

class CacheOptimizer:
    """
    Оптимизатор кэширования
    """
    
    @staticmethod
    def get_cache_stats():
        """
        Получает статистику кэша
        """
        # Здесь можно добавить логику для получения статистики кэша
        # В зависимости от используемого бэкенда кэша
        return {
            'cache_hits': 0,  # Заглушка
            'cache_misses': 0,  # Заглушка
            'cache_size': 0,  # Заглушка
        }
    
    @staticmethod
    def optimize_cache_keys():
        """
        Оптимизирует ключи кэша
        """
        # Логика для оптимизации ключей кэша
        pass

class SEOOptimizer:
    """
    Оптимизатор SEO
    """
    
    @staticmethod
    def check_page_seo(request, response):
        """
        Проверяет SEO страницы
        """
        issues = []
        
        # Проверяем наличие title
        if '<title>' not in response.content.decode():
            issues.append('Missing title tag')
        
        # Проверяем наличие meta description
        if 'name="description"' not in response.content.decode():
            issues.append('Missing meta description')
        
        # Проверяем наличие h1
        if '<h1>' not in response.content.decode():
            issues.append('Missing h1 tag')
        
        return issues
    
    @staticmethod
    def generate_structured_data(product=None):
        """
        Генерирует структурированные данные
        """
        if product:
            return {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": product.title,
                "description": product.description,
                "image": product.image.url if product.image else None,
                "offers": {
                    "@type": "Offer",
                    "price": str(product.price),
                    "priceCurrency": "UAH",
                    "availability": "https://schema.org/InStock" if product.is_active else "https://schema.org/OutOfStock"
                }
            }
        
        return None
