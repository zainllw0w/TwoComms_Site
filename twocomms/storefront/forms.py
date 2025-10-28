from django import forms
from django.forms import inlineformset_factory

from productcolors.models import ProductColorVariant, ProductColorImage
from storefront.services.catalog import ensure_color_identity

from .models import (
    Product,
    ProductImage,
    Category,
    PrintProposal,
    Catalog,
    CatalogOption,
    CatalogOptionValue,
    SizeGrid,
)

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
            "title",
            "slug",
            "category",
            "catalog",
            "size_grid",
            "price",
            "discount_percent",
            "featured",
            "short_description",
            "full_description",
            "main_image",
            "main_image_alt",
            "points_reward",
            "status",
            "priority",
        ]
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "full_description": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.NumberInput(attrs={"class": "form-control", "min": "0", "value": "0"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "catalog": forms.Select(attrs={"class": "form-control"}),
            "size_grid": forms.Select(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "discount_percent": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "100"}),
            "featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "main_image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "main_image_alt": forms.TextInput(attrs={"class": "form-control"}),
            "points_reward": forms.NumberInput(attrs={"class": "form-control", "min": "0", "value": "0"}),
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

        # Длина короткого описания
        short_description = data.get('short_description') or ''
        if short_description and len(short_description) > 300:
            self.add_error('short_description', "Короткий опис не може містити більше 300 символів")

        # Пріоритет показу
        priority = data.get('priority')
        if priority is not None:
            try:
                priority_int = int(priority)
                if priority_int < 0:
                    self.add_error('priority', "Пріоритет не може бути від'ємним")
                data['priority'] = priority_int
            except (ValueError, TypeError):
                self.add_error('priority', "Невірне значення пріоритету")

        # Синхронизация описаний
        full_description = data.get('full_description') or ''
        if not short_description and full_description:
            data['short_description'] = full_description[:297].rstrip() + '...' if len(full_description) > 300 else full_description
        
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Поддерживаем legacy-поле description для обратной совместимости
        full_description = self.cleaned_data.get('full_description') or ''
        if full_description:
            instance.description = full_description
        elif self.cleaned_data.get('short_description'):
            instance.description = self.cleaned_data['short_description']
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductSEOForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["seo_title", "seo_description", "seo_keywords", "seo_schema"]
        widgets = {
            "seo_title": forms.TextInput(attrs={"maxlength": 160}),
            "seo_description": forms.Textarea(attrs={"rows": 3, "maxlength": 320}),
            "seo_keywords": forms.TextInput(attrs={"placeholder": "ключові слова через кому"}),
            "seo_schema": forms.Textarea(attrs={"rows": 6, "placeholder": '{"@context": "..."}'}),
        }

    def clean_seo_title(self):
        value = (self.cleaned_data.get("seo_title") or "").strip()
        if len(value) > 160:
            raise forms.ValidationError("SEO title не може бути довшим за 160 символів")
        return value

    def clean_seo_description(self):
        value = (self.cleaned_data.get("seo_description") or "").strip()
        if len(value) > 320:
            raise forms.ValidationError("SEO description не може бути довшим за 320 символів")
        return value


class SizeGridForm(forms.ModelForm):
    class Meta:
        model = SizeGrid
        fields = ["name", "image", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class CatalogOptionForm(forms.ModelForm):
    class Meta:
        model = CatalogOption
        fields = [
            "name",
            "option_type",
            "is_required",
            "is_additional_cost",
            "additional_cost",
            "help_text",
            "order",
        ]


CatalogOptionFormSet = inlineformset_factory(
    Catalog,
    CatalogOption,
    form=CatalogOptionForm,
    extra=0,
    can_delete=True,
)


class CatalogOptionValueForm(forms.ModelForm):
    class Meta:
        model = CatalogOptionValue
        fields = ["value", "display_name", "image", "order", "is_default", "metadata"]


CatalogOptionValueFormSet = inlineformset_factory(
    CatalogOption,
    CatalogOptionValue,
    form=CatalogOptionValueForm,
    extra=0,
    can_delete=True,
)


class ProductColorVariantForm(forms.ModelForm):
    name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Назва кольору"}),
    )
    primary_hex = forms.CharField(
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs={"placeholder": "#RRGGBB"}),
        help_text="Основний HEX"
    )
    secondary_hex = forms.CharField(
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs={"placeholder": "#RRGGBB"}),
        help_text="Другий HEX (опціонально)"
    )

    class Meta:
        model = ProductColorVariant
        fields = [
            "color",
            "is_default",
            "order",
            "sku",
            "barcode",
            "stock",
            "price_override",
            "metadata",
        ]
        widgets = {
            "order": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].widget = forms.HiddenInput()
        self.fields["color"].required = False
        if self.instance and self.instance.pk:
            color = getattr(self.instance, "color", None)
            if color:
                self.fields["name"].initial = color.name
                self.fields["primary_hex"].initial = color.primary_hex
                self.fields["secondary_hex"].initial = color.secondary_hex or ""

    def clean_primary_hex(self):
        value = (self.cleaned_data.get("primary_hex") or "").strip()
        if not value:
            return ""
        if not value.startswith("#"):
            value = f"#{value}"
        if len(value) != 7:
            raise forms.ValidationError("HEX має містити 7 символів разом з #")
        return value.upper()

    def clean_secondary_hex(self):
        value = (self.cleaned_data.get("secondary_hex") or "").strip()
        if not value:
            return ""
        if not value.startswith("#"):
            value = f"#{value}"
        if len(value) != 7:
            raise forms.ValidationError("HEX має містити 7 символів разом з #")
        return value.upper()

    def clean(self):
        data = super().clean()
        color = data.get("color")
        primary_hex = data.get("primary_hex")
        if not color and not primary_hex:
            raise forms.ValidationError("Вкажіть існуючий колір або HEX значення.")
        return data

    def save(self, commit=True):
        variant = super().save(commit=False)
        color = self.cleaned_data.get("color")
        primary_hex = (self.cleaned_data.get("primary_hex") or "").strip()
        secondary_hex = (self.cleaned_data.get("secondary_hex") or "").strip() or None
        name = (self.cleaned_data.get("name") or "").strip()

        result = ensure_color_identity(
            primary_hex=primary_hex or (color.primary_hex if color else None),
            secondary_hex=secondary_hex,
            name=name,
            color=color,
        )

        variant.color = result.color
        if commit:
            variant.save()
            self.save_m2m()
        return variant


