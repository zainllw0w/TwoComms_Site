"""Phase 21 (PR-4c) — review submission form.

Supports both authenticated users and guests. Photo handling is at the
view layer (``InMemoryUploadedFile`` list); the form only validates
text + rating + honeypot + length floors.

Validation contract:
    * rating ∈ {1, 2, 3, 4, 5}
    * body length ≥ 20 visible characters (whitespace-stripped)
    * author_name 1–80 chars
    * email optional but RFC-validated when provided
    * honeypot field ``website`` MUST be empty (bot trap)
"""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError


_MIN_BODY_LEN = 20


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=[(str(n), f"{n}★") for n in range(1, 6)],
        coerce=int,
        empty_value=0,
        error_messages={"required": "Оберіть оцінку від 1 до 5."},
    )
    title = forms.CharField(
        required=False,
        max_length=120,
        strip=True,
    )
    body = forms.CharField(
        widget=forms.Textarea,
        max_length=4000,
        strip=True,
        error_messages={"required": "Розкажіть про свій досвід — мінімум 20 символів."},
    )
    author_name = forms.CharField(
        max_length=80,
        strip=True,
        error_messages={"required": "Як вас підписати?"},
    )
    email = forms.EmailField(
        required=False,
    )

    # Honeypot — visible to bots, hidden from humans via CSS in the
    # template. If anything ends up here we silently reject as if the
    # form was valid (caller checks ``cleaned_data['_is_bot']``).
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_rating(self) -> int:
        value = int(self.cleaned_data.get("rating") or 0)
        if value < 1 or value > 5:
            raise ValidationError("Оцінка має бути цілим числом 1-5.")
        return value

    def clean_body(self) -> str:
        body = (self.cleaned_data.get("body") or "").strip()
        if len(body) < _MIN_BODY_LEN:
            raise ValidationError(
                f"Текст відгуку має містити щонайменше {_MIN_BODY_LEN} символів."
            )
        return body

    def clean_author_name(self) -> str:
        name = (self.cleaned_data.get("author_name") or "").strip()
        if not name:
            raise ValidationError("Введіть ім'я для публікації.")
        return name

    def clean(self):
        cleaned = super().clean()
        cleaned["_is_bot"] = bool((cleaned.get("website") or "").strip())
        return cleaned
