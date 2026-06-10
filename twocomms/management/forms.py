import re

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

    PRICING_MODE_CHOICES = (
        ("OPT", "OPT — опт"),
        ("DROP", "DROP — дроп"),
    )
    OPT_TIER_CHOICES = (
        ("8_15", "8–15 (мінімальне)"),
        ("16_31", "16–31"),
        ("32_63", "32–63"),
        ("64_99", "64–99"),
        ("100_PLUS", "100+ (макс вигода)"),
    )

    pricing_mode = forms.ChoiceField(label=_("Тип цін"), choices=PRICING_MODE_CHOICES, required=False, initial="OPT")
    opt_tier = forms.ChoiceField(label=_("Орієнтовний обсяг замовлення"), choices=OPT_TIER_CHOICES, required=False, initial="8_15")
    drop_tee_price = forms.IntegerField(label=_("Дроп: футболка (грн)"), required=False, min_value=0)
    drop_hoodie_price = forms.IntegerField(label=_("Дроп: худі (грн)"), required=False, min_value=0)
    dropship_loyalty_bonus = forms.BooleanField(label=_("Бонус дропу −10 грн"), required=False)

    CTA_TYPE_CHOICES = (
        ("", "Авто (рекомендовано)"),
        ("TELEGRAM_MANAGER", "Telegram менеджера"),
        ("WHATSAPP_MANAGER", "WhatsApp менеджера"),
        ("MAILTO_COOPERATION", "На email cooperation@"),
    )

    cta_type = forms.ChoiceField(label=_("Кнопка зв'язку"), choices=CTA_TYPE_CHOICES, required=False)
    cta_button_text = forms.CharField(label=_("Текст кнопки"), max_length=120, required=False)
    cta_custom_url = forms.CharField(label=_("Своє посилання кнопки"), max_length=500, required=False)
    cta_microtext = forms.CharField(label=_("Підпис під кнопкою"), max_length=255, required=False)

    tee_entry = forms.IntegerField(label=_("Вхідна ціна футболки (грн)"), required=False, min_value=0)
    tee_retail_example = forms.IntegerField(label=_("Приклад роздробу футболки (грн)"), required=False, min_value=0)
    hoodie_entry = forms.IntegerField(label=_("Вхідна ціна худі (грн)"), required=False, min_value=0)
    hoodie_retail_example = forms.IntegerField(label=_("Приклад роздробу худі (грн)"), required=False, min_value=0)

    show_manager = forms.BooleanField(label=_("Показувати менеджера"), required=False, initial=True)
    manager_name = forms.CharField(label=_("Імʼя менеджера"), max_length=255, required=False)
    phone_enabled = forms.BooleanField(label=_("Телефон"), required=False)
    phone = forms.CharField(label=_("Телефон"), max_length=50, required=False)

    viber_enabled = forms.BooleanField(label=_("Viber"), required=False)
    viber = forms.CharField(label=_("Viber"), max_length=100, required=False)

    whatsapp_enabled = forms.BooleanField(label=_("WhatsApp"), required=False)
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=100, required=False)

    telegram_enabled = forms.BooleanField(label=_("Telegram"), required=False)
    telegram = forms.CharField(label=_("Telegram"), max_length=100, required=False)

    general_tg = forms.CharField(label=_("Резервний Telegram"), max_length=255, required=False)

    include_catalog_link = forms.BooleanField(label=_("Каталог"), required=False, initial=True)
    include_wholesale_link = forms.BooleanField(label=_("Опт"), required=False, initial=True)
    include_dropship_link = forms.BooleanField(label=_("Дроп"), required=False, initial=True)
    include_instagram_link = forms.BooleanField(label=_("Instagram"), required=False, initial=True)
    include_site_link = forms.BooleanField(label=_("Сайт"), required=False, initial=True)

    gallery_neutral = forms.JSONField(label=_("Галерея Neutral"), required=False)
    gallery_edgy = forms.JSONField(label=_("Галерея Edgy"), required=False)

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

    def clean_general_tg(self):
        return (self.cleaned_data.get("general_tg") or "").strip()

    def clean_gallery_neutral(self):
        value = self.cleaned_data.get("gallery_neutral")
        if not value:
            return []
        if not isinstance(value, list):
            return []
        slots = []
        for item in value:
            if isinstance(item, str):
                url = item.strip()
                caption = ""
            elif isinstance(item, dict):
                url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
                caption = str(item.get("caption") or item.get("title") or "").strip()
            else:
                continue
            if url:
                slots.append({"url": url, "caption": caption})
        return slots[:6]

    def clean_gallery_edgy(self):
        value = self.cleaned_data.get("gallery_edgy")
        if not value:
            return []
        if not isinstance(value, list):
            return []
        slots = []
        for item in value:
            if isinstance(item, str):
                url = item.strip()
                caption = ""
            elif isinstance(item, dict):
                url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
                caption = str(item.get("caption") or item.get("title") or "").strip()
            else:
                continue
            if url:
                slots.append({"url": url, "caption": caption})
        return slots[:6]

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

        cta_type = (cleaned.get("cta_type") or "").strip().upper()
        cleaned["cta_type"] = cta_type
        cleaned["cta_button_text"] = (cleaned.get("cta_button_text") or "").strip()
        cleaned["cta_custom_url"] = (cleaned.get("cta_custom_url") or "").strip()
        cleaned["cta_microtext"] = (cleaned.get("cta_microtext") or "").strip()
        if cta_type == "CUSTOM_URL" and not cleaned["cta_custom_url"]:
            self.add_error("cta_custom_url", _("Вкажіть URL для CTA."))

        pricing_mode = (cleaned.get("pricing_mode") or "OPT").strip().upper()
        if pricing_mode not in {"OPT", "DROP"}:
            pricing_mode = "OPT"
        cleaned["pricing_mode"] = pricing_mode

        opt_tier = (cleaned.get("opt_tier") or "8_15").strip().upper()
        if opt_tier not in {"8_15", "16_31", "32_63", "64_99", "100_PLUS"}:
            opt_tier = "8_15"
        cleaned["opt_tier"] = opt_tier

        def normalize_ua_phone(raw: str) -> str:
            s = (raw or "").strip()
            if not s:
                return ""
            digits = re.sub(r"\D+", "", s)
            if not digits:
                return s
            if digits.startswith("380") and len(digits) == 12:
                return f"+{digits}"
            if digits.startswith("0") and len(digits) == 10:
                return f"+38{digits}"
            if len(digits) == 9:
                return f"+380{digits}"
            if s.startswith("+") and digits:
                return f"+{digits}"
            return s

        phone_enabled = bool(cleaned.get("phone_enabled"))
        cleaned["phone_enabled"] = phone_enabled
        cleaned["phone"] = normalize_ua_phone(cleaned.get("phone") or "")
        if show_manager and phone_enabled:
            if not cleaned["phone"]:
                self.add_error("phone", _("Вкажіть телефон менеджера або вимкніть цей контакт."))
            elif not re.match(r"^\+380\d{9}$", cleaned["phone"]):
                self.add_error("phone", _("Телефон має бути у форматі +380XXXXXXXXX."))

        def require_if_enabled(enabled_key: str, value_key: str, label: str):
            enabled = bool(cleaned.get(enabled_key))
            value = (cleaned.get(value_key) or "").strip()
            cleaned[value_key] = value
            if show_manager and enabled and not value:
                self.add_error(value_key, _("Вкажіть контакт для %(label)s.") % {"label": label})

        require_if_enabled("viber_enabled", "viber", "Viber")
        require_if_enabled("whatsapp_enabled", "whatsapp", "WhatsApp")
        require_if_enabled("telegram_enabled", "telegram", "Telegram")

        if show_manager:
            cleaned["viber"] = normalize_ua_phone(cleaned.get("viber") or "") if bool(cleaned.get("viber_enabled")) else (cleaned.get("viber") or "")
            cleaned["whatsapp"] = normalize_ua_phone(cleaned.get("whatsapp") or "") if bool(cleaned.get("whatsapp_enabled")) else (cleaned.get("whatsapp") or "")

        return cleaned


class CommercialOfferEmailPreviewForm(CommercialOfferEmailForm):
    recipient_email = forms.EmailField(label=_("Email отримувача"), max_length=254, required=False)
