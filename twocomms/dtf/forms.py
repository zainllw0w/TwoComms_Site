from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import (
    BuilderPlacement,
    BuilderProductType,
    DtfBuilderSession,
    DtfLead,
    DtfOrder,
    DtfSampleLead,
    SampleSize,
)
from .preflight.engine import analyze_upload
from .utils import (
    ALLOWED_CONSTRUCTOR_EXTS,
    ALLOWED_HELP_EXTS,
    ALLOWED_READY_EXTS,
    build_safe_upload_name,
    build_content_file_from_bytes,
    detect_length_m,
    get_limits,
    normalize_phone,
    render_constructor_preview,
    validate_uploaded_file,
)


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned = []
        for item in data:
            cleaned.append(super().clean(item, initial))
        return cleaned


class DtfOrderForm(forms.ModelForm):
    trust_check = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = DtfOrder
        fields = [
            "name",
            "phone",
            "contact_channel",
            "contact_handle",
            "city",
            "np_branch",
            "gang_file",
            "length_m",
            "copies",
            "comment",
        ]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.setdefault("data-vanish-input", "1")

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "").strip()
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise ValidationError(_("Введіть коректний номер телефону"))
        return value

    def clean_gang_file(self):
        file = self.cleaned_data.get("gang_file")
        if not file:
            raise ValidationError(_("Завантажте файл ганг-листа"))
        limits = get_limits()
        try:
            validate_uploaded_file(
                file,
                allowed_exts=ALLOWED_READY_EXTS,
                max_file_mb=limits["max_file_mb"],
                strict_magic=True,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "unsupported_extension":
                raise ValidationError(
                    _("Формат файлу не підтримується для готового ганг-листа. Використайте PDF або PNG.")
                )
            if code == "file_too_large":
                raise ValidationError(
                    _("Файл завеликий. Максимум %(max_size)s MB") % {"max_size": limits["max_file_mb"]}
                )
            raise ValidationError(_("Файл не пройшов перевірку безпеки. Завантажте коректний PDF або PNG."))

        file.name = build_safe_upload_name("orders", file.name)
        return file

    def clean_length_m(self):
        value = self.cleaned_data.get("length_m")
        if value is None:
            return value
        if value <= 0:
            raise ValidationError(_("Довжина має бути більшою за нуль"))
        return value

    def clean_copies(self):
        value = self.cleaned_data.get("copies")
        if value is None:
            raise ValidationError(_("Вкажіть кількість копій"))
        if value < 1:
            raise ValidationError(_("Мінімум 1 копія"))
        limits = get_limits()
        if value > limits["max_copies"]:
            self._copies_requires_review = True
        return value

    def clean(self):
        cleaned = super().clean()
        length_m = cleaned.get("length_m")
        gang_file = cleaned.get("gang_file")
        if length_m is None and gang_file:
            auto_length = detect_length_m(gang_file)
            if auto_length:
                cleaned["length_m"] = Decimal(auto_length)
                self._auto_length_m = auto_length
            else:
                self.add_error("length_m", _("Не вдалося визначити довжину файлу. Вкажіть вручну."))
        return cleaned


class DtfHelpForm(forms.ModelForm):
    files = MultiFileField(required=False, widget=MultiFileInput(attrs={"multiple": True}))
    folder_link = forms.URLField(required=False)

    class Meta:
        model = DtfLead
        fields = [
            "name",
            "phone",
            "contact_channel",
            "contact_handle",
            "city",
            "np_branch",
            "task_description",
            "deadline_note",
            "folder_link",
        ]
        widgets = {
            "task_description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "").strip()
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise ValidationError(_("Введіть коректний номер телефону"))
        return value

    def clean(self):
        cleaned = super().clean()
        files = cleaned.get("files") or []
        if not isinstance(files, (list, tuple)):
            files = [files]
        folder_link = cleaned.get("folder_link")
        task = cleaned.get("task_description", "").strip()
        if not task:
            self.add_error("task_description", _("Опишіть задачу"))
        if not files and not folder_link:
            self.add_error("folder_link", _("Завантажте файли або додайте посилання на папку"))

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
                    self.add_error("files", _("Непідтримуваний формат файлу у вкладеннях."))
                elif code == "file_too_large":
                    self.add_error("files", _("Один із файлів перевищує ліміт %(max_size)s MB.") % {"max_size": limits["max_file_mb"]})
                else:
                    self.add_error("files", _("Один із файлів не пройшов перевірку безпеки."))
                continue
            uploaded_file.name = build_safe_upload_name("leads", uploaded_file.name)
            validated_files.append(uploaded_file)

        self._validated_files = validated_files
        return cleaned


class DtfFabLeadForm(forms.ModelForm):
    class Meta:
        model = DtfLead
        fields = [
            "name",
            "phone",
            "contact_channel",
            "contact_handle",
            "task_description",
        ]
        widgets = {
            "task_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "name" in self.fields:
            self.fields["name"].widget.attrs.setdefault("autocomplete", "name")
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.setdefault("autocomplete", "tel")
        if "contact_handle" in self.fields:
            self.fields["contact_handle"].widget.attrs.setdefault("autocomplete", "off")

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "").strip()
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise ValidationError(_("Введіть коректний номер телефону"))
        return value


class DtfSampleLeadForm(forms.ModelForm):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = DtfSampleLead
        fields = [
            "sample_size",
            "is_brand_volume",
            "name",
            "phone",
            "contact_channel",
            "contact_handle",
            "city",
            "np_branch",
            "niche",
            "monthly_volume",
            "comment",
            "consent",
        ]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3}),
            "sample_size": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.setdefault("data-vanish-input", "1")

    def clean_honeypot(self):
        value = (self.cleaned_data.get("honeypot") or "").strip()
        if value:
            raise ValidationError(_("Spam detected"))
        return value

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "").strip()
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise ValidationError(_("Введіть коректний номер телефону"))
        return value

    def clean(self):
        cleaned = super().clean()
        sample_size = cleaned.get("sample_size")
        is_brand = cleaned.get("is_brand_volume")
        if sample_size == SampleSize.A3 and not is_brand:
            self.add_error("is_brand_volume", _("Для A3 зразка позначте, що ви бренд або плануєте об'єм."))
        if not cleaned.get("consent"):
            self.add_error("consent", _("Потрібна згода на обробку даних"))
        return cleaned


