"""
Django REST Framework ViewSets for Storefront API.

ViewSets обеспечивают CRUD операции и кастомные endpoints для API.
Используют сериализаторы для преобразования данных в JSON.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django.db.models import Q

from .models import Product, Category
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    CategorySerializer,
    CartItemSerializer,
    SearchQuerySerializer
)


class TestProductViewSet(viewsets.ViewSet):
    """
    ВРЕМЕННЫЙ тестовый ViewSet для debug 500 ошибки.
    Минимальная реализация без пагинации и сериализаторов.
    """
    permission_classes = [AllowAny]
    
    def list(self, request):
        """Простой список товаров без всяких наворотов."""
        products = list(Product.objects.all().values('id', 'title', 'slug', 'price')[:20])
        return Response({
            'count': len(products),
            'results': products
        })


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для категорий товаров.
    
    Предоставляет:
        - list: GET /api/categories/ - список всех категорий
        - retrieve: GET /api/categories/{id}/ - детали категории
    
    Permissions: Read-only для всех пользователей
    """
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'


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


