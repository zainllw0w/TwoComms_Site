from django import forms
from django.utils.translation import gettext_lazy as _


class CommercialOfferEmailForm(forms.Form):
    recipient_email = forms.EmailField(label=_("Email отримувача"), max_length=254)
    recipient_name = forms.CharField(label=_("Імʼя/компанія отримувача"), max_length=255, required=False)

    MODE_CHOICES = (
        ("LIGHT", "Light"),
        ("VISUAL", "Visual"),
    )
    SEGMENT_CHOICES = (
        ("NEUTRAL", "Neutral"),
        ("EDGY", "Edgy"),
    )
    SUBJECT_PRESET_CHOICES = (
        ("PRESET_1", "TwoComms: Тест-ростовка 14 днів…"),
        ("PRESET_2", "Опт від 8 шт / Дропшип…"),
        ("PRESET_3", "📦 Тест-драйв 14 днів…"),
        ("CUSTOM", "Custom"),
    )

    mode = forms.ChoiceField(label=_("Режим"), choices=MODE_CHOICES, required=False, initial="VISUAL")
    segment_mode = forms.ChoiceField(label=_("Сегмент"), choices=SEGMENT_CHOICES, required=False, initial="NEUTRAL")
    subject_preset = forms.ChoiceField(label=_("Тема листа"), choices=SUBJECT_PRESET_CHOICES, required=False, initial="PRESET_1")
    subject_custom = forms.CharField(label=_("Кастомна тема"), max_length=255, required=False)

    tee_entry = forms.IntegerField(label=_("Вхід футболка (грн)"), required=False, min_value=0)
    tee_retail_example = forms.IntegerField(label=_("Роздріб футболка (приклад, грн)"), required=False, min_value=0)
    hoodie_entry = forms.IntegerField(label=_("Вхід худі (грн)"), required=False, min_value=0)
    hoodie_retail_example = forms.IntegerField(label=_("Роздріб худі (приклад, грн)"), required=False, min_value=0)

    show_manager = forms.BooleanField(label=_("Показувати менеджера"), required=False, initial=True)
    manager_name = forms.CharField(label=_("Імʼя менеджера"), max_length=255, required=False)
    phone = forms.CharField(label=_("Телефон"), max_length=50, required=False)

    viber_enabled = forms.BooleanField(label=_("Viber"), required=False)
    viber = forms.CharField(label=_("Viber"), max_length=100, required=False)

    whatsapp_enabled = forms.BooleanField(label=_("WhatsApp"), required=False)
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=100, required=False)

    telegram_enabled = forms.BooleanField(label=_("Telegram"), required=False)
    telegram = forms.CharField(label=_("Telegram"), max_length=100, required=False)

    confirm_resend = forms.IntegerField(required=False, min_value=0, max_value=1)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_recipient_name(self):
        return (self.cleaned_data.get("recipient_name") or "").strip()

    def clean_manager_name(self):
        return (self.cleaned_data.get("manager_name") or "").strip()

    def clean_phone(self):
        return (self.cleaned_data.get("phone") or "").strip()

    def clean_viber(self):
        return (self.cleaned_data.get("viber") or "").strip()

    def clean_whatsapp(self):
        return (self.cleaned_data.get("whatsapp") or "").strip()

    def clean_telegram(self):
        return (self.cleaned_data.get("telegram") or "").strip()

    def clean(self):
        cleaned = super().clean()

        show_manager = bool(cleaned.get("show_manager"))
        manager_name = (cleaned.get("manager_name") or "").strip()
        if show_manager and not manager_name:
            default_name = ""
            if self.user:
                try:
                    prof = self.user.userprofile
                    default_name = (getattr(prof, "full_name", "") or "").strip()
                except Exception:
                    default_name = ""
                if not default_name:
                    default_name = (self.user.get_full_name() or self.user.username or "").strip()
            cleaned["manager_name"] = default_name

        subject_preset = (cleaned.get("subject_preset") or "PRESET_1").strip().upper()
        subject_custom = (cleaned.get("subject_custom") or "").strip()
        cleaned["subject_custom"] = subject_custom
        if subject_preset == "CUSTOM" and not subject_custom:
            self.add_error("subject_custom", _("Вкажіть кастомну тему листа."))

        def require_if_enabled(enabled_key: str, value_key: str, label: str):
            enabled = bool(cleaned.get(enabled_key))
            value = (cleaned.get(value_key) or "").strip()
            cleaned[value_key] = value
            if show_manager and enabled and not value:
                self.add_error(value_key, _("Вкажіть контакт для %(label)s.") % {"label": label})

        require_if_enabled("viber_enabled", "viber", "Viber")
        require_if_enabled("whatsapp_enabled", "whatsapp", "WhatsApp")
        require_if_enabled("telegram_enabled", "telegram", "Telegram")

        return cleaned


class CommercialOfferEmailPreviewForm(CommercialOfferEmailForm):
    recipient_email = forms.EmailField(label=_("Email отримувача"), max_length=254, required=False)
