import re
import json

from django import forms
from django.forms import inlineformset_factory

from dtf.utils import (
    ALLOWED_HELP_EXTS,
    build_safe_upload_name,
    get_limits,
    normalize_phone,
    validate_uploaded_file,
)
from productcolors.models import ProductColorVariant, ProductColorImage
from storefront.services.catalog import ensure_color_identity
from storefront.custom_print_config import build_placement_specs, normalize_custom_print_snapshot

from .models import (
    CustomPrintBusinessKind,
    Product,
    Category,
    CustomPrintClientKind,
    CustomPrintContactChannel,
    CustomPrintLead,
    CustomPrintLeadAttachment,
    CustomPrintProductType,
    CustomPrintServiceKind,
    CustomPrintSizeMode,
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
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        # Пустое значение — это ок для required=False
        if not data:
            if self.required:
                return single_file_clean(data, initial)
            return []
        # Если пришёл список/кортеж — валидируем каждый файл как обычный FileField
        if isinstance(data, (list, tuple)):
            cleaned = []
            errors = []
            for f in data:
                try:
                    cleaned.append(single_file_clean(f, initial))
                except forms.ValidationError as e:
                    errors.extend(e.error_list)
            if errors:
                raise forms.ValidationError(errors)
            return cleaned
        # Одиночный файл (на случай, если браузер не поддерживает multiple)
        return [single_file_clean(data, initial)]


class CustomPrintLeadForm(forms.Form):
    PLACEMENT_CHOICES = (
        ("front", "Спереду"),
        ("back", "На спині"),
        ("sleeve", "На рукаві"),
        ("custom", "Інший варіант"),
    )

    service_kind = forms.ChoiceField(choices=CustomPrintServiceKind.choices)
    product_type = forms.ChoiceField(choices=CustomPrintProductType.choices)
    placements = forms.MultipleChoiceField(choices=PLACEMENT_CHOICES)
    placement_note = forms.CharField(required=False, max_length=255)
    files = MultiFileField(required=False, widget=MultiFileInput(attrs={"multiple": True}))
    quantity = forms.IntegerField(min_value=1)
    size_mode = forms.ChoiceField(choices=CustomPrintSizeMode.choices, required=False)
    sizes_note = forms.CharField(required=False, max_length=255)
    client_kind = forms.ChoiceField(choices=CustomPrintClientKind.choices, required=False)
    business_kind = forms.ChoiceField(choices=CustomPrintBusinessKind.choices, required=False)
    brand_name = forms.CharField(required=False, max_length=255)
    garment_note = forms.CharField(required=False, max_length=255)
    fit = forms.CharField(required=False, max_length=32)
    fabric = forms.CharField(required=False, max_length=32)
    color_choice = forms.CharField(required=False, max_length=64)
    file_triage_status = forms.CharField(required=False, max_length=32)
    exit_step = forms.CharField(required=False, max_length=32)
    placement_specs_json = forms.CharField(required=False)
    pricing_snapshot_json = forms.CharField(required=False)
    config_draft_json = forms.CharField(required=False)
    name = forms.CharField(max_length=200)
    contact_channel = forms.ChoiceField(choices=CustomPrintContactChannel.choices)
    contact_value = forms.CharField(max_length=255)
    brief = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, require_artwork_files=None, **kwargs):
        self.require_artwork_files = require_artwork_files
        super().__init__(*args, **kwargs)

    @staticmethod
    def _spec_requires_artwork_file(spec):
        if not isinstance(spec, dict):
            return False
        requires_artwork_file = spec.get("requires_artwork_file")
        if requires_artwork_file is None:
            return spec.get("mode") != "full_text"
        return bool(requires_artwork_file)

    @staticmethod
    def _parse_json_field(raw_value, default, field_name):
        if raw_value in (None, ""):
            return default
        if isinstance(raw_value, (list, dict)):
            return raw_value
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError):
            raise forms.ValidationError("Некоректні дані форми.") from None
        if default == [] and not isinstance(parsed, list):
            raise forms.ValidationError("Некоректні дані форми.")
        if default == {} and not isinstance(parsed, dict):
            raise forms.ValidationError("Некоректні дані форми.")
        return parsed

    def clean_contact_value(self):
        value = (self.cleaned_data.get("contact_value") or "").strip()
        channel = (self.cleaned_data.get("contact_channel") or "").strip()

        if channel == CustomPrintContactChannel.PHONE:
            if len(normalize_phone(value)) < 10:
                raise forms.ValidationError("Введіть коректний номер телефону.")
            return value

        if channel == CustomPrintContactChannel.WHATSAPP:
            if len(normalize_phone(value)) < 10:
                raise forms.ValidationError("Введіть коректний номер для WhatsApp.")
            return value

        if channel == CustomPrintContactChannel.TELEGRAM:
            if value.startswith("https://t.me/"):
                return value
            if value.startswith("@") and len(value) > 1:
                return value
            if re.fullmatch(r"[A-Za-z0-9_]{3,}", value):
                return value
            raise forms.ValidationError("Вкажіть Telegram у форматі @username або посилання.")

        return value

    def clean(self):
        cleaned = super().clean()
        service_kind = cleaned.get("service_kind")
        placements = cleaned.get("placements") or []
        placement_note = (cleaned.get("placement_note") or "").strip()
        brief = (cleaned.get("brief") or "").strip()
        client_kind = cleaned.get("client_kind") or CustomPrintClientKind.PERSONAL
        business_kind = (cleaned.get("business_kind") or "").strip()
        garment_note = (cleaned.get("garment_note") or "").strip()
        files = cleaned.get("files")
        if not files:
            files = []
        elif not isinstance(files, (list, tuple)):
            files = [files]

        try:
            placement_specs = self._parse_json_field(
                cleaned.get("placement_specs_json"),
                [],
                "placement_specs_json",
            )
        except forms.ValidationError as exc:
            self.add_error("placement_specs_json", exc)
            placement_specs = []

        try:
            pricing_snapshot = self._parse_json_field(
                cleaned.get("pricing_snapshot_json"),
                {},
                "pricing_snapshot_json",
            )
        except forms.ValidationError as exc:
            self.add_error("pricing_snapshot_json", exc)
            pricing_snapshot = {}

        try:
            config_draft = self._parse_json_field(
                cleaned.get("config_draft_json"),
                {},
                "config_draft_json",
            )
        except forms.ValidationError as exc:
            self.add_error("config_draft_json", exc)
            config_draft = {}
        normalized_snapshot = normalize_custom_print_snapshot(config_draft) if config_draft else {}
        submission_type = (
            (config_draft.get("submission_type") if isinstance(config_draft, dict) else "")
            or ""
        ).strip()

        if not placement_specs and normalized_snapshot:
            placement_specs = build_placement_specs(normalized_snapshot)
        if not placement_specs and placements:
            placement_specs = [
                {
                    "zone": zone,
                    "label": dict(self.PLACEMENT_CHOICES).get(zone, zone),
                    "placement_key": zone,
                    "requires_artwork_file": True,
                    "file_index": index,
                }
                for index, zone in enumerate(placements)
            ]

        required_artwork_specs = [spec for spec in placement_specs if self._spec_requires_artwork_file(spec)]
        required_artwork_file_count = len(required_artwork_specs)
        require_artwork_files = self.require_artwork_files
        if require_artwork_files is None:
            require_artwork_files = submission_type != "lead"

        if "custom" in placements and not placement_note:
            self.add_error("placement_note", "Опишіть нестандартне розміщення принта.")

        if client_kind == CustomPrintClientKind.BRAND and not (cleaned.get("brand_name") or "").strip():
            self.add_error("brand_name", "Вкажіть назву бренду, команди або події.")
        if client_kind == CustomPrintClientKind.BRAND and not business_kind:
            business_kind = CustomPrintBusinessKind.BRANDING
        if cleaned.get("product_type") == CustomPrintProductType.CUSTOMER_GARMENT and not garment_note:
            self.add_error("garment_note", "Опишіть ваш виріб для попереднього прорахунку.")

        if (
            require_artwork_files
            and service_kind == CustomPrintServiceKind.READY
            and len(files) < required_artwork_file_count
        ):
            self.add_error("files", "Додайте файли для всіх зон, де потрібен макет.")

        if service_kind == CustomPrintServiceKind.ADJUST:
            if not brief:
                self.add_error("brief", "Опишіть, що саме потрібно змінити у файлі.")
            if require_artwork_files and len(files) < required_artwork_file_count:
                self.add_error("files", "Додайте файли для всіх зон, де потрібен макет.")

        if service_kind == CustomPrintServiceKind.DESIGN and not brief:
            self.add_error("brief", "Опишіть ідею, стиль або референси для дизайну.")

        validated_files = []
        limits = get_limits()
        for uploaded_file in files:
            try:
                validate_uploaded_file(
                    uploaded_file,
                    allowed_exts=ALLOWED_HELP_EXTS,
                    max_file_mb=limits["max_file_mb"],
                    strict_magic=True,
                )
            except ValueError as exc:
                code = str(exc)
                if code == "unsupported_extension":
                    self.add_error("files", "Непідтримуваний формат файлу.")
                elif code == "file_too_large":
                    self.add_error("files", f"Файл перевищує ліміт {limits['max_file_mb']} MB.")
                else:
                    self.add_error("files", "Один із файлів не пройшов перевірку безпеки.")
                continue
            uploaded_file.name = build_safe_upload_name("custom-print", uploaded_file.name)
            validated_files.append(uploaded_file)

        cleaned["client_kind"] = client_kind
        cleaned["business_kind"] = business_kind
        cleaned["brief"] = brief
        cleaned["garment_note"] = garment_note
        cleaned["placement_note"] = placement_note
        cleaned["placement_specs_json"] = placement_specs
        cleaned["pricing_snapshot_json"] = pricing_snapshot
        cleaned["config_draft_json"] = normalized_snapshot or config_draft or {}
        cleaned["fit"] = (cleaned.get("fit") or (normalized_snapshot.get("product") or {}).get("fit") or "").strip()
        cleaned["fabric"] = (cleaned.get("fabric") or (normalized_snapshot.get("product") or {}).get("fabric") or "").strip()
        cleaned["color_choice"] = (
            cleaned.get("color_choice")
            or (normalized_snapshot.get("product") or {}).get("color")
            or ""
        ).strip()
        cleaned["file_triage_status"] = (
            cleaned.get("file_triage_status")
            or (normalized_snapshot.get("artwork") or {}).get("triage_status")
            or ""
        ).strip()
        cleaned["exit_step"] = (
            cleaned.get("exit_step")
            or (normalized_snapshot.get("ui") or {}).get("current_step")
            or ""
        ).strip()
        self.cleaned_files = validated_files
        return cleaned

    def save(self) -> CustomPrintLead:
        lead = CustomPrintLead.objects.create(
            service_kind=self.cleaned_data["service_kind"],
            product_type=self.cleaned_data["product_type"],
            placements=self.cleaned_data["placements"],
            placement_note=self.cleaned_data.get("placement_note", ""),
            quantity=self.cleaned_data["quantity"],
            size_mode=self.cleaned_data.get("size_mode", ""),
            sizes_note=self.cleaned_data.get("sizes_note", ""),
            client_kind=self.cleaned_data.get("client_kind") or CustomPrintClientKind.PERSONAL,
            business_kind=self.cleaned_data.get("business_kind", ""),
            brand_name=self.cleaned_data.get("brand_name", ""),
            fit=self.cleaned_data.get("fit", ""),
            fabric=self.cleaned_data.get("fabric", ""),
            color_choice=self.cleaned_data.get("color_choice", ""),
            garment_note=self.cleaned_data.get("garment_note", ""),
            file_triage_status=self.cleaned_data.get("file_triage_status", ""),
            exit_step=self.cleaned_data.get("exit_step", ""),
            placement_specs_json=self.cleaned_data.get("placement_specs_json") or [],
            pricing_snapshot_json=self.cleaned_data.get("pricing_snapshot_json") or {},
            config_draft_json=self.cleaned_data.get("config_draft_json") or {},
            name=self.cleaned_data["name"],
            contact_channel=self.cleaned_data["contact_channel"],
            contact_value=self.cleaned_data["contact_value"],
            brief=self.cleaned_data.get("brief", ""),
            source="main_custom_print",
        )
        placement_specs = self.cleaned_data.get("placement_specs_json") or []
        file_spec_map = {}
        for spec in placement_specs:
            file_index = spec.get("file_index")
            if file_index is None:
                continue
            try:
                file_index = int(file_index)
            except (TypeError, ValueError):
                continue
            file_spec_map.setdefault(file_index, spec)

        for sort_order, uploaded_file in enumerate(getattr(self, "cleaned_files", [])):
            matched_spec = file_spec_map.get(sort_order)
            if matched_spec is None and sort_order < len(placement_specs):
                matched_spec = placement_specs[sort_order]
            CustomPrintLeadAttachment.objects.create(
                lead=lead,
                file=uploaded_file,
                placement_zone=(matched_spec or {}).get("placement_key") or (matched_spec or {}).get("zone", ""),
                attachment_role=(matched_spec or {}).get("attachment_role")
                or CustomPrintLeadAttachment.AttachmentRole.DESIGN,
                sort_order=sort_order,
            )
        return lead