class ProductColorImageForm(forms.ModelForm):
    class Meta:
        model = ProductColorImage
        fields = ["image", "alt_text", "order"]


ProductColorImageFormSet = inlineformset_factory(
    ProductColorVariant,
    ProductColorImage,
    form=ProductColorImageForm,
    extra=0,
    can_delete=True,
)


ProductColorVariantFormSet = inlineformset_factory(
    Product,
    ProductColorVariant,
    form=ProductColorVariantForm,
    extra=1,
    can_delete=True,
)


def build_color_variant_formset(
    product=None,
    data=None,
    files=None,
    prefix='color_variants'
):
    """
    Строит formset вариантов цвета и подготавливает вложенные formset изображений.
    """
    product_instance = product or Product()
    formset = ProductColorVariantFormSet(
        data=data if data is not None else None,
        files=files if files is not None else None,
        instance=product_instance,
        prefix=prefix,
    )

    for form in formset.forms:
        variant_instance = form.instance
        if not variant_instance.pk:
            variant_instance.product = product_instance
        form.images_formset = ProductColorImageFormSet(
            data=data if data is not None else None,
            files=files if files is not None else None,
            instance=variant_instance,
            prefix=f"{form.prefix}-images",
        )
    empty_variant = formset.empty_form
    empty_variant.instance.product = product_instance
    empty_variant.images_formset = ProductColorImageFormSet(
        data=data if data is not None else None,
        files=files if files is not None else None,
        instance=empty_variant.instance,
        prefix=f"{empty_variant.prefix}-images",
    )
    return formset


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
