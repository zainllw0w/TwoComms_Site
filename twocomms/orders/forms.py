from django import forms

class CompanyProfileForm(forms.Form):
    company_name = forms.CharField(
        label="Назва компанії",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "TwoComms Partner"})
    )
    company_number = forms.CharField(
        label="ЄДРПОУ / ІПН",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "1234567890"})
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "+380XXXXXXXXX"})
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "partner@email.com"})
    )
    website = forms.URLField(
        label="Сайт або магазин",
        required=False,
        widget=forms.URLInput(attrs={"placeholder": "https://"})
    )
    instagram = forms.CharField(
        label="Instagram",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "@brand"})
    )
    telegram = forms.CharField(
        label="Telegram",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "@manager"})
    )
    payment_details = forms.CharField(
        label="Реквізити для виплат",
        required=False,
        widget=forms.Textarea(
            attrs={
                "placeholder": "IBAN або номер картки",
                "rows": 4,
                "maxlength": 180,
                "class": "ds-textarea ds-textarea--payment",
            }
        )
    )
    avatar = forms.ImageField(
        label="Логотип",
        required=False
    )

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError('Телефон обов’язковий для заповнення.')
        return phone

    def clean(self):
        cleaned = super().clean()
        return cleaned

    def clean_website(self):
        website = self.cleaned_data.get('website', '').strip()
        if website and not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        return website

    def clean_instagram(self):
        instagram = self.cleaned_data.get('instagram', '').strip()
        if instagram and not instagram.startswith('@') and 'http' not in instagram:
            instagram = f'@{instagram}'
        return instagram

    def clean_payment_details(self):
        return self.cleaned_data.get('payment_details', '').strip()
