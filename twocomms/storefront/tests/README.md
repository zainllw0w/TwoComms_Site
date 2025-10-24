# 🧪 Storefront Views Unit Tests

Комплексное тестовое покрытие для модульной структуры `storefront/views/`.

## 📊 Статистика

- **Всего тестовых файлов:** 5
- **Покрытие модулей:** 100+ unit tests
- **Покрытые модули:** auth.py, cart.py, checkout.py, product.py, catalog.py

## 📁 Структура

```
tests/
├── __init__.py                    # Test package initialization
├── test_auth.py                   # Authentication tests (18+ tests)
├── test_cart.py                   # Shopping cart tests (30+ tests)
├── test_checkout.py               # Checkout tests (20+ tests)
├── test_product.py                # Product views tests (15+ tests)
├── test_catalog.py                # Catalog tests (20+ tests)
└── README.md                      # This file
```

## 🚀 Запуск тестов

### Все тесты

```bash
cd /path/to/TwoComms/twocomms
python manage.py test storefront.tests
```

### Конкретный тестовый файл

```bash
# Тесты аутентификации
python manage.py test storefront.tests.test_auth

# Тесты корзины
python manage.py test storefront.tests.test_cart

# Тесты оформления заказа
python manage.py test storefront.tests.test_checkout

# Тесты товаров
python manage.py test storefront.tests.test_product

# Тесты каталога
python manage.py test storefront.tests.test_catalog
```

### Конкретный тестовый класс

```bash
python manage.py test storefront.tests.test_auth.LoginViewTests
```

### Конкретный тест

```bash
python manage.py test storefront.tests.test_auth.LoginViewTests.test_login_with_valid_credentials
```

### С verbose output

```bash
python manage.py test storefront.tests -v 2
```

### С coverage отчетом

```bash
# Установить coverage
pip install coverage

# Запустить тесты с coverage
coverage run --source='storefront' manage.py test storefront.tests
coverage report
coverage html  # Создает HTML отчет в htmlcov/
```

## 📝 Описание тестовых модулей

### 1. test_auth.py - Authentication Tests

**Покрывает:** `views/auth.py`

**Классы:**
- `LoginViewTests` - Тесты страницы входа
  * Загрузка страницы
  * Валидные/невалидные credentials
  * Редирект авторизованных пользователей
  * Next parameter

- `RegisterViewTests` - Тесты регистрации
  * Создание нового пользователя
  * Duplicate username
  * Password mismatch
  * Weak password validation

- `LogoutViewTests` - Тесты выхода
  * Logout авторизованного пользователя
  * Очистка сессии
  * Logout неавторизованного

**Примеры:**
```python
def test_login_with_valid_credentials(self):
    """Test login with correct username and password."""
    response = self.client.post(self.login_url, {
        'username': 'testuser',
        'password': 'testpass123'
    })
    self.assertEqual(response.status_code, 302)
```

### 2. test_cart.py - Shopping Cart Tests

**Покрывает:** `views/cart.py`

**Классы:**
- `ViewCartTests` - Просмотр корзины
- `AddToCartTests` - Добавление товара
- `UpdateCartTests` - Обновление количества
- `RemoveFromCartTests` - Удаление товара
- `ClearCartTests` - Очистка корзины
- `PromoCodeTests` - Промокоды
- `GetCartCountTests` - Подсчет товаров

**Примеры:**
```python
def test_add_product_to_cart(self):
    """Test adding a product to cart."""
    response = self.client.post(self.add_to_cart_url, {
        'product_id': self.product.id,
        'quantity': 1,
        'color': 'Black',
        'size': 'M'
    })
    self.assertEqual(response.status_code, 200)
    data = json.loads(response.content)
    self.assertTrue(data.get('success'))
```

### 3. test_checkout.py - Checkout Tests

**Покрывает:** `views/checkout.py`

**Классы:**
- `CheckoutViewTests` - Страница оформления заказа
- `CreateOrderTests` - Создание заказа
- `ConfirmPaymentTests` - Подтверждение оплаты
- `OrderSuccessTests` - Страница успешного заказа

**Примеры:**
```python
def test_create_order_as_guest(self):
    """Test order creation as guest user."""
    response = self.client.post(self.create_order_url, {
        'full_name': 'Test Guest',
        'phone': '+380991234567',
        'city': 'Київ',
        'np_office': 'Відділення №1',
        'payment_method': 'cash'
    })
    self.assertEqual(response.status_code, 302)
    self.assertTrue(Order.objects.filter(phone='+380991234567').exists())
```

### 4. test_product.py - Product Views Tests

**Покрывает:** `views/product.py`

**Классы:**
- `ProductDetailTests` - Детальная страница товара
- `GetProductImagesTests` - AJAX получение изображений
- `GetProductVariantsTests` - AJAX получение вариантов
- `QuickViewTests` - Быстрый просмотр (модальное окно)

**Примеры:**
```python
def test_product_detail_page_loads(self):
    """Test that product detail page loads successfully."""
    response = self.client.get(self.product_url)
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, self.product.title)
```