class ProductForm(forms.ModelForm):
    # множественный аплоад: безопасно обрабатываем список файлов
    extra_images = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={
            "multiple": True,
            "accept": "image/*",
            "class": "form-control d-none",
            "data-extra-images-input": "1"
        })
    )

    class Meta:
        model = Product
        fields = [
            # Поля которые РЕАЛЬНО отправляет шаблон admin_product_edit_unified.html
            "title",
            "slug",
            "category",
            "status",
            "priority",
            "price",
            "discount_percent",
            "featured",
            "description",
            "main_image",
            "points_reward",
            # Дополнительные поля для других шаблонов (опциональные)
            "catalog",
            "size_grid",
            "short_description",
            "full_description",
            "main_image_alt",
            "drop_price",
            "wholesale_price",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "short_description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "full_description": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "catalog": forms.Select(attrs={"class": "form-control"}),
            "size_grid": forms.Select(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "discount_percent": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "100"}),
            "priority": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "main_image": forms.FileInput(attrs={"class": "form-control d-none", "accept": "image/*", "data-main-image-input": "1"}),
            "main_image_alt": forms.TextInput(attrs={"class": "form-control"}),
            "points_reward": forms.NumberInput(attrs={"class": "form-control", "min": "0", "value": "0"}),
            "drop_price": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "wholesale_price": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Позволяем создавать товары без явного указания дроп/опт цены — проставляем 0 по умолчанию
        for price_field in ('drop_price', 'wholesale_price'):
            if price_field in self.fields:
                self.fields[price_field].required = False
                self.fields[price_field].initial = self.fields[price_field].initial or 0

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

        # Дроп/опт цены — задаем 0 по умолчанию, валидируем на неотрицательность
        for field_name in ('drop_price', 'wholesale_price'):
            value = data.get(field_name)
            if value in (None, ''):
                data[field_name] = 0
                continue
            try:
                numeric_value = int(value)
                if numeric_value < 0:
                    self.add_error(field_name, "Ціна не може бути від'ємною")
                else:
                    data[field_name] = numeric_value
            except (ValueError, TypeError):
                self.add_error(field_name, "Невірний формат ціни")

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
