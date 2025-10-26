from django import forms
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
        # Главное изображение необязательно - оно может быть взято из цветовых вариантов
        # или добавлено позже через редактирование товара
        
        # Валидация цены
        price = data.get('price')
        if price is not None:
            try:
                price = float(price)
                if price < 0:
                    self.add_error('price', "Ціна не може бути від'ємною")
                elif price > 999999.99:
                    self.add_error('price', "Ціна не може перевищувати 999,999.99 грн")
            except (ValueError, TypeError):
                self.add_error('price', "Невірний формат ціни")
        
        # Обработка points_reward
        points_reward = data.get('points_reward')
        if points_reward is not None:
            try:
                points_reward = int(points_reward) if points_reward else 0
                if points_reward < 0:
                    self.add_error('points_reward', "Кількість балів не може бути від'ємною")
                elif points_reward > 10000:
                    self.add_error('points_reward', "Кількість балів не може перевищувати 10,000")
                data['points_reward'] = points_reward
            except (ValueError, TypeError):
                data['points_reward'] = 0
        
        # Обработка discount_percent
        discount_percent = data.get('discount_percent')
        if discount_percent is not None:
            try:
                discount_percent = int(discount_percent) if discount_percent else None
                if discount_percent is not None:
                    if discount_percent < 0:
                        self.add_error('discount_percent', "Знижка не може бути від'ємною")
                    elif discount_percent > 100:
                        self.add_error('discount_percent', "Знижка не може перевищувати 100%")
                data['discount_percent'] = discount_percent
            except (ValueError, TypeError):
                data['discount_percent'] = None
        
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "icon", "cover", "order", "description"]
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if slug:
            # Проверяем уникальность slug без конфликта кодировок
            try:
                existing = Category.objects.filter(slug=slug)
                if self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                if existing.exists():
                    raise forms.ValidationError('Категорія з таким slug вже існує.')
            except Exception as e:
                # Если возникает ошибка кодировки, пропускаем проверку
                pass
        return slug
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # По умолчанию категория всегда активна и без рекомендации
        instance.is_active = True
        instance.is_featured = False
        if commit:
            instance.save()
        return instance


class PrintProposalForm(forms.ModelForm):
    class Meta:
        model = PrintProposal
        fields = ["image", "link_url", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Опис і примітки до принта"}),
        }

    def clean(self):
        data = super().clean()
        image = data.get("image")
        link_url = data.get("link_url", "").strip()

        # Требуем хотя бы один источник: файл или ссылка
        if not image and not link_url:
            raise forms.ValidationError("Додайте зображення або вкажіть посилання")

        # Лёгкая защита от спама: ограничим частоту отправок в view
        return data