### 5. test_catalog.py - Catalog Tests

**Покрывает:** `views/catalog.py`

**Классы:**
- `HomeViewTests` - Главная страница
- `CatalogViewTests` - Каталог категорий
- `SearchViewTests` - Поиск товаров
- `LoadMoreProductsTests` - AJAX подгрузка

**Примеры:**
```python
def test_search_with_query(self):
    """Test search with query parameter."""
    response = self.client.get(self.search_url, {'q': 'red'})
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'Red T-Shirt')
```

## ✅ Покрываемые сценарии

### Authentication (auth.py)
- ✅ Login с валидными/невалидными credentials
- ✅ Регистрация нового пользователя
- ✅ Validation паролей и username
- ✅ Logout и очистка сессии
- ✅ Редиректы авторизованных пользователей

### Cart (cart.py)
- ✅ Добавление товара в корзину
- ✅ Обновление количества
- ✅ Удаление товара
- ✅ Очистка корзины
- ✅ Применение/удаление промокодов
- ✅ Подсчет товаров в корзине
- ✅ Валидация stock availability

### Checkout (checkout.py)
- ✅ Оформление заказа (guest и auth)
- ✅ Валидация данных заказа
- ✅ Применение промокодов к заказу
- ✅ Выбор способа оплаты
- ✅ Подтверждение оплаты
- ✅ Success страница заказа

### Product (product.py)
- ✅ Просмотр детальной страницы товара
- ✅ Отображение цен и описаний
- ✅ Варианты товара (цвета, размеры)
- ✅ AJAX получение изображений
- ✅ Быстрый просмотр товара
- ✅ 404 для неактивных товаров

### Catalog (catalog.py)
- ✅ Главная страница с товарами
- ✅ Каталог по категориям
- ✅ Поиск товаров
- ✅ Фильтрация и сортировка
- ✅ AJAX пагинация
- ✅ Только активные товары

## 🎯 Best Practices

### 1. Используйте setUp/tearDown
```python
def setUp(self):
    """Set up test client and test data."""
    self.client = Client()
    # Create test data
```

### 2. Именование тестов
Используйте описательные имена: `test_<action>_<scenario>`

```python
def test_login_with_valid_credentials(self):
def test_add_product_to_empty_cart(self):
def test_search_with_empty_query(self):
```

### 3. Один тест = Один сценарий
Каждый тест должен проверять один конкретный сценарий.

### 4. AAA Pattern (Arrange-Act-Assert)
```python
def test_example(self):
    # Arrange: Set up test data
    product = Product.objects.create(...)
    
    # Act: Perform action
    response = self.client.post(url, data)
    
    # Assert: Verify result
    self.assertEqual(response.status_code, 200)
```

### 5. Используйте docstrings
```python
def test_login_with_valid_credentials(self):
    """Test login with correct username and password."""
    # Test implementation
```

## 🔧 Рекомендации

### Continuous Integration
Добавьте тесты в CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          python manage.py test storefront.tests
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
python manage.py test storefront.tests --failfast
```

### Coverage Target
Стремитесь к 80%+ coverage для критичных модулей.

## 📈 Расширение тестов

### Добавление новых тестов

1. Создайте новый файл `test_<module>.py`
2. Импортируйте необходимые классы
3. Создайте TestCase класс
4. Напишите тесты с `test_` префиксом

```python
from django.test import TestCase

class MyNewTests(TestCase):
    def setUp(self):
        # Setup
        pass
    
    def test_something(self):
        """Test description."""
        # Test implementation
        pass
```

### Тестирование AJAX endpoints

```python
def test_ajax_endpoint(self):
    """Test AJAX endpoint returns JSON."""
    response = self.client.get(url)
    self.assertEqual(response['Content-Type'], 'application/json')
    
    data = json.loads(response.content)
    self.assertTrue(data.get('success'))
```

### Тестирование с authenticated user

```python
def setUp(self):
    self.user = User.objects.create_user(...)
    self.client.login(username='...', password='...')

def test_protected_endpoint(self):
    response = self.client.get(protected_url)
    self.assertEqual(response.status_code, 200)
```

## 🐛 Troubleshooting

### Проблема: Tests падают с database errors
**Решение:** Django автоматически создает test database. Убедитесь, что у пользователя БД есть права на создание databases.

### Проблема: Fixtures не загружаются
**Решение:** Используйте `setUp()` метод вместо fixtures для создания test data.

### Проблема: Тесты проходят локально, но падают на CI
**Решение:** Проверьте environment variables и dependencies в CI конфигурации.

## 📚 Дополнительные ресурсы

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Django TestCase API](https://docs.djangoproject.com/en/stable/topics/testing/tools/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

## ✨ Вклад

При добавлении новых views, обязательно:
1. Добавьте соответствующие unit tests
2. Покройте positive и negative сценарии
3. Проверьте coverage `coverage report`
4. Обновите этот README при необходимости

---

**Created:** As part of architectural refactoring  
**Last Updated:** October 2025  
**Maintainer:** Development Team