def _parse_size_breakdown(raw: str) -> dict:
    source = (raw or "").strip()
    if not source:
        return {}
    result = {}
    for chunk in source.split(","):
        part = chunk.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        size = key.strip().upper()[:12]
        try:
            qty = int(value.strip())
        except ValueError:
            continue
        if qty > 0:
            result[size] = qty
    return result


class DtfBuilderSessionForm(forms.ModelForm):
    size_breakdown = forms.CharField(
        required=False,
        help_text=_("Формат: S:10,M:20,L:5"),
    )
    risk_ack = forms.BooleanField(required=False)

    class Meta:
        model = DtfBuilderSession
        fields = [
            "product_type",
            "product_color",
            "quantity",
            "placement",
            "design_file",
            "delivery_city",
            "delivery_np_branch",
            "comment",
            "risk_ack",
        ]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3}),
            "product_type": forms.Select(choices=BuilderProductType.choices),
            "placement": forms.Select(choices=BuilderPlacement.choices),
        }

    def clean_design_file(self):
        file = self.cleaned_data.get("design_file")
        if not file:
            return file
        limits = get_limits()
        try:
            validate_uploaded_file(
                file,
                allowed_exts=ALLOWED_CONSTRUCTOR_EXTS,
                max_file_mb=limits["max_file_mb"],
                strict_magic=True,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "unsupported_extension":
                raise ValidationError(_("Підтримуються лише PDF/PNG/JPG/WEBP"))
            if code == "file_too_large":
                raise ValidationError(
                    _("Файл завеликий. Максимум %(max_size)s MB") % {"max_size": limits["max_file_mb"]}
                )
            raise ValidationError(_("Файл не пройшов перевірку безпеки"))
        file.name = build_safe_upload_name("builder", file.name)
        return file

    def clean_quantity(self):
        value = self.cleaned_data.get("quantity") or 0
        if value < 1:
            raise ValidationError(_("Мінімум 1 шт"))
        if value > 1000:
            raise ValidationError(_("Занадто велика кількість для MVP"))
        return value

    def clean(self):
        cleaned = super().clean()
        cleaned["size_breakdown_json"] = _parse_size_breakdown(self.data.get("size_breakdown", ""))
        placement = cleaned.get("placement")
        cleaned["placements_json"] = [placement] if placement else []

        design_file = cleaned.get("design_file")
        if design_file:
            report = analyze_upload(design_file, allowed_exts=ALLOWED_CONSTRUCTOR_EXTS)
            cleaned["preflight_json"] = report
            has_warn = bool(report.get("result") == "WARN" or report.get("has_warn"))
            has_fail = bool(report.get("result") == "FAIL" or report.get("has_fail"))
            if has_fail:
                self.add_error("design_file", _("Файл має критичні помилки preflight. Виправте перед відправкою."))
            if has_warn and not cleaned.get("risk_ack"):
                self.add_error("risk_ack", _("Підтвердіть ризики preflight, щоб продовжити."))

            preview = render_constructor_preview(
                design_file,
                product_type=cleaned.get("product_type") or BuilderProductType.TSHIRT,
                placement=placement or BuilderPlacement.FRONT,
                product_color=cleaned.get("product_color") or "#151515",
            )
            if preview:
                cleaned["preview_image_file"] = build_content_file_from_bytes(
                    preview,
                    build_safe_upload_name("builder-preview", "preview.png"),
                )
        return cleaned
