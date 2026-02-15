from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    DtfFulfillmentKind,
    DtfLifecycleStatus,
    DtfOrder,
    DtfPaymentStatus,
    KnowledgePost,
)
from .utils import unique_slug_for_queryset

try:
    from storefront.models import PromoCode, PromoCodeGroup
except Exception:  # pragma: no cover - storefront is expected in production
    PromoCode = None
    PromoCodeGroup = None


class DtfAdminOrderUpdateForm(forms.ModelForm):
    class Meta:
        model = DtfOrder
        fields = [
            "status",
            "lifecycle_status",
            "payment_status",
            "payment_amount",
            "payment_reference",
            "payment_link",
            "tracking_number",
            "delivery_point_type",
            "delivery_point_code",
            "delivery_point_label",
            "fulfillment_kind",
            "product_type",
            "print_placement",
            "product_quantity",
            "manager_note",
        ]
        widgets = {
            "manager_note": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        lifecycle = cleaned.get("lifecycle_status")
        tracking_number = (cleaned.get("tracking_number") or "").strip()
        payment_status = cleaned.get("payment_status")
        fulfillment_kind = cleaned.get("fulfillment_kind")
        product_quantity = cleaned.get("product_quantity")

        if lifecycle == DtfLifecycleStatus.SHIPPED and not tracking_number:
            self.add_error("tracking_number", _("Вкажіть ТТН перед переходом у статус 'Відправлено'."))

        if payment_status in {DtfPaymentStatus.PAID, DtfPaymentStatus.PARTIAL}:
            if not self.instance.payment_updated_at:
                self.instance.payment_updated_at = timezone.now()

        if fulfillment_kind == DtfFulfillmentKind.CUSTOM_PRODUCT and not product_quantity:
            self.add_error("product_quantity", _("Вкажіть кількість виробів для замовлення готового продукту."))

        return cleaned


class DtfKnowledgePostAdminForm(forms.ModelForm):
    class Meta:
        model = KnowledgePost
        fields = [
            "title",
            "slug",
            "excerpt",
            "content_md",
            "content_rich_html",
            "pub_date",
            "is_published",
            "seo_title",
            "seo_description",
            "seo_keywords",
        ]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "content_md": forms.Textarea(attrs={"rows": 8}),
            "content_rich_html": forms.Textarea(attrs={"rows": 12}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_slug(self):
        slug_raw = (self.cleaned_data.get("slug") or "").strip()
        title = (self.cleaned_data.get("title") or "").strip()
        base = slug_raw or title
        return unique_slug_for_queryset(
            KnowledgePost.objects.all(),
            base,
            fallback="knowledge-post",
            max_length=240,
            exclude_pk=self.instance.pk,
        )

    def clean(self):
        cleaned = super().clean()
        content_md = (cleaned.get("content_md") or "").strip()
        content_rich_html = (cleaned.get("content_rich_html") or "").strip()
        if not content_md and not content_rich_html:
            self.add_error("content_md", _("Додайте контент: Markdown або Rich HTML."))
        return cleaned


if PromoCode is not None:
    class DtfAdminPromoCodeForm(forms.ModelForm):
        valid_from = forms.DateTimeField(
            required=False,
            input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
            widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        )
        valid_until = forms.DateTimeField(
            required=False,
            input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
            widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        )

        class Meta:
            model = PromoCode
            fields = [
                "code",
                "promo_type",
                "discount_type",
                "discount_value",
                "description",
                "group",
                "max_uses",
                "one_time_per_user",
                "min_order_amount",
                "valid_from",
                "valid_until",
                "is_active",
            ]
            widgets = {
                "description": forms.Textarea(attrs={"rows": 3}),
            }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if PromoCodeGroup is not None and "group" in self.fields:
                self.fields["group"].queryset = PromoCodeGroup.objects.filter(is_active=True).order_by("name")
                self.fields["group"].required = False

            for field_name in ("valid_from", "valid_until"):
                dt = getattr(self.instance, field_name, None)
                if dt and field_name in self.fields and not self.initial.get(field_name):
                    self.initial[field_name] = timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

        def clean_code(self):
            raw = (self.cleaned_data.get("code") or "").strip().upper()
            if raw:
                return raw
            if getattr(self.instance, "pk", None) and getattr(self.instance, "code", ""):
                return self.instance.code
            if hasattr(PromoCode, "generate_code"):
                return PromoCode.generate_code()
            return ""

        def clean(self):
            cleaned = super().clean()
            valid_from = cleaned.get("valid_from")
            valid_until = cleaned.get("valid_until")
            if valid_from and valid_until and valid_until <= valid_from:
                self.add_error("valid_until", _("Дата завершення має бути пізніше дати початку."))

            discount_value = cleaned.get("discount_value")
            if discount_value is not None and discount_value <= 0:
                self.add_error("discount_value", _("Значення знижки має бути більше нуля."))
            return cleaned
else:
    class DtfAdminPromoCodeForm(forms.Form):
        """Fallback form if storefront app is unavailable."""
