"""
Django REST Framework ViewSets for Storefront API.

ViewSets обеспечивают CRUD операции и кастомные endpoints для API.
Используют сериализаторы для преобразования данных в JSON.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django.db.models import Q, Count

from .models import Product, Category
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    CategorySerializer,
    CartItemSerializer,
    SearchQuerySerializer,
    # AJAX endpoints serializers
    SearchSuggestionSerializer,
    ProductAvailabilitySerializer,
    RelatedProductSerializer,
    TrackEventSerializer,
    NewsletterSubscribeSerializer,
    ContactFormSerializer
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для категорий товаров.
    
    Предоставляет:
        - list: GET /api/categories/ - список всех категорий
        - retrieve: GET /api/categories/{id}/ - детали категории
    
    Permissions: Read-only для всех пользователей
    Performance: Использует annotate для products_count чтобы избежать N+1 queries
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """
        Возвращает queryset категорий с оптимизацией.
        Добавляет annotate для подсчета товаров без N+1 проблем.
        """
        return Category.objects.annotate(
            products_count_annotated=Count('products')
        ).order_by('name')


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для товаров.
    
    Предоставляет:
        - list: GET /api/products/ - список товаров
        - retrieve: GET /api/products/{id}/ - детали товара
        - search: GET /api/products/search/?q=query - поиск товаров
        - by_category: GET /api/products/by_category/{slug}/ - товары по категории
    
    Permissions: Read-only для всех пользователей
    Pagination: По умолчанию 20 товаров на страницу
    """
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """
        Возвращает queryset товаров с оптимизацией.
        
        Использует select_related для минимизации запросов к БД.
        """
        return Product.objects.all().select_related('category').order_by('-id')
    
    def get_serializer_class(self):
        """
        Возвращает сериализатор в зависимости от action.
        
        - list: ProductListSerializer (минимальная информация)
        - retrieve: ProductDetailSerializer (полная информация)
        """
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Поиск товаров по запросу.
        
        Query Parameters:
            - q: Поисковый запрос (required)
            - category: ID категории (optional)
            - min_price: Минимальная цена (optional)
            - max_price: Максимальная цена (optional)
            - in_stock: Только в наличии (optional)
        
        Returns:
            - 200: Список найденных товаров
            - 400: Ошибка валидации параметров
        
        Example:
            GET /api/products/search/?q=футболка&category=1&in_stock=true
        """
        # Валидация параметров
        serializer = SearchQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        query = validated_data.get('q', '')
        
        # Базовый queryset
        queryset = self.get_queryset()
        
        # Поиск по названию и описанию
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Фильтр по категории
        if validated_data.get('category'):
            queryset = queryset.filter(category_id=validated_data['category'])
        
        # Фильтр по цене
        if validated_data.get('min_price'):
            queryset = queryset.filter(price__gte=validated_data['min_price'])
        if validated_data.get('max_price'):
            queryset = queryset.filter(price__lte=validated_data['max_price'])
        
        # Фильтр "только в наличии" - пропускаем, т.к. поле отсутствует в модели
        # if validated_data.get('in_stock'):
        #     queryset = queryset.filter(in_stock=True)
        
        # Пагинация
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(
                page, 
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-category/(?P<category_slug>[^/.]+)')
    def by_category(self, request, category_slug=None):
        """
        Получить товары по slug категории.
        
        Args:
            category_slug: URL slug категории
        
        Returns:
            - 200: Список товаров категории
            - 404: Категория не найдена
        
        Example:
            GET /api/products/by-category/odezhda/
        """
        try:
            category = Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = self.get_queryset().filter(category=category)
        
        # Пагинация
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='related')
    def related(self, request, slug=None):
        """
        Получить похожие товары.
        
        Возвращает товары из той же категории (кроме текущего).
        
        Args:
            slug: URL slug товара
        
        Returns:
            - 200: Список похожих товаров (до 6 штук)
            - 404: Товар не найден
        
        Example:
            GET /api/products/futbolka-classic/related/
        """
        product = self.get_object()
        
        # Ищем товары из той же категории
        related_products = Product.objects.filter(
            category=product.category
        ).exclude(
            id=product.id
        ).select_related('category')[:6]
        
        serializer = RelatedProductSerializer(
            related_products,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'success': True,
            'products': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=True, methods=['get'], url_path='availability')
    def availability(self, request, slug=None):
        """
        Проверить доступность товара.
        
        Args:
            slug: URL slug товара
        
        Returns:
            - 200: Информация о доступности
            - 404: Товар не найден
        
        Example:
            GET /api/products/futbolka-classic/availability/
        """
        product = self.get_object()
        
        # TODO: Добавить реальную проверку наличия на складе
        # Пока просто возвращаем True для всех товаров
        
        data = {
            'available': True,
            'in_stock': True,
            'message': 'Товар доступний'
        }
        
        serializer = ProductAvailabilitySerializer(data)
        
        return Response({
            'success': True,
            **serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='suggestions')
    def suggestions(self, request):
        """
        Автодополнение для поиска товаров.
        
        Query Parameters:
            - q: Поисковый запрос (required, min 2 символа)
            - limit: Количество результатов (optional, default 5, max 10)
        
        Returns:
            - 200: Список предложений
        
        Example:
            GET /api/products/suggestions/?q=футб&limit=5
        """
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 5))
        
        # Ограничение лимита
        if limit > 10:
            limit = 10
        
        if not query or len(query) < 2:
            return Response({
                'success': True,
                'suggestions': [],
                'count': 0
            })
        
        # Ищем по началу названия (быстрее чем contains)
        products = Product.objects.filter(
            title__istartswith=query
        ).values('id', 'title', 'slug')[:limit]
        
        serializer = SearchSuggestionSerializer(products, many=True)
        
        return Response({
            'success': True,
            'suggestions': serializer.data,
            'count': len(serializer.data)
        })


class CartViewSet(viewsets.ViewSet):
    """
    ViewSet для операций с корзиной.
    
    Предоставляет:
        - add: POST /api/cart/add/ - добавить товар в корзину
        - remove: POST /api/cart/remove/ - удалить товар
        - clear: POST /api/cart/clear/ - очистить корзину
        - contents: GET /api/cart/ - содержимое корзины
    
    Permissions: Read-only для всех, write для аутентифицированных
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    @action(detail=False, methods=['post'])
    def add(self, request):
        """
        Добавить товар в корзину.
        
        Request Body:
            - product_id: ID товара (required)
            - quantity: Количество (required, >= 1)
            - color: Цвет (optional)
            - size: Размер (optional)
        
        Returns:
            - 200: Товар добавлен успешно
            - 400: Ошибка валидации
            - 404: Товар не найден
        
        Example:
            POST /api/cart/add/
            {
                "product_id": 123,
                "quantity": 2,
                "color": "Black",
                "size": "M"
            }
        """
        serializer = CartItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        product_id = validated_data['product_id']
        quantity = validated_data['quantity']
        color = validated_data.get('color', '')
        size = validated_data.get('size', '')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Товар не найден или недоступен'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Работа с сессией корзины
        cart = request.session.get('cart', {})
        cart_key = str(product_id)
        
        if cart_key in cart:
            cart[cart_key]['quantity'] += quantity
        else:
            cart[cart_key] = {
                'product_id': product_id,
                'quantity': quantity,
                'color': color,
                'size': size,
                'title': product.title,
                'price': float(product.price)
            }
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return Response({
            'success': True,
            'message': f'Товар "{product.title}" додано до кошику',
            'cart_count': sum(item['quantity'] for item in cart.values())
        })
    
    @action(detail=False, methods=['post'])
    def remove(self, request):
        """
        Удалить товар из корзины.
        
        Request Body:
            - product_id: ID товара
        
        Returns:
            - 200: Товар удален
            - 404: Товар не найден в корзине
        """
        product_id = request.data.get('product_id')
        if not product_id:
            return Response(
                {'error': 'product_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart = request.session.get('cart', {})
        cart_key = str(product_id)
        
        if cart_key in cart:
            del cart[cart_key]
            request.session['cart'] = cart
            request.session.modified = True
            
            return Response({
                'success': True,
                'message': 'Товар видалено з кошику',
                'cart_count': sum(item['quantity'] for item in cart.values())
            })
        
        return Response(
            {'error': 'Товар не знайдено у кошику'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """
        Очистить корзину.
        
        Returns:
            - 200: Корзина очищена
        """
        request.session['cart'] = {}
        request.session.modified = True
        
        return Response({
            'success': True,
            'message': 'Кошик очищено',
            'cart_count': 0
        })
    
    def list(self, request):
        """
        Получить содержимое корзины.
        
        Returns:
            - 200: Список товаров в корзине
        """
        cart = request.session.get('cart', {})
        
        return Response({
            'cart': cart,
            'cart_count': sum(item['quantity'] for item in cart.values()),
            'total': sum(
                item['quantity'] * item['price']
                for item in cart.values()
            )
        })


class AnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet для аналитики и трекинга событий.
    
    Предоставляет:
        - track: POST /api/analytics/track/ - трекинг событий
    
    Permissions: Доступно для всех (CSRF exempt для внешних интеграций)
    """
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], url_path='track')
    def track(self, request):
        """
        Трекинг событий для аналитики.
        
        Request Body:
            - event_type: Тип события (view, click, add_to_cart, purchase, etc.)
            - product_id: ID товара (optional)
            - category_id: ID категории (optional)
            - metadata: Дополнительные данные JSON (optional)
        
        Returns:
            - 200: Событие записано
            - 400: Ошибка валидации
        
        Example:
            POST /api/analytics/track/
            {
                "event_type": "add_to_cart",
                "product_id": 123,
                "metadata": {"source": "homepage"}
            }
        """
        serializer = TrackEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        event_type = validated_data['event_type']
        product_id = validated_data.get('product_id')
        category_id = validated_data.get('category_id')
        metadata = validated_data.get('metadata', {})
        
        # TODO: Сохранить событие в БД или отправить в аналитику
        # Например: Google Analytics, Mixpanel, Amplitude, etc.
        
        import logging
        logger = logging.getLogger('storefront.analytics')
        logger.info(
            f"Event tracked: {event_type}, "
            f"Product: {product_id}, "
            f"Category: {category_id}, "
            f"Metadata: {metadata}"
        )
        
        return Response({
            'success': True,
            'message': 'Подію відстежено',
            'event_type': event_type
        })


class CommunicationViewSet(viewsets.ViewSet):
    """
    ViewSet для коммуникации с клиентами.
    
    Предоставляет:
        - newsletter: POST /api/communication/newsletter/ - подписка на рассылку
        - contact: POST /api/communication/contact/ - форма обратной связи
    
    Permissions: Доступно для всех
    """
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], url_path='newsletter')
    def newsletter(self, request):
        """
        Подписка на email рассылку.
        
        Request Body:
            - email: Email адрес подписчика
        
        Returns:
            - 200: Подписка успешна
            - 400: Ошибка валидации
        
        Example:
            POST /api/communication/newsletter/
            {
                "email": "user@example.com"
            }
        """
        serializer = NewsletterSubscribeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        
        # TODO: Сохранить email в БД или отправить в сервис рассылок
        # Например: MailChimp, SendGrid, Mailgun, etc.
        
        import logging
        logger = logging.getLogger('storefront.newsletter')
        logger.info(f"Newsletter subscription: {email}")
        
        return Response({
            'success': True,
            'message': 'Дякуємо за підписку! Ви будете отримувати наші новини.'
        })
    
    @action(detail=False, methods=['post'], url_path='contact')
    def contact(self, request):
        """
        Форма обратной связи.
        
        Request Body:
            - name: Имя отправителя
            - email: Email отправителя
            - phone: Телефон (optional)
            - message: Текст сообщения
        
        Returns:
            - 200: Сообщение отправлено
            - 400: Ошибка валидации
        
        Example:
            POST /api/communication/contact/
            {
                "name": "Іван Петренко",
                "email": "ivan@example.com",
                "phone": "+380501234567",
                "message": "Питання про доставку..."
            }
        """
        serializer = ContactFormSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        name = validated_data['name']
        email = validated_data['email']
        phone = validated_data.get('phone', '')
        message = validated_data['message']
        
        # TODO: Отправить email администратору или сохранить в БД
        # Например: Django send_mail, Celery task, etc.
        
        import logging
        logger = logging.getLogger('storefront.contact')
        logger.info(
            f"Contact form submission: {name} ({email}), "
            f"Phone: {phone}, Message: {message[:50]}..."
        )
        
        return Response({
            'success': True,
            'message': 'Ваше повідомлення надіслано! Ми зв\'яжемося з вами найближчим часом.'
        })


