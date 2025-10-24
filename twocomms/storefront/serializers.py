"""
Django REST Framework Serializers for Storefront API.

Сериализаторы для преобразования моделей в JSON и обратно.
Используются ViewSets для автоматической генерации API endpoints.
"""

from rest_framework import serializers
from .models import Product, Category
from productcolors.models import ProductColorVariant


class CategorySerializer(serializers.ModelSerializer):
    """
    Сериализатор для категорий товаров.
    
    Fields:
        - id: ID категории
        - name: Название категории
        - slug: URL slug
        - is_active: Активна ли категория
        - products_count: Количество товаров (read-only)
    """
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'products_count']
        read_only_fields = ['id', 'slug']
    
    def get_products_count(self, obj):
        """Возвращает количество товаров в категории."""
        return obj.products.count()


class ProductColorSerializer(serializers.ModelSerializer):
    """
    Сериализатор для цветовых вариантов товара.
    
    Fields:
        - id: ID варианта
        - color: Объект цвета
        - is_default: Дефолтный вариант
        - order: Порядок сортировки
    """
    class Meta:
        model = ProductColorVariant
        fields = ['id', 'color', 'is_default', 'order']
        depth = 1  # Включаем вложенный объект color


class ProductListSerializer(serializers.ModelSerializer):
    """
    Сериализатор для списка товаров (минимальная информация).
    
    Оптимизирован для быстрой загрузки списков.
    Fields:
        - id: ID товара
        - title: Название
        - slug: URL slug
        - retail_price: Розничная цена
        - image: Главное изображение (URL)
        - category: Название категории
        - is_active: Активен ли товар
        - in_stock: В наличии
    """
    category = serializers.CharField(source='category.name', read_only=True)
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'price', 'image',
            'category', 'featured'
        ]
        read_only_fields = ['id', 'slug']
    
    def get_image(self, obj):
        """Возвращает URL главного изображения."""
        if obj.main_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.main_image.url)
            return obj.main_image.url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детальной информации о товаре.
    
    Включает полную информацию о товаре и связанных сущностях.
    Fields:
        - id: ID товара
        - title: Название
        - slug: URL slug
        - description: Описание
        - retail_price: Розничная цена
        - wholesale_price: Оптовая цена
        - drop_price: Дропшиппинг цена
        - image: Главное изображение
        - category: Объект категории
        - is_active: Активен
        - in_stock: В наличии
        - colors: Список цветовых вариантов
        - points_reward: Баллы за покупку
    """
    category = CategorySerializer(read_only=True)
    colors = ProductColorSerializer(many=True, read_only=True, source='color_variants')
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'description',
            'price', 'wholesale_price', 'drop_price',
            'image', 'category', 'featured',
            'colors', 'points_reward'
        ]
        read_only_fields = ['id', 'slug']
    
    def get_image(self, obj):
        """Возвращает URL главного изображения."""
        if obj.main_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.main_image.url)
            return obj.main_image.url
        return None


class CartItemSerializer(serializers.Serializer):
    """
    Сериализатор для элемента корзины.
    
    Fields:
        - product_id: ID товара
        - quantity: Количество
        - color: Цвет (optional)
        - size: Размер (optional)
    """
    product_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    color = serializers.CharField(required=False, allow_blank=True)
    size = serializers.CharField(required=False, allow_blank=True)
    
    def validate_product_id(self, value):
        """Проверяет существование товара."""
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Товар не найден")
        return value


class SearchQuerySerializer(serializers.Serializer):
    """
    Сериализатор для параметров поиска.
    
    Fields:
        - q: Поисковый запрос
        - category: ID категории (optional)
        - min_price: Минимальная цена (optional)
        - max_price: Максимальная цена (optional)
        - in_stock: Только в наличии (optional)
    """
    q = serializers.CharField(required=True, max_length=200)
    category = serializers.IntegerField(required=False, allow_null=True)
    min_price = serializers.DecimalField(
        required=False, 
        allow_null=True,
        max_digits=10, 
        decimal_places=2
    )
    max_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=2
    )
    in_stock = serializers.BooleanField(required=False, default=False)


