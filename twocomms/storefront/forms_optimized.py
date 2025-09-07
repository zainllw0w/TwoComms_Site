"""
Оптимизированные формы для storefront приложения
"""

from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from .models import Product, ProductImage, Category, PrintProposal

# ✅ Виджет с поддержкой множественной загрузки
class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

# ✅ Поле, умеющее принимать список файлов (или пусто) без ошибки "No file was submitted"
class MultiFileField(forms.FileField):
    def clean(self, data, initial=None):
        # Пустое значение — это ок для required=False
        if not data:
            return None
        # Если пришёл список/кортеж — валидируем каждый файл как обычный FileField
        if isinstance(data, (list, tuple)):
            cleaned = []
            errors = []
            for f in data:
                try:
                    cleaned.append(super().clean(f, initial))
                except forms.ValidationError as e:
                    errors.extend(e.error_list)
            if errors:
                raise forms.ValidationError(errors)
            return cleaned
        # Одиночный файл (на случай, если браузер не поддерживает multiple)
        return super().clean(data, initial)

class OptimizedProductForm(forms.ModelForm):
    """Оптимизированная форма товара с кэшированием и валидацией"""
    
    # множественный аплоад: безопасно обрабатываем список файлов
    extra_images = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={
            "multiple": True,
            "accept": "image/*",
            "class": "form-control"
        })
    )

    class Meta:
        model = Product
        fields = [
            "title", "slug", "category", "price",
            "discount_percent", "featured",
            "description", "main_image", "points_reward",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_percent": forms.NumberInput(attrs={"class": "form-control"}),
            "points_reward": forms.NumberInput(attrs={"class": "form-control"}),
            "main_image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Кэшируем категории для оптимизации
        self.fields['category'].queryset = self.get_cached_categories()

    def get_cached_categories(self):
        """Получить кэшированные категории"""
        cache_key = 'form_categories'
        categories = cache.get(cache_key)
        
        if categories is None:
            categories = Category.objects.filter(is_active=True).order_by('order', 'name')
            cache.set(cache_key, categories, 1800)  # Кэшируем на 30 минут
        
        return categories

    def clean_slug(self):
        """Оптимизированная проверка уникальности slug"""
        slug = self.cleaned_data.get('slug')
        if not slug:
            return slug
        
        # Кэшируем проверку уникальности
        cache_key = f'slug_check_{slug}_{self.instance.pk or 0}'
        is_unique = cache.get(cache_key)
        
        if is_unique is None:
            try:
                existing = Product.objects.filter(slug=slug)
                if self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                is_unique = not existing.exists()
                cache.set(cache_key, is_unique, 300)  # Кэшируем на 5 минут
            except Exception:
                is_unique = True  # В случае ошибки пропускаем проверку
        
        if not is_unique:
            raise forms.ValidationError('Товар з таким slug вже існує.')
        
        return slug

    def clean_price(self):
        """Валидация цены с кэшированием"""
        price = self.cleaned_data.get('price')
        if price is None:
            return price
        
        try:
            price = float(price)
            if price < 0:
                raise forms.ValidationError("Ціна не може бути від'ємною")
            elif price > 999999.99:
                raise forms.ValidationError("Ціна не може перевищувати 999,999.99 грн")
        except (ValueError, TypeError):
            raise forms.ValidationError("Невірний формат ціни")
        
        return price

    def clean_points_reward(self):
        """Валидация баллов"""
        points_reward = self.cleaned_data.get('points_reward')
        if points_reward is None:
            return 0
        
        try:
            points_reward = int(points_reward) if points_reward else 0
            if points_reward < 0:
                raise forms.ValidationError("Кількість балів не може бути від'ємною")
            elif points_reward > 10000:
                raise forms.ValidationError("Кількість балів не може перевищувати 10,000")
        except (ValueError, TypeError):
            points_reward = 0
        
        return points_reward

    def clean_discount_percent(self):
        """Валидация скидки"""
        discount_percent = self.cleaned_data.get('discount_percent')
        if discount_percent is None:
            return None
        
        try:
            discount_percent = int(discount_percent) if discount_percent else None
            if discount_percent is not None:
                if discount_percent < 0:
                    raise forms.ValidationError("Знижка не може бути від'ємною")
                elif discount_percent > 100:
                    raise forms.ValidationError("Знижка не може перевищувати 100%")
        except (ValueError, TypeError):
            discount_percent = None
        
        return discount_percent

    def clean(self):
        data = super().clean()
        
        # Обов'язково вимагати головне зображення під час створення товару
        if not self.instance.pk and not data.get("main_image"):
            self.add_error("main_image", "Головне зображення є обов'язковим")
        
        return data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        # Инвалидируем кэш при сохранении
        if commit:
            self.invalidate_cache()
        
        return instance

    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'form_categories',
            'home_data',
            'products_count',
        ]
        cache.delete_many(cache_keys)

