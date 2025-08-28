from django import forms
from .models import Product, ProductImage, Category

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

class ProductForm(forms.ModelForm):
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
        }

    def clean(self):
        data = super().clean()
        # Обов'язково вимагати головне зображення під час створення товару
        if not self.instance.pk and not data.get("main_image"):
            self.add_error("main_image", "Головне зображення є обов'язковим")
        
        # Обработка points_reward
        points_reward = data.get('points_reward')
        if points_reward is not None:
            try:
                data['points_reward'] = int(points_reward) if points_reward else 0
            except (ValueError, TypeError):
                data['points_reward'] = 0
        
        # Обработка discount_percent
        discount_percent = data.get('discount_percent')
        if discount_percent is not None:
            try:
                data['discount_percent'] = int(discount_percent) if discount_percent else None
            except (ValueError, TypeError):
                data['discount_percent'] = None
        
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "icon", "cover", "order"]
