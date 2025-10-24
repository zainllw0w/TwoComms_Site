"""
Authentication views для storefront приложения.

Содержит views для login, register, logout и связанные формы.
"""

from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

from ..models import Product
from accounts.models import UserProfile, FavoriteProduct


# ==================== FORMS ====================

class LoginForm(forms.Form):
    """Форма входа в систему."""
    
    username = forms.CharField(
        label="Логін",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control bg-elevate"})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control bg-elevate"})
    )


class RegisterForm(forms.Form):
    """Форма регистрации нового пользователя."""
    
    username = forms.CharField(
        label="Логін",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control bg-elevate"})
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control bg-elevate"})
    )
    password2 = forms.CharField(
        label="Повтор паролю",
        widget=forms.PasswordInput(attrs={"class": "form-control bg-elevate"})
    )
    
    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Паролі не співпадають")
        return data


class ProfileSetupForm(forms.Form):
    """Форма первоначальной настройки профиля."""
    
    full_name = forms.CharField(
        label="ПІБ",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "Прізвище Ім'я По батькові"
        })
    )
    phone = forms.CharField(
        label="Телефон",
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "+380XXXXXXXXX"
        })
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "your@email.com"
        })
    )
    telegram = forms.CharField(
        label="Telegram",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "@username"
        })
    )
    instagram = forms.CharField(
        label="Instagram",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "@username"
        })
    )
    city = forms.CharField(
        label="Місто",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "Київ"
        })
    )
    np_office = forms.CharField(
        label="Відділення/Поштомат НП",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control bg-elevate",
            "placeholder": "№ відділення або адреса поштомата"
        })
    )
    pay_type = forms.ChoiceField(
        label="Тип оплати",
        required=False,
        choices=(
            ("partial", "Часткова передоплата"),
            ("full", "Повна передоплата")
        ),
        widget=forms.Select(attrs={"class": "form-select bg-elevate"})
    )
    avatar = forms.ImageField(label="Аватар", required=False)
    is_ubd = forms.BooleanField(
        label="Я — УБД",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    ubd_doc = forms.ImageField(
        label="Фото посвідчення УБД",
        required=False
    )
    
    def clean(self):
        data = super().clean()
        if data.get("is_ubd") and not data.get("ubd_doc"):
            self.add_error("ubd_doc", "Для УБД додайте фото посвідчення")
        return data


# ==================== VIEWS ====================

def login_view(request):
    """
    View для входа в систему.
    
    Features:
    - Проверяет аутентификацию
    - Переносит избранные товары из сессии в БД
    - Проверяет заполненность профиля
    - Поддерживает редирект через параметр 'next'
    """
    if request.user.is_authenticated:
        return redirect('profile_setup')
    
    form = LoginForm(request.POST or None)
    
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )
        
        if user:
            login(request, user)
            
            # Переносим избранные товары из сессии в базу данных
            session_favorites = request.session.get('favorites', [])
            if session_favorites:
                for product_id in session_favorites:
                    try:
                        product = Product.objects.get(id=product_id)
                        FavoriteProduct.objects.get_or_create(
                            user=user,
                            product=product
                        )
                    except Product.DoesNotExist:
                        # Товар был удален, пропускаем
                        continue
                
                # Очищаем сессию
                del request.session['favorites']
                request.session.modified = True
            
            # Если профиль пустой по телефону — просим заполнить
            try:
                prof = user.userprofile
            except UserProfile.DoesNotExist:
                prof = UserProfile.objects.create(user=user)
            
            if not prof.phone:
                return redirect('profile_setup')
            
            # Проверяем параметр next для перенаправления
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect('home')
        else:
            form.add_error(None, "Невірний логін або пароль")
    
    return render(request, 'pages/auth_login.html', {
        'form': form,
        'next': request.GET.get('next')
    })


def register_view(request):
    """
    View для регистрации нового пользователя.
    
    Features:
    - Проверяет уникальность username
    - Создает нового пользователя
    - Автоматически авторизует после регистрации
    - Переносит избранные товары из сессии
    - Редиректит на настройку профиля
    """
    if request.user.is_authenticated:
        return redirect('profile_setup')
    
    form = RegisterForm(request.POST or None)
    
    if request.method == 'POST' and form.is_valid():
        # Проверяем уникальность username
        if User.objects.filter(username=form.cleaned_data['username']).exists():
            form.add_error('username', 'Користувач з таким логіном вже існує')
        else:
            # Создаем пользователя
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1']
            )
            
            # Автоматически авторизуем
            login(request, user)
            
            # Переносим избранные товары из сессии в базу данных
            session_favorites = request.session.get('favorites', [])
            if session_favorites:
                for product_id in session_favorites:
                    try:
                        product = Product.objects.get(id=product_id)
                        FavoriteProduct.objects.get_or_create(
                            user=user,
                            product=product
                        )
                    except Product.DoesNotExist:
                        # Товар был удален, пропускаем
                        continue
                
                # Очищаем сессию
                del request.session['favorites']
                request.session.modified = True
            
            return redirect('profile_setup')
    
    return render(request, 'pages/auth_register.html', {'form': form})


def logout_view(request):
    """
    View для выхода из системы.
    
    Разлогинивает пользователя и редиректит на главную.
    """
    logout(request)
    return redirect('home')
