class OptimizedCategoryForm(forms.ModelForm):
    """Оптимизированная форма категории"""
    
    class Meta:
        model = Category
        fields = ["name", "slug", "icon", "cover", "order", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "icon": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "cover": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }
    
    def clean_slug(self):
        """Оптимизированная проверка уникальности slug"""
        slug = self.cleaned_data.get('slug')
        if not slug:
            return slug
        
        # Кэшируем проверку уникальности
        cache_key = f'category_slug_check_{slug}_{self.instance.pk or 0}'
        is_unique = cache.get(cache_key)
        
        if is_unique is None:
            try:
                existing = Category.objects.filter(slug=slug)
                if self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                is_unique = not existing.exists()
                cache.set(cache_key, is_unique, 300)  # Кэшируем на 5 минут
            except Exception:
                is_unique = True  # В случае ошибки пропускаем проверку
        
        if not is_unique:
            raise forms.ValidationError('Категорія з таким slug вже існує.')
        
        return slug
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # По умолчанию категория всегда активна и без рекомендации
        instance.is_active = True
        instance.is_featured = False
        
        if commit:
            instance.save()
            self.invalidate_cache()
        
        return instance

    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'form_categories',
            'categories_list',
            'home_data',
        ]
        cache.delete_many(cache_keys)

class OptimizedPrintProposalForm(forms.ModelForm):
    """Оптимизированная форма предложения принта"""
    
    class Meta:
        model = PrintProposal
        fields = ["image", "link_url", "description"]
        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 4, 
                "placeholder": "Опис і примітки до принта",
                "class": "form-control"
            }),
            "link_url": forms.URLInput(attrs={
                "class": "form-control",
                "placeholder": "https://example.com"
            }),
            "image": forms.FileInput(attrs={
                "class": "form-control", 
                "accept": "image/*"
            }),
        }

    def clean_link_url(self):
        """Валидация URL"""
        link_url = self.cleaned_data.get('link_url', '').strip()
        
        if link_url:
            # Простая валидация URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                raise forms.ValidationError("URL повинен починатися з http:// або https://")
        
        return link_url

    def clean(self):
        data = super().clean()
        image = data.get("image")
        link_url = data.get("link_url", "").strip()

        # Требуем хотя бы один источник: файл или ссылка
        if not image and not link_url:
            raise forms.ValidationError("Додайте зображення або вкажіть посилання")

        return data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        # Инвалидируем кэш при сохранении
        if commit:
            self.invalidate_cache()
        
        return instance

    def invalidate_cache(self):
        """Инвалидация кэша"""
        cache_keys = [
            'print_proposals_pending',
            'admin_orders_data',
        ]
        cache.delete_many(cache_keys)

# Алиасы для обратной совместимости
ProductForm = OptimizedProductForm
CategoryForm = OptimizedCategoryForm
PrintProposalForm = OptimizedPrintProposalForm
