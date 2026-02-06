from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import DtfLead, DtfOrder, ContactChannel, LeadType
from .utils import ALLOWED_READY_EXTS, detect_length_m, get_file_extension, get_limits, normalize_phone


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


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
        ext = get_file_extension(file.name)
        if ext not in ALLOWED_READY_EXTS:
            raise ValidationError(_("Формат файлу не підтримується для готового ганг-листа. Використайте PDF або PNG."))
        limits = get_limits()
        max_bytes = limits["max_file_mb"] * 1024 * 1024
        if file.size and file.size > max_bytes:
            raise ValidationError(
                _("Файл завеликий. Максимум %(max_size)s MB") % {"max_size": limits["max_file_mb"]}
            )
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
    files = forms.FileField(required=False, widget=MultiFileInput(attrs={"multiple": True}))
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
        files = self.files.getlist("files") if hasattr(self, "files") else []
        folder_link = cleaned.get("folder_link")
        task = cleaned.get("task_description", "").strip()
        if not task:
            self.add_error("task_description", _("Опишіть задачу"))
        if not files and not folder_link:
            self.add_error("folder_link", _("Завантажте файли або додайте посилання на папку"))
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

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "").strip()
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise ValidationError(_("Введіть коректний номер телефону"))
        return value
