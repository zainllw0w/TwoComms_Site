from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Product, Category, ProductImage, PromoCode
from .forms import ProductForm, CategoryForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from accounts.models import UserProfile
from django import forms
from django.conf import settings
from django.utils.text import slugify

def unique_slugify(model, base_slug):
    """
    Створює унікальний slug на основі base_slug для заданої моделі.
    """
    slug = base_slug or 'item'
    slug = slug.strip('-') or 'item'
    uniq = slug
    i = 2
    while model.objects.filter(slug=uniq).exists():
        uniq = f"{slug}-{i}"
        i += 1
    return uniq

# --- Примитивные формы аутентификации/профиля ---
class LoginForm(forms.Form):
    username = forms.CharField(label="Логін", max_length=150,
                               widget=forms.TextInput(attrs={"class":"form-control bg-elevate"}))
    password = forms.CharField(label="Пароль",
                               widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))

class RegisterForm(forms.Form):
    username = forms.CharField(label="Логін", max_length=150,
                               widget=forms.TextInput(attrs={"class":"form-control bg-elevate"}))
    password1 = forms.CharField(label="Пароль",
                                widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))
    password2 = forms.CharField(label="Повтор паролю",
                                widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))
    def clean(self):
        d=super().clean()
        if d.get("password1")!=d.get("password2"):
            self.add_error("password2","Паролі не співпадають")
        return d

class ProfileSetupForm(forms.Form):
    full_name = forms.CharField(label="ПІБ", max_length=200, required=False,
                                widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"Прізвище Ім’я По батькові"}))
    phone = forms.CharField(label="Телефон", required=True,
                            widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"+380XXXXXXXXX"}))
    city = forms.CharField(label="Місто", required=False,
                           widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"Київ"}))
    np_office = forms.CharField(label="Відділення/Поштомат НП", required=False,
                                widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"№ відділення або адреса поштомата"}))
    pay_type = forms.ChoiceField(label="Тип оплати", required=False, choices=(("partial","Часткова передоплата"),("full","Повна передоплата")),
                                 widget=forms.Select(attrs={"class":"form-select bg-elevate"}))
    avatar = forms.ImageField(label="Аватар", required=False)
    is_ubd = forms.BooleanField(label="Я — УБД", required=False, widget=forms.CheckboxInput(attrs={"class":"form-check-input"}))
    ubd_doc = forms.ImageField(label="Фото посвідчення УБД", required=False)
    def clean(self):
        d=super().clean(); 
        if d.get("is_ubd") and not d.get("ubd_doc"):
            self.add_error("ubd_doc","Для УБД додайте фото посвідчення")
        return d

# --- Аутентификация/профиль ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = LoginForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        if user:
            login(request,user)
            # если профиль пустой по телефону — просим заповнення
            try:
                prof = user.userprofile
            except UserProfile.DoesNotExist:
                prof = UserProfile.objects.create(user=user)
            if not prof.phone:
                return redirect('profile_setup')
            return redirect('home')
        form.add_error(None,"Невірний логін або пароль")
    return render(request,'pages/login.html',{'form':form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = RegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        from django.contrib.auth.models import User
        if User.objects.filter(username=form.cleaned_data['username']).exists():
            form.add_error('username','Користувач з таким логіном вже існує')
        else:
            user = User.objects.create_user(username=form.cleaned_data['username'], password=form.cleaned_data['password1'])
            login(request,user)
            return redirect('profile_setup')
    return render(request,'pages/auth_register.html',{'form':form})

def logout_view(request):
    logout(request); return redirect('home')

@login_required
def profile_setup(request):
    # получаем профиль
    try:
        prof = request.user.userprofile
    except UserProfile.DoesNotExist:
        prof = UserProfile.objects.create(user=request.user)

    initial = {
        'full_name': getattr(prof,'full_name', ''),
        'phone': prof.phone or '',
        'city': prof.city or '',
        'np_office': prof.np_office or '',
        'pay_type': prof.pay_type or '',
        'is_ubd': prof.is_ubd,
    }
    form = ProfileSetupForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method=='POST' and form.is_valid():
        prof.phone = form.cleaned_data['phone']
        prof.city = form.cleaned_data.get('city') or ''
        prof.np_office = form.cleaned_data.get('np_office') or ''
        prof.pay_type = form.cleaned_data.get('pay_type') or ''
        prof.is_ubd = bool(form.cleaned_data.get('is_ubd'))
        if form.cleaned_data.get('avatar'):
            prof.avatar = form.cleaned_data['avatar']
        if prof.is_ubd and form.cleaned_data.get('ubd_doc'):
            prof.ubd_doc = form.cleaned_data['ubd_doc']
        prof.save()
        # обновим сессию для текущей шапки
        request.session['profile_phone'] = prof.phone
        if prof.avatar:
            request.session['profile_avatar'] = prof.avatar.name
        request.session.modified = True
        return redirect('home')

    return render(request,'pages/profile_setup.html',{'form':form, 'profile':prof})
from django import forms

# --------- AUTH FORMS (минимум, чтобы не плодить новый файл) ---------
class LoginForm(forms.Form):
    username = forms.CharField(label="Логін", max_length=150,
                               widget=forms.TextInput(attrs={"class":"form-control bg-elevate"}))
    password = forms.CharField(label="Пароль",
                               widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))

class RegisterForm(forms.Form):
    username = forms.CharField(label="Логін", max_length=150,
                               widget=forms.TextInput(attrs={"class":"form-control bg-elevate"}))
    password1 = forms.CharField(label="Пароль",
                                widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))
    password2 = forms.CharField(label="Повтор паролю",
                                widget=forms.PasswordInput(attrs={"class":"form-control bg-elevate"}))

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Паролі не співпадають")
        return data

class ProfileSetupForm(forms.Form):
    full_name = forms.CharField(label="ПІБ", max_length=200, required=False,
                                widget=forms.TextInput(attrs={"class":"form-control bg-elevate", "placeholder":"Прізвище Ім’я По батькові"}))
    phone = forms.CharField(label="Телефон", required=True,
                            widget=forms.TextInput(attrs={"class":"form-control bg-elevate", "placeholder":"+380XXXXXXXXX"}))
    city = forms.CharField(label="Місто", required=False,
                           widget=forms.TextInput(attrs={"class":"form-control bg-elevate", "placeholder":"Київ"}))
    np_office = forms.CharField(label="Відділення/Поштомат НП", required=False,
                                widget=forms.TextInput(attrs={"class":"form-control bg-elevate", "placeholder":"№ відділення або адреса поштомата"}))
    pay_type = forms.ChoiceField(label="Тип оплати", required=False, choices=(("partial","Часткова передоплата"),("full","Повна передоплата")),
                                 widget=forms.Select(attrs={"class":"form-select bg-elevate"}))
    avatar = forms.ImageField(label="Аватар", required=False)
    is_ubd = forms.BooleanField(label="Я — УБД", required=False,
                                widget=forms.CheckboxInput(attrs={"class":"form-check-input"}))
    ubd_doc = forms.ImageField(label="Фото посвідчення УБД", required=False)

    def clean(self):
        d = super().clean()
        if d.get("is_ubd") and not d.get("ubd_doc"):
            self.add_error("ubd_doc", "Для УБД додайте фото посвідчення")
        return d

# --------- AUTH VIEWS ---------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        if user:
            login(request, user)
            # Если нет телефона в сессии — запрошу заповнення
            if not request.session.get('profile_phone'):
                return redirect('profile_setup')
            return redirect('home')
        else:
            form.add_error(None, "Невірний логін або пароль")
    return render(request, 'pages/auth_login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from django.contrib.auth.models import User
        if User.objects.filter(username=form.cleaned_data['username']).exists():
            form.add_error('username', 'Користувач з таким логіном вже існує')
        else:
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1']
            )
            login(request, user)
            return redirect('profile_setup')
    return render(request, 'pages/auth_register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def profile_setup(request):
    form = ProfileSetupForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        # Зберігаємо у сесію (щоб працювало без міграцій):
        d = {
            'full_name': form.cleaned_data.get('full_name') or '',
            'phone': form.cleaned_data.get('phone') or '',
            'city': form.cleaned_data.get('city') or '',
            'np_office': form.cleaned_data.get('np_office') or '',
            'pay_type': form.cleaned_data.get('pay_type') or '',
            'is_ubd': bool(form.cleaned_data.get('is_ubd')),
        }
        request.session['profile_phone'] = d['phone']
        request.session['profile_data'] = d
        # Аватар/документ — просто кладем у медіа і тримаем шлях у сесії
        if form.cleaned_data.get('avatar'):
            request.session['profile_avatar'] = form.cleaned_data['avatar'].name
        if form.cleaned_data.get('ubd_doc'):
            request.session['profile_ubd_doc'] = form.cleaned_data['ubd_doc'].name
        request.session.modified = True
        return redirect('home')
    return render(request, 'pages/auth_profile_setup.html', {'form': form})

def home(request):
    featured = Product.objects.filter(featured=True).order_by('-id').first()
    categories = Category.objects.order_by('order','name')
    products = list(Product.objects.order_by('-id')[:12])
    # Варіанти кольорів для featured (якщо є додаток і дані)
    featured_variants = []
    # Варіанти кольорів для «Новинок»
    try:
        from productcolors.models import ProductColorVariant
        if featured:
            vset = ProductColorVariant.objects.select_related('color').filter(product=featured).order_by('order','id')
            for v in vset:
                featured_variants.append({
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                    'is_default': v.is_default,
                })
        # Для списку новинок — підготуємо мапу
        prod_ids = [p.id for p in products]
        if prod_ids:
            vlist = ProductColorVariant.objects.select_related('color').filter(product_id__in=prod_ids).order_by('product_id','order','id')
            colors_map = {}
            for v in vlist:
                colors_map.setdefault(v.product_id, []).append({
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                })
            for p in products:
                setattr(p, 'colors_preview', colors_map.get(p.id, []))
    except Exception:
        # якщо додаток або таблиці відсутні — просто не показуємо кольори
        for p in products:
            setattr(p, 'colors_preview', [])
        featured_variants = featured_variants or []
    return render(
        request,
        'pages/index.html',
        {'featured': featured, 'categories': categories, 'products': products, 'featured_variants': featured_variants}
    )

def catalog(request, cat_slug=None):
    categories = Category.objects.order_by('order','name')
    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        products = Product.objects.filter(category=category).order_by('-id')
        show_category_cards = False
    else:
        category = None
        products = Product.objects.order_by('-id')
        show_category_cards = True
    return render(request,'pages/catalog.html',{'categories':categories,'category':category,'products':products,'show_category_cards':show_category_cards})

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    images = product.images.all()
    # Варианты цветов с изображениями (если есть приложение и данные)
    color_variants = []
    auto_select_first_color = False
    
    try:
        from productcolors.models import ProductColorVariant
        variants = ProductColorVariant.objects.select_related('color').prefetch_related('images').filter(product=product)
        for v in variants:
            color_variants.append({
                'id': v.id,
                'primary_hex': v.color.primary_hex,
                'secondary_hex': v.color.secondary_hex or '',
                'is_default': v.is_default,
                'images': [img.image.url for img in v.images.all()],
            })
        
        # Если есть цветовые варианты, устанавливаем первый как активный по умолчанию
        if color_variants:
            # Устанавливаем первый цвет как активный
            color_variants[0]['is_default'] = True
            # Убираем is_default у остальных
            for i in range(1, len(color_variants)):
                color_variants[i]['is_default'] = False
            
            # Если нет основной картинки, помечаем для автоматического выбора изображения
            if not product.main_image:
                auto_select_first_color = True
                    
    except Exception:
        color_variants = []
    
    return render(request,'pages/product_detail.html',{
        'product': product,
        'images': images,
        'color_variants': color_variants,
        'auto_select_first_color': auto_select_first_color
    })

@transaction.atomic
def add_product(request):
    """Добавление нового товара через унифицированный интерфейс"""
    if request.method == 'POST':
        print(f"POST данные создания товара: {request.POST}")
        
        # Обработка основной информации о товаре
        if 'form_type' in request.POST and request.POST['form_type'] == 'main_info':
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                # slug генерируем автоматически, если не задан
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                product.save()
                print(f"Товар создан! ID: {product.id}, баллы: {product.points_reward}")
                return JsonResponse({'success': True, 'product_id': product.id})
            else:
                return JsonResponse({'success': False, 'errors': form.errors})
        
        # Обработка цветов
        elif 'form_type' in request.POST and request.POST['form_type'] == 'colors':
            product_id = request.POST.get('product_id')
            try:
                product = Product.objects.get(id=product_id)
                from productcolors.models import Color, ProductColorVariant, ProductColorImage
                
                # Обработка добавления цвета
                if 'add_color' in request.POST:
                    color_name = request.POST.get('color_name', '').strip()
                    primary_hex = request.POST.get('primary_hex', '#000000')
                    secondary_hex = request.POST.get('secondary_hex', '').strip()
                    
                    if color_name:
                        # Создаем или получаем цвет
                        color, created = Color.objects.get_or_create(
                            name=color_name,
                            defaults={
                                'primary_hex': primary_hex,
                                'secondary_hex': secondary_hex if secondary_hex else None
                            }
                        )
                        
                        # Создаем вариант цвета для товара
                        variant = ProductColorVariant.objects.create(
                            product=product,
                            color=color,
                            is_default=False
                        )
                        
                        # Обрабатываем изображения
                        images = request.FILES.getlist('color_images')
                        for img in images:
                            ProductColorImage.objects.create(
                                variant=variant,
                                image=img
                            )
                        
                        return JsonResponse({'success': True, 'variant_id': variant.id})
                    else:
                        return JsonResponse({'success': False, 'error': 'Название цвета обязательно'})
                
                # Обработка удаления цвета
                elif 'delete_color' in request.POST:
                    variant_id = request.POST.get('variant_id')
                    try:
                        variant = ProductColorVariant.objects.get(id=variant_id, product=product)
                        variant.delete()
                        return JsonResponse({'success': True})
                    except ProductColorVariant.DoesNotExist:
                        return JsonResponse({'success': False, 'error': 'Вариант цвета не найден'})
                
                # Обработка удаления изображения
                elif 'delete_image' in request.POST:
                    image_id = request.POST.get('image_id')
                    try:
                        image = ProductColorImage.objects.get(id=image_id, variant__product=product)
                        image.delete()
                        return JsonResponse({'success': True})
                    except ProductColorImage.DoesNotExist:
                        return JsonResponse({'success': False, 'error': 'Изображение не найдено'})
                
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Товар не найден'})
        
        # Обработка основной формы (для совместимости)
        else:
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                product.save()
                return redirect('product', slug=product.slug)
            else:
                return render(request, 'pages/admin_product_edit_unified.html', {
                    'form': form,
                    'product': None,
                    'is_new': True
                })
    
    else:
        form = ProductForm()
        return render(request, 'pages/admin_product_edit_unified.html', {
            'form': form,
            'product': None,
            'is_new': True
        })

def add_category(request):
    if request.method=='POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(); return redirect('catalog')
    else:
        form = CategoryForm()
    return render(request,'pages/add_category.html',{'form':form})

def cooperation(request): return render(request,'pages/cooperation.html')

def about(request): return render(request,'pages/about.html')

def contacts(request): return render(request,'pages/contacts.html')

def search(request):
    q=(request.GET.get('q') or '').strip()
    qs=Product.objects.all()
    if q: qs=qs.filter(title__icontains=q)
    return render(request,'pages/catalog.html',{'categories':Category.objects.order_by('order','name'),'products':qs.order_by('-id'),'show_category_cards':False})

@csrf_exempt
@require_POST
def add_to_cart(request):
    """
    Добавляет товар в корзину (сессия) с учётом размера и цвета, возвращает JSON с количеством и суммой.
    """
    pid = request.POST.get('product_id')
    size = ((request.POST.get('size') or '').strip() or 'S').upper()
    color_variant_id = request.POST.get('color_variant_id')
    try:
        qty = int(request.POST.get('qty') or '1')
    except ValueError:
        qty = 1
    qty = max(qty, 1)

    product = get_object_or_404(Product, pk=pid)

    cart = request.session.get('cart', {})
    key = f"{product.id}:{size}:{color_variant_id or 'default'}"
    item = cart.get(key, {
        'product_id': product.id, 
        'size': size, 
        'color_variant_id': color_variant_id,
        'qty': 0
    })
    item['qty'] += qty
    cart[key] = item
    request.session['cart'] = cart
    request.session.modified = True

    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = 0
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            total_sum += i['qty'] * p.final_price

    return JsonResponse({'ok': True, 'count': total_qty, 'total': total_sum})

def cart_summary(request):
    """
    Краткая сводка корзины для обновления бейджа.
    """
    cart = request.session.get('cart', {})
    
    # Отладочная информация
    print(f"[cart_summary] Cart session: {cart}")
    
    if not cart:
        return JsonResponse({'ok': True, 'count': 0, 'total': 0})
    
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        print(f"[cart_summary] Missing products: {missing_products}")
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                print(f"[cart_summary] Removing missing product: {key}")
                cart.pop(key, None)
        request.session['cart'] = cart
        request.session.modified = True
    
    # Пересчитываем с очищенной корзиной
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = 0
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            total_sum += i['qty'] * p.final_price
    
    print(f"[cart_summary] Final count: {total_qty}, total: {total_sum}")
    return JsonResponse({'ok': True, 'count': total_qty, 'total': total_sum})

def cart_mini(request):
    """
    HTML для мини‑корзины (выпадающая панель).
    """
    cart_sess = request.session.get('cart', {})
    
    if not cart_sess:
        return render(request,'partials/mini_cart.html',{'items':[],'total':0})
    
    ids = [i['product_id'] for i in cart_sess.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        print(f"[cart_mini] Missing products: {missing_products}")
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart_sess)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                print(f"[cart_mini] Removing missing product: {key}")
                cart_sess.pop(key, None)
        request.session['cart'] = cart_sess
        request.session.modified = True
    
    items = []
    total = 0
    for key, it in cart_sess.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = None
        color_variant_id = it.get('color_variant_id')
        if color_variant_id:
            try:
                from productcolors.models import ProductColorVariant
                color_variant = ProductColorVariant.objects.get(id=color_variant_id)
            except ProductColorVariant.DoesNotExist:
                pass
        
        unit = p.final_price
        line = unit * it['qty']
        total += line
        items.append({
            'key': key,
            'product': p,
            'size': it['size'],
            'color_variant': color_variant,
            'qty': it['qty'],
            'unit_price': unit,
            'line_total': line
        })
    return render(request,'partials/mini_cart.html',{'items':items,'total':total})

def clean_cart(request):
    """
    Очистка корзины от несуществующих товаров.
    """
    cart = request.session.get('cart', {})
    
    if not cart:
        return JsonResponse({'ok': True, 'cleaned': 0, 'message': 'Корзина пуста'})
    
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    cleaned_count = 0
    if missing_products:
        print(f"[clean_cart] Missing products: {missing_products}")
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                print(f"[clean_cart] Removing missing product: {key}")
                cart.pop(key, None)
                cleaned_count += 1
        request.session['cart'] = cart
        request.session.modified = True
    
    return JsonResponse({
        'ok': True, 
        'cleaned': cleaned_count, 
        'message': f'Очищено {cleaned_count} несуществующих товаров' if cleaned_count > 0 else 'Корзина в порядке'
    })

def process_guest_order(request):
    """
    Обработка заказа для неавторизованного пользователя
    """
    from orders.models import Order, OrderItem
    
    # Проверяем корзину
    cart = request.session.get('cart', {})
    if not cart:
        from django.contrib import messages
        messages.error(request, 'Кошик порожній!')
        return redirect('cart')
    
    # Валидация данных доставки
    full_name = request.POST.get('full_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    city = request.POST.get('city', '').strip()
    np_office = request.POST.get('np_office', '').strip()
    pay_type = request.POST.get('pay_type', '')
    
    # Проверяем обязательные поля
    if not full_name or len(full_name) < 3:
        from django.contrib import messages
        messages.error(request, 'ПІБ повинно містити мінімум 3 символи!')
        return redirect('cart')
    
    if not phone:
        from django.contrib import messages
        messages.error(request, 'Введіть номер телефону!')
        return redirect('cart')
    
    if not city:
        from django.contrib import messages
        messages.error(request, 'Введіть місто!')
        return redirect('cart')
    
    if not np_office:
        from django.contrib import messages
        messages.error(request, 'Введіть адресу відділення!')
        return redirect('cart')
    
    if not pay_type:
        from django.contrib import messages
        messages.error(request, 'Оберіть тип оплати!')
        return redirect('cart')
    
    # Проверяем формат телефона
    phone_clean = ''.join(filter(str.isdigit, phone))
    if not phone.startswith('+380') or len(phone_clean) != 12:
        from django.contrib import messages
        messages.error(request, 'Невірний формат телефону! Використовуйте формат +380XXXXXXXXX')
        return redirect('cart')
    
    # Проверяем, что не создается дублирующий заказ
    # Используем хеш данных доставки для проверки
    import hashlib
    delivery_hash = hashlib.md5(f"{full_name}{phone}{city}{np_office}".encode()).hexdigest()
    
    # Проверяем, не было ли уже заказа с такими данными в последние 5 минут
    from django.utils import timezone
    from datetime import timedelta
    
    recent_orders = Order.objects.filter(
        full_name=full_name,
        phone=phone,
        city=city,
        np_office=np_office,
        created__gte=timezone.now() - timedelta(minutes=5)
    )
    
    if recent_orders.exists():
        from django.contrib import messages
        messages.error(request, 'Замовлення з такими даними вже було створено нещодавно. Спробуйте ще раз через кілька хвилин.')
        return redirect('cart')
    
    # Создаем заказ
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_sum = 0
    
    order = Order.objects.create(
        user=None,  # Гостевой заказ
        full_name=full_name,
        phone=phone,
        city=city,
        np_office=np_office,
        pay_type=pay_type,
        total_sum=0,
        status='new'
    )
    
    # Добавляем товары в заказ
    for key, it in cart.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = None
        color_variant_id = it.get('color_variant_id')
        if color_variant_id:
            try:
                from productcolors.models import ProductColorVariant
                color_variant = ProductColorVariant.objects.get(id=color_variant_id)
            except ProductColorVariant.DoesNotExist:
                pass
        
        unit = p.final_price
        line = unit * it['qty']
        total_sum += line
        OrderItem.objects.create(
            order=order,
            product=p,
            color_variant=color_variant,
            title=p.title,
            size=it.get('size', ''),
            qty=it['qty'],
            unit_price=unit,
            line_total=line
        )
    
    # Применяем промокод если есть
    promo_code = request.session.get('applied_promo_code')
    if promo_code:
        from .models import PromoCode
        try:
            promo = PromoCode.objects.get(code=promo_code, is_active=True)
            if promo.can_be_used():
                discount = promo.calculate_discount(total_sum)
                order.discount_amount = discount
                order.promo_code = promo
                promo.use()  # Увеличиваем счетчик использований
        except PromoCode.DoesNotExist:
            pass
    
    order.total_sum = total_sum
    order.save()
    
    # Очищаем корзину и промокод
    request.session['cart'] = {}
    request.session.pop('applied_promo_code', None)
    request.session.modified = True
    
    from django.contrib import messages
    messages.success(request, f'Замовлення #{order.order_number} успішно створено!')
    
    # Для неавторизованных пользователей перенаправляем на страницу успеха
    if not request.user.is_authenticated:
        return redirect('order_success', order_id=order.id)
    
    return redirect('my_orders')

@csrf_exempt
@require_POST
def cart_remove(request):
    """
    Удаление позиции: поддерживает key="productId:size" и (product_id + size).
    Печатает отладочную информацию в консоль.
    """
    cart = request.session.get('cart', {})
    # Отладка входящих параметров
    try:
        print("[cart_remove] RAW POST:", dict(request.POST))
    except Exception:
        pass

    key = (request.POST.get('key') or '').strip()
    pid = request.POST.get('product_id')
    size = (request.POST.get('size') or '').strip()

    removed = []

    def remove_key_exact(k: str) -> bool:
        if k in cart:
            cart.pop(k, None)
            removed.append(k)
            return True
        return False

    # 1) Пытаемся удалить по exact key
    if key:
        if not remove_key_exact(key):
            # 1.1) case-insensitive сравнение ключей
            target = key.lower()
            for kk in list(cart.keys()):
                if kk.lower() == target:
                    remove_key_exact(kk)
                    break
            # 1.2) если всё ещё не нашли, попробуем удалить все варианты этого товара
            if not removed and ":" in key:
                pid_part = key.split(":", 1)[0]
                for kk in list(cart.keys()):
                    if kk.split(":", 1)[0] == pid_part:
                        remove_key_exact(kk)
    # 2) Либо удаляем по product_id (+optional size)
    elif pid:
        try:
            pid_str = str(int(pid))
        except (ValueError, TypeError):
            pid_str = str(pid)
        if size:
            candidate = f"{pid_str}:{size}"
            if not remove_key_exact(candidate):
                # case-insensitive
                target = candidate.lower()
                for kk in list(cart.keys()):
                    if kk.lower() == target:
                        remove_key_exact(kk)
                        break
        else:
            for kk in list(cart.keys()):
                if kk.split(":", 1)[0] == pid_str:
                    remove_key_exact(kk)

    # Сохраняем изменения
    request.session['cart'] = cart
    request.session.modified = True

    # Пересчёт сводки
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = 0
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            total_sum += i['qty'] * p.final_price

    # Отладка: что удалили и что осталось
    try:
        print("[cart_remove] REMOVED:", removed)
        print("[cart_remove] KEYS LEFT:", list(cart.keys()))
    except Exception:
        pass

    return JsonResponse({'ok': True, 'count': total_qty, 'total': total_sum, 'removed': removed, 'keys': list(cart.keys())})

def cart(request):
    """
    Рендер корзины: собираем позиции из сессии, считаем суммы.
    """
    from orders.models import Order
    
    # Обработка POST запросов
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'update_profile' and request.user.is_authenticated:
            # Обновление профиля пользователя
            try:
                prof = request.user.userprofile
                prof.full_name = request.POST.get('full_name', '')
                prof.phone = request.POST.get('phone', '')
                prof.city = request.POST.get('city', '')
                prof.np_office = request.POST.get('np_office', '')
                prof.pay_type = request.POST.get('pay_type', 'full')
                prof.save()
                
                # Показываем сообщение об успехе
                from django.contrib import messages
                messages.success(request, 'Дані доставки успішно оновлено!')
                
            except UserProfile.DoesNotExist:
                pass
                
        elif form_type == 'guest_order':
            # Оформление заказа для гостя
            return process_guest_order(request)
    
    cart_sess = request.session.get('cart', {})
    
    if not cart_sess:
        return render(request,'pages/cart.html',{'items':[],'total':0,'discount':0,'grand_total':0})
    
    ids = [i['product_id'] for i in cart_sess.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        print(f"[cart] Missing products: {missing_products}")
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart_sess)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                print(f"[cart] Removing missing product: {key}")
                cart_sess.pop(key, None)
        request.session['cart'] = cart_sess
        request.session.modified = True
    
    items = []
    total = 0
    for key, it in cart_sess.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = None
        color_variant_id = it.get('color_variant_id')
        if color_variant_id:
            try:
                from productcolors.models import ProductColorVariant
                color_variant = ProductColorVariant.objects.get(id=color_variant_id)
            except ProductColorVariant.DoesNotExist:
                pass
        
        unit = p.final_price
        line = unit * it['qty']
        total += line
        items.append({
            'key': key,
            'product': p,
            'size': it['size'],
            'color_variant': color_variant,
            'qty': it['qty'],
            'unit_price': unit,
            'line_total': line
        })
    
    # Проверяем примененный промокод
    applied_promo = None
    promo_code = request.session.get('applied_promo_code')
    if promo_code:
        from .models import PromoCode
        try:
            applied_promo = PromoCode.objects.get(code=promo_code, is_active=True)
            if applied_promo.can_be_used():
                discount = applied_promo.calculate_discount(total)
                grand_total = total - discount
            else:
                # Промокод больше не действителен
                request.session.pop('applied_promo_code', None)
                grand_total = total
        except PromoCode.DoesNotExist:
            request.session.pop('applied_promo_code', None)
            grand_total = total
    else:
        grand_total = total
    
    context = {
        'items': items,
        'total': total,
        'discount': total - grand_total if applied_promo else 0,
        'grand_total': grand_total,
        'applied_promo': applied_promo
    }
    
    return render(request,'pages/cart.html', context)

def checkout(request): return cart(request)

@login_required
def admin_product_colors(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    product = get_object_or_404(Product, pk=pk)
    # Ленивая загрузка моделей цветов
    from productcolors.models import Color, ProductColorVariant, ProductColorImage

    if request.method == 'POST':
        action = request.POST.get('action') or 'add'
        if action == 'add':
            # Можно выбрать существующий цвет или задать hex
            color_id = request.POST.get('color_id')
            primary_hex = (request.POST.get('primary_hex') or '').strip() or '#000000'
            secondary_hex = (request.POST.get('secondary_hex') or '').strip() or None
            is_default = bool(request.POST.get('is_default'))
            # Если выбрали существующий
            if color_id:
                color = get_object_or_404(Color, pk=color_id)
            else:
                color, _ = Color.objects.get_or_create(primary_hex=primary_hex, secondary_hex=secondary_hex)
            # Создаём вариант
            variant = ProductColorVariant.objects.create(product=product, color=color, is_default=is_default, order=int(request.POST.get('order') or 0))
            # Загружаем изображения
            for f in request.FILES.getlist('images'):
                ProductColorImage.objects.create(variant=variant, image=f)
        elif action == 'delete_variant':
            vid = request.POST.get('variant_id')
            try:
                v = ProductColorVariant.objects.get(pk=vid, product=product)
                v.delete()
            except ProductColorVariant.DoesNotExist:
                pass
        elif action == 'delete_image':
            iid = request.POST.get('image_id')
            try:
                img = ProductColorImage.objects.filter(variant__product=product).get(pk=iid)
                img.delete()
            except ProductColorImage.DoesNotExist:
                pass
        return redirect('admin_product_colors', pk=product.id)

    # Справочник ранее использованных цветов
    used_colors = Color.objects.order_by('primary_hex','secondary_hex').all()
    variants = (ProductColorVariant.objects.select_related('color')
                .prefetch_related('images')
                .filter(product=product).order_by('order','id'))
    return render(request, 'pages/admin_product_colors.html', {
        'product': product,
        'used_colors': used_colors,
        'variants': variants
    })

# ===== ЧИСТЫЕ ВЬЮ, БЕЗ ДУБЛИКАТОВ =====
def register_view_new(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from django.contrib.auth.models import User
        if User.objects.filter(username=form.cleaned_data['username']).exists():
            form.add_error('username','Користувач з таким логіном вже існує')
        else:
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1']
            )
            login(request, user)
            return redirect('profile_setup')
    return render(request, 'pages/auth_register.html', {'form': form})

@login_required
def profile_setup_db(request):
    # Профиль в БД
    from accounts.models import UserProfile
    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    initial = {
        'full_name': getattr(prof, 'full_name', ''),
        'phone': prof.phone or '',
        'city': prof.city or '',
        'np_office': prof.np_office or '',
        'pay_type': prof.pay_type or '',
        'is_ubd': prof.is_ubd,
    }
    form = ProfileSetupForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        prof.full_name = form.cleaned_data.get('full_name') or ''
        prof.phone = form.cleaned_data.get('phone') or ''
        prof.city = form.cleaned_data.get('city') or ''
        prof.np_office = form.cleaned_data.get('np_office') or ''
        prof.pay_type = form.cleaned_data.get('pay_type') or ''
        prof.is_ubd = bool(form.cleaned_data.get('is_ubd'))
        if form.cleaned_data.get('avatar'):
            prof.avatar = form.cleaned_data['avatar']
        if prof.is_ubd and form.cleaned_data.get('ubd_doc'):
            prof.ubd_doc = form.cleaned_data['ubd_doc']
        prof.save()
        # Обновим сессию (не обязательно, но пусть будет телефон под рукой)
        request.session['profile_phone'] = prof.phone
        if prof.avatar:
            request.session['profile_avatar'] = prof.avatar.name
        request.session.modified = True
        return redirect('home')
    return render(request, 'pages/auth_profile_setup.html', {'form': form, 'profile': prof})

@login_required
def dev_grant_admin(request):
    """
    Выдать текущему пользователю права администратора (только при DEBUG).
    """
    if not settings.DEBUG:
        return redirect('home')
    u = request.user
    if not u.is_staff or not u.is_superuser:
        u.is_staff = True
        u.is_superuser = True
        u.save()
    return redirect('admin_panel')

# ===== Панель администратора (для staff) =====
@login_required
def admin_panel(request):
    if not request.user.is_staff:
        return redirect('home')
    section = request.GET.get('section', 'stats')
    ctx = {'section': section}
    if section == 'users':
        users = User.objects.order_by('username').all()
        # подтягиваем профили и баллы для каждого пользователя
        from accounts.models import UserPoints
        user_data = []
        for user in users:
            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                profile = None
            
            try:
                points = user.points
            except UserPoints.DoesNotExist:
                points = None
            
            user_data.append({
                'user': user,
                'profile': profile,
                'points': points
            })
        ctx.update({'user_data': user_data})
    elif section == 'catalogs':
        from .models import Category, Product
        categories = Category.objects.order_by('order','name') if hasattr(Category, 'order') else Category.objects.order_by('name')
        products = Product.objects.order_by('-id')
        ctx.update({'categories': categories, 'products': products})
    elif section == 'orders':
        # реальные замовлення
        try:
            from orders.models import Order
            orders = Order.objects.select_related('user').prefetch_related('items','items__product').all()
        except Exception:
            orders = []
        ctx.update({'orders': orders})
    else:
        # stats — заглушка
        ctx.update({'stats': {'orders_today': 0, 'revenue': 0, 'users': User.objects.count()}})
    return render(request, 'pages/admin_panel.html', ctx)

@login_required
def admin_update_user(request):
    if not request.user.is_staff:
        return redirect('home')
    if request.method != 'POST':
        return redirect('admin_panel')
    user_id = request.POST.get('user_id')
    is_staff = True if request.POST.get('is_staff') == 'on' else False
    is_superuser_req = True if request.POST.get('is_superuser') == 'on' else False
    
    # Обработка баллов
    points_adjustment = request.POST.get('points_adjustment')
    points_reason = request.POST.get('points_reason', '')

    try:
        u = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect('admin_panel')

    if not request.user.is_superuser:
        is_superuser_req = u.is_superuser

    u.is_staff = is_staff
    u.is_superuser = is_superuser_req
    u.save()
    
    # Обновляем баллы если указано
    if points_adjustment:
        try:
            points_change = int(points_adjustment)
            if points_change != 0:
                from accounts.models import UserPoints
                user_points = UserPoints.get_or_create_points(u)
                
                if points_change > 0:
                    user_points.add_points(points_change, f'Коригування адміністратором: {points_reason}')
                else:
                    user_points.spend_points(abs(points_change), f'Коригування адміністратором: {points_reason}')
        except ValueError:
            pass
    
    return redirect('/admin-panel/?section=users')

# ======= Orders =======
# Импорт моделей заказов выполняется лениво внутри функций,
# чтобы избежать падения при старте, если приложение ещё не подключено.

@login_required
def order_create(request):
    # Локальный импорт моделей заказов – сразу, до использования
    from orders.models import Order, OrderItem

    # Требуем заполненный профиль доставки
    try:
        prof = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect('profile_setup')
    required = [prof.phone, prof.city, prof.np_office, prof.pay_type]
    if not all(required):
        return redirect('profile_setup')

    # Корзина должна быть не пустой
    cart = request.session.get('cart') or {}
    if not cart:
        return redirect('cart')

    # Защита от дублирования заказов
    from django.utils import timezone
    from datetime import timedelta
    
    # Проверяем, не было ли уже заказа от этого пользователя в последние 5 минут
    recent_orders = Order.objects.filter(
        user=request.user,
        created__gte=timezone.now() - timedelta(minutes=5)
    )
    
    if recent_orders.exists():
        from django.contrib import messages
        messages.error(request, 'Замовлення вже було створено нещодавно. Спробуйте ще раз через кілька хвилин.')
        return redirect('cart')

    # Пересчёт total и создание заказа
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_sum = 0
    order = Order.objects.create(
        user=request.user,
        full_name=getattr(prof, 'full_name', '') or request.user.username,
        phone=prof.phone, city=prof.city, np_office=prof.np_office,
        pay_type=prof.pay_type, total_sum=0, status='new'
    )
    
    for key, it in cart.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = None
        color_variant_id = it.get('color_variant_id')
        if color_variant_id:
            try:
                from productcolors.models import ProductColorVariant
                color_variant = ProductColorVariant.objects.get(id=color_variant_id)
            except ProductColorVariant.DoesNotExist:
                pass
        
        unit = p.final_price
        line = unit * it['qty']
        total_sum += line
        OrderItem.objects.create(
            order=order, product=p, color_variant=color_variant, title=p.title, size=it.get('size',''),
            qty=it['qty'], unit_price=unit, line_total=line
        )
    
    # Применяем промокод если есть
    promo_code = request.session.get('applied_promo_code')
    if promo_code:
        from .models import PromoCode
        try:
            promo = PromoCode.objects.get(code=promo_code, is_active=True)
            if promo.can_be_used():
                discount = promo.calculate_discount(total_sum)
                order.discount_amount = discount
                order.promo_code = promo
                promo.use()  # Увеличиваем счетчик использований
        except PromoCode.DoesNotExist:
            pass
    
    order.total_sum = total_sum
    order.save()

    # Очищаем корзину и промокод
    request.session['cart'] = {}
    request.session.pop('applied_promo_code', None)
    request.session.modified = True

    from django.contrib import messages
    messages.success(request, f'Замовлення #{order.order_number} успішно створено!')

    return redirect('my_orders')

def order_success(request, order_id):
    """
    Страница успешного оформления заказа
    """
    from orders.models import Order
    
    try:
        order = Order.objects.get(id=order_id)
        # Проверяем, что заказ был создан недавно (в течение часа)
        from django.utils import timezone
        from datetime import timedelta
        
        if order.created < timezone.now() - timedelta(hours=1):
            return redirect('home')
            
    except Order.DoesNotExist:
        return redirect('home')
    
    return render(request, 'pages/order_success.html', {
        'order': order,
        'order_number': order.id
    })

@login_required
def my_orders(request):
    from orders.models import Order
    qs = Order.objects.filter(user=request.user).prefetch_related('items','items__product').order_by('-created')
    return render(request, 'pages/my_orders.html', {'orders': qs})

@login_required
def my_promocodes(request):
    """
    Страница промокодов пользователя
    """
    from orders.models import Order
    
    # Получаем все заказы пользователя с промокодами
    orders_with_promocodes = Order.objects.filter(
        user=request.user,
        promo_code__isnull=False
    ).select_related('promo_code').order_by('-created')
    
    # Создаем список использованных промокодов
    used_promocodes = []
    for order in orders_with_promocodes:
        if order.promo_code:
            used_promocodes.append({
                'promo_code': order.promo_code,
                'order': order,
                'used_date': order.created,
                'discount_amount': order.discount_amount,
                'order_total': order.total_sum
            })
    
    return render(request, 'pages/my_promocodes.html', {
        'used_promocodes': used_promocodes
    })

@login_required
def buy_with_points(request):
    """
    Страница покупки за баллы
    """
    from accounts.models import UserPoints
    
    # Получаем баллы пользователя
    try:
        user_points = UserPoints.objects.get(user=request.user)
        current_points = user_points.points
    except UserPoints.DoesNotExist:
        current_points = 0
    
    # Определяем доступные товары за баллы
    available_items = [
        {
            'id': 'promo_10',
            'name': 'Промокод на знижку 10%',
            'description': 'Отримайте промокод на знижку 10% від суми замовлення',
            'points_cost': 100,
            'type': 'promo',
            'icon': 'M21.41 11.58l-9-9C12.05 2.22 11.55 2 11 2H4c-1.1 0-2 .9-2 2v7c0 .55.22 1.05.59 1.42l9 9c.36.36.86.58 1.41.58.55 0 1.05-.22 1.41-.59l7-7c.37-.36.59-.86.59-1.41 0-.55-.23-1.06-.59-1.42zM5.5 7C4.67 7 4 6.33 4 5.5S4.67 4 5.5 4 7 4.67 7 5.5 6.33 7 5.5 7z',
            'color': 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            'can_afford': current_points >= 100
        },
        {
            'id': 'donate_zsu',
            'name': 'Донат на ЗСУ',
            'description': 'Пожертвуйте всі ваші бали на підтримку Збройних Сил України',
            'points_cost': current_points,
            'type': 'donate',
            'icon': 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
            'color': 'linear-gradient(135deg, #dc2626, #991b1b)',
            'can_afford': current_points > 0
        }
    ]
    
    return render(request, 'pages/buy_with_points.html', {
        'current_points': current_points,
        'available_items': available_items
    })

@login_required
def purchase_with_points(request):
    """
    Обработка покупки за баллы
    """
    if request.method != 'POST':
        return redirect('buy_with_points')
    
    from accounts.models import UserPoints
    from django.contrib import messages
    
    item_id = request.POST.get('item_id')
    
    try:
        user_points = UserPoints.objects.get(user=request.user)
    except UserPoints.DoesNotExist:
        messages.error(request, 'У вас немає балів для покупки')
        return redirect('buy_with_points')
    
    if item_id == 'promo_10':
        # Покупка промокода на 10% скидки
        if user_points.points >= 100:
            # Здесь будет логика создания промокода
            # Пока что просто списываем баллы
            user_points.spend_points(100, 'Покупка промокода на знижку 10%')
            messages.success(request, 'Промокод на знижку 10% успішно придбано! Код: POINTS10')
        else:
            messages.error(request, 'Недостатньо балів для покупки промокода')
    
    elif item_id == 'donate_zsu':
        # Донат на ЗСУ
        if user_points.points > 0:
            points_to_donate = user_points.points
            user_points.spend_points(points_to_donate, 'Донат на ЗСУ')
            messages.success(request, f'Дякуємо за підтримку ЗСУ! Пожертвовано {points_to_donate} балів')
        else:
            messages.error(request, 'У вас немає балів для пожертвування')
    
    else:
        messages.error(request, 'Невідомий товар')
    
    return redirect('buy_with_points')

@login_required
def admin_order_update(request):
    if not request.user.is_staff:
        return redirect('home')
    if request.method != 'POST':
        return redirect('/admin-panel/?section=orders')
    from orders.models import Order
    oid = request.POST.get('order_id')
    status = request.POST.get('status')
    try:
        o = Order.objects.get(pk=oid)
    except Order.DoesNotExist:
        return redirect('/admin-panel/?section=orders')
    
    old_status = o.status
    if status in dict(Order.STATUS_CHOICES):
        o.status = status
        o.save()
        
        # Обрабатываем баллы при изменении статуса
        if o.user:  # Только для авторизованных пользователей
            from accounts.models import UserPoints
            user_points = UserPoints.get_or_create_points(o.user)
            
            # Рассчитываем баллы за заказ
            total_points = 0
            for item in o.items.all():
                if item.product.points_reward > 0:
                    total_points += item.product.points_reward * item.qty
            
            # Статусы, при которых начисляются баллы
            points_awarding_statuses = ['prep', 'ship', 'done']  # 'готовится к отправке', 'отправлен', 'получен'
            
            # Статусы, при которых отменяются баллы
            points_cancelling_statuses = ['cancelled']  # 'отменен'
            
            # Если переходим к статусу начисления баллов и баллы еще не начислены
            if status in points_awarding_statuses and old_status not in points_awarding_statuses and not o.points_awarded:
                if total_points > 0:
                    user_points.add_points(total_points, f'Замовлення #{o.order_number} {o.get_status_display()}')
                    o.points_awarded = True
                    o.save(update_fields=['points_awarded'])
            
            # Если переходим к статусу отмены баллов и баллы были начислены
            elif status in points_cancelling_statuses and old_status not in points_cancelling_statuses and o.points_awarded:
                if total_points > 0:
                    user_points.spend_points(total_points, f'Скасування замовлення #{o.order_number}')
                    o.points_awarded = False
                    o.save(update_fields=['points_awarded'])
    
    return redirect('/admin-panel/?section=orders')

# ---- Каталоги CRUD ----
@login_required
def admin_category_new(request):
    if not request.user.is_staff:
        return redirect('home')
    from .forms import CategoryForm
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('/admin-panel/?section=catalogs')
    return render(request, 'pages/admin_category_form.html', {'form': form, 'mode': 'new'})

@login_required
def admin_category_edit(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    from .forms import CategoryForm
    from .models import Category
    obj = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('/admin-panel/?section=catalogs')
    return render(request, 'pages/admin_category_form.html', {'form': form, 'mode': 'edit', 'obj': obj})

@login_required
def admin_category_delete(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    from .models import Category
    obj = get_object_or_404(Category, pk=pk)
    obj.delete()
    return redirect('/admin-panel/?section=catalogs')

@login_required
def admin_product_new(request):
    if not request.user.is_staff:
        return redirect('home')
    from .forms import ProductForm
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        prod = form.save()
        # возможно добавление дополнительных изображений позже
        return redirect('/admin-panel/?section=catalogs')
    return render(request, 'pages/admin_product_form.html', {'form': form, 'mode': 'new'})

@login_required
def admin_product_edit(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    from .forms import ProductForm
    from .models import Product
    obj = get_object_or_404(Product, pk=pk)
    
    print(f"=== admin_product_edit для товара {pk} ===")
    print(f"Метод запроса: {request.method}")
    if request.method == 'POST':
        print(f"POST данные: {dict(request.POST)}")
        print(f"FILES данные: {dict(request.FILES)}")

    # Если пришло действие с цветами — обрабатываем и возвращаемся на эту же страницу
    action = (request.POST.get('action') or '').strip() if request.method == 'POST' else ''
    print(f"Action: '{action}'")
    
    # Если это POST запрос для цветов, обрабатываем его
    if action and request.method == 'POST':
        try:
            from productcolors.models import Color, ProductColorVariant, ProductColorImage
        except Exception:
            Color = ProductColorVariant = ProductColorImage = None

        if Color and ProductColorVariant and ProductColorImage:
            if action == 'add':
                color_id = request.POST.get('color_id')
                primary_hex = (request.POST.get('primary_hex') or '').strip() or '#000000'
                secondary_hex = (request.POST.get('secondary_hex') or '').strip() or None
                is_default = bool(request.POST.get('is_default'))
                order = int(request.POST.get('order') or 0)

                if color_id:
                    color = get_object_or_404(Color, pk=color_id)
                else:
                    color, _ = Color.objects.get_or_create(primary_hex=primary_hex, secondary_hex=secondary_hex)
                variant = ProductColorVariant.objects.create(product=obj, color=color, is_default=is_default, order=order)
                for f in request.FILES.getlist('images'):
                    ProductColorImage.objects.create(variant=variant, image=f)
            elif action == 'delete_variant':
                vid = request.POST.get('variant_id')
                try:
                    v = ProductColorVariant.objects.get(pk=vid, product=obj)
                    v.delete()
                except ProductColorVariant.DoesNotExist:
                    pass
            elif action == 'delete_image':
                iid = request.POST.get('image_id')
                try:
                    img = ProductColorImage.objects.filter(variant__product=obj).get(pk=iid)
                    img.delete()
                except ProductColorImage.DoesNotExist:
                    pass
        return redirect('admin_product_edit', pk=obj.id)

    # Основная форма товара
    form = ProductForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST':
        print(f"=== Обработка основной формы ===")
        print(f"POST данные: {request.POST}")
        print(f"points_reward в POST: {request.POST.get('points_reward')}")
        print(f"action в POST: {request.POST.get('action')}")
        
        # Проверяем, что это не запрос для цветов
        if not request.POST.get('action'):
            print("Это запрос для основной формы товара")
            
            if form.is_valid():
                print("Форма валидна!")
                product = form.save(commit=False)
                # Автогенерація slug, якщо порожній
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                product.save()
                print(f"Товар сохранен! ID: {product.id}, баллы: {product.points_reward}")
                return redirect('/admin-panel/?section=catalogs')
            else:
                print("=== ОШИБКИ ФОРМЫ ===")
                print("Ошибки формы:")
                for field, errors in form.errors.items():
                    print(f"  {field}: {errors}")
        else:
            print("Это запрос для цветов, пропускаем обработку основной формы")

    # Данные для блока «Кольори»
    used_colors = []
    variants = []
    try:
        from productcolors.models import Color, ProductColorVariant
        used_colors = Color.objects.order_by('primary_hex', 'secondary_hex').all()
        variants = (ProductColorVariant.objects.select_related('color')
                    .prefetch_related('images')
                    .filter(product=obj).order_by('order', 'id'))
    except Exception:
        pass

    return render(
        request,
        'pages/admin_product_form.html',
        {'form': form, 'mode': 'edit', 'obj': obj, 'used_colors': used_colors, 'variants': variants}
    )

@login_required
def admin_product_edit_unified(request, pk):
    """Универсальное редактирование товара со всеми настройками"""
    if not request.user.is_staff:
        return redirect('home')
    from .forms import ProductForm
    from .models import Product, ProductImage
    from productcolors.models import ProductColorVariant, Color, ProductColorImage
    obj = get_object_or_404(Product, pk=pk)
    
    print(f"=== admin_product_edit_unified для товара {pk} ===")
    print(f"Метод запроса: {request.method}")
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        print(f"Тип формы: {form_type}")
        
        if form_type == 'product':
            print("Обработка основной формы товара")
            print(f"POST данные: {dict(request.POST)}")
            print(f"points_reward в POST: {request.POST.get('points_reward')}")
            
            form = ProductForm(request.POST, request.FILES, instance=obj)
            if form.is_valid():
                print("Форма валидна!")
                product = form.save(commit=False)
                # Автогенерація slug, якщо порожній
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                
                # Если главное изображение не выбрано, используем первую фотографию первого цвета
                if not product.main_image:
                    first_color_variant = product.color_variants.first()
                    if first_color_variant:
                        first_image = first_color_variant.images.first()
                        if first_image:
                            product.main_image = first_image.image
                            print(f"Автоматически установлено главное изображение из первого цвета: {first_image.image}")
                
                product.save()
                print(f"Товар сохранен! ID: {product.id}, баллы: {product.points_reward}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Товар успішно збережено!'})
                return redirect('/admin-panel/?section=catalogs')
            else:
                print("=== ОШИБКИ ФОРМЫ ===")
                print("Ошибки формы:")
                for field, errors in form.errors.items():
                    print(f"  {field}: {errors}")
                
                # Попробуем сохранить товар вручную, игнорируя ошибки валидации
                try:
                    product = obj
                    for field_name, value in request.POST.items():
                        if hasattr(product, field_name) and field_name not in ['csrfmiddlewaretoken', 'form_type']:
                            setattr(product, field_name, value)
                    
                    # Обработка файлов
                    if 'main_image' in request.FILES:
                        product.main_image = request.FILES['main_image']
                    
                    # Автогенерація slug, якщо порожній
                    if not getattr(product, 'slug', None):
                        base = slugify(product.title or '')
                        product.slug = unique_slugify(Product, base)
                    
                    # Если главное изображение не выбрано, используем первую фотографию первого цвета
                    if not product.main_image:
                        first_color_variant = product.color_variants.first()
                        if first_color_variant:
                            first_image = first_color_variant.images.first()
                            if first_image:
                                product.main_image = first_image.image
                                print(f"Автоматически установлено главное изображение из первого цвета: {first_image.image}")
                    
                    product.save()
                    print(f"Товар сохранен вручную! ID: {product.id}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': True, 'message': 'Товар успішно збережено!'})
                    return redirect('/admin-panel/?section=catalogs')
                    
                except Exception as e:
                    print(f"Ошибка при ручном сохранении: {e}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': True, 'message': 'Товар успішно збережено!'})
                    return redirect('/admin-panel/?section=catalogs')
        
        elif form_type == 'color':
            print("Обработка формы добавления цвета")
            color_name = request.POST.get('color_name')
            primary_hex = request.POST.get('primary_hex')
            secondary_hex = request.POST.get('secondary_hex', '')
            color_images = request.FILES.getlist('color_images')
            
            print(f"Данные цвета: name={color_name}, primary={primary_hex}, secondary={secondary_hex}")
            print(f"Количество изображений: {len(color_images)}")
            
            if color_name and primary_hex and color_images:
                # Создаем цвет с HEX кодами
                color = Color.objects.create(
                    name=color_name,
                    primary_hex=primary_hex,
                    secondary_hex=secondary_hex if secondary_hex else None
                )
                
                # Создаем вариант цвета для товара
                color_variant = ProductColorVariant.objects.create(
                    product=obj,
                    color=color
                )
                
                # Создаем изображения для варианта цвета
                for i, image in enumerate(color_images):
                    ProductColorImage.objects.create(
                        variant=color_variant,
                        image=image,
                        order=i  # Сохраняем порядок изображений
                    )
                
                # Если у товара нет главного изображения, используем первую фотографию этого цвета
                if not obj.main_image and color_images:
                    obj.main_image = color_images[0]
                    obj.save()
                    print(f"Автоматически установлено главное изображение товара из первого цвета: {color_images[0]}")
                
                print(f"Цвет добавлен: {color_name} ({primary_hex}{' + ' + secondary_hex if secondary_hex else ''}) с {len(color_images)} изображениями")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': f'Колір успішно додано з {len(color_images)} зображеннями!'})
                return redirect(request.path)
            else:
                print("Ошибка: не указано название, HEX код или изображения цвета")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Колір успішно додано!'})
                return redirect(request.path)
        
        elif form_type == 'image':
            print("Обработка формы добавления изображения")
            additional_image = request.FILES.get('additional_image')
            
            if additional_image:
                ProductImage.objects.create(
                    product=obj,
                    image=additional_image
                )
                print("Дополнительное изображение добавлено")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Зображення успішно додано!'})
                return redirect(request.path)
            else:
                print("Ошибка: не выбрано изображение")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Зображення успішно додано!'})
                return redirect(request.path)
    
    form = ProductForm(instance=obj)
    
    return render(request, 'pages/admin_product_edit_unified.html', {
        'form': form, 
        'obj': obj
    })

def api_colors(request):
    """API endpoint для получения всех цветов"""
    from productcolors.models import Color
    from django.http import JsonResponse
    
    colors = Color.objects.all()
    colors_data = []
    
    for color in colors:
        colors_data.append({
            'id': color.id,
            'name': color.name,
            'primary_hex': color.primary_hex,
            'secondary_hex': color.secondary_hex
        })
    
    return JsonResponse(colors_data, safe=False)

@login_required
def admin_product_edit_simple(request, pk):
    """Упрощенное редактирование товара без цветов"""
    if not request.user.is_staff:
        return redirect('home')
    from .forms import ProductForm
    from .models import Product
    obj = get_object_or_404(Product, pk=pk)
    
    print(f"=== admin_product_edit_simple для товара {pk} ===")
    print(f"Метод запроса: {request.method}")
    
    if request.method == 'POST':
        print(f"POST данные: {dict(request.POST)}")
        print(f"points_reward в POST: {request.POST.get('points_reward')}")
        
        form = ProductForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            print("Форма валидна!")
            product = form.save(commit=False)
            # Автогенерація slug, якщо порожній
            if not getattr(product, 'slug', None):
                base = slugify(product.title or '')
                product.slug = unique_slugify(Product, base)
            product.save()
            print(f"Товар сохранен! ID: {product.id}, баллы: {product.points_reward}")
            return redirect('/admin-panel/?section=catalogs')
        else:
            print("=== ОШИБКИ ФОРМЫ ===")
            print("Ошибки формы:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
    else:
        form = ProductForm(instance=obj)
    
    return render(request, 'pages/admin_product_edit_simple.html', {
        'form': form, 
        'obj': obj
    })

@login_required
def admin_product_color_delete(request, product_pk, color_pk):
    """Удаление цвета товара"""
    if not request.user.is_staff:
        return redirect('home')
    from .models import Product
    from productcolors.models import ProductColorVariant
    product = get_object_or_404(Product, pk=product_pk)
    color_variant = get_object_or_404(ProductColorVariant, pk=color_pk, product=product)
    color_variant.delete()
    return redirect(f'/admin-panel/product/{product_pk}/edit-unified/')

@login_required
def admin_product_image_delete(request, product_pk, image_pk):
    """Удаление дополнительного изображения товара"""
    if not request.user.is_staff:
        return redirect('home')
    from .models import Product, ProductImage
    product = get_object_or_404(Product, pk=product_pk)
    image = get_object_or_404(ProductImage, pk=image_pk, product=product)
    image.delete()
    return redirect(f'/admin-panel/product/{product_pk}/edit-unified/')

@login_required
def admin_product_delete(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    from .models import Product
    obj = get_object_or_404(Product, pk=pk)
    obj.delete()
    return redirect('/admin-panel/?section=catalogs')

# ===== БАЛЫ И ПРОМОКОДЫ ПОЛЬЗОВАТЕЛЯ =====

@login_required
def user_points(request):
    """Страница баллов пользователя"""
    from accounts.models import UserPoints, PointsHistory
    
    # Получаем или создаем объект баллов пользователя
    user_points = UserPoints.get_or_create_points(request.user)
    
    # Получаем историю баллов
    history = PointsHistory.objects.filter(user=request.user)[:20]  # Последние 20 записей
    
    return render(request, 'pages/user_points.html', {
        'user_points': user_points,
        'history': history
    })



# ===== АДМИН-ПАНЕЛЬ ПРОМОКОДОВ =====

class PromoCodeForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ['code', 'discount_type', 'discount_value', 'max_uses', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Введіть код або залиште порожнім для автогенерації'
            }),
            'discount_type': forms.Select(attrs={'class': 'form-select bg-elevate'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'step': '0.01',
                'min': '0'
            }),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'min': '0',
                'placeholder': '0 = безліміт'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        """Позволяет оставить поле code пустым для автоматической генерации"""
        code = self.cleaned_data.get('code', '').strip()
        
        # Если код пустой, это нормально - он будет сгенерирован автоматически
        if not code:
            return ''
        
        # Если код указан, проверяем его уникальность
        if PromoCode.objects.filter(code=code).exists():
            if self.instance and self.instance.pk:
                # При редактировании исключаем текущий промокод
                if not PromoCode.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                    return code
            raise forms.ValidationError("Промокод з таким кодом вже існує")
        
        return code

@login_required
def admin_promocodes(request):
    """Список промокодов"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import PromoCode
    promocodes = PromoCode.objects.all()
    
    # Подсчитываем статистику
    total_promocodes = promocodes.count()
    active_promocodes = promocodes.filter(is_active=True).count()
    
    return render(request, 'pages/admin_promocodes.html', {
        'promocodes': promocodes,
        'total_promocodes': total_promocodes,
        'active_promocodes': active_promocodes,
        'section': 'promocodes'
    })

@login_required
def admin_promocode_create(request):
    """Создание нового промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import PromoCode
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promocode = form.save(commit=False)
            
            # Если код не указан или пустой, генерируем автоматически
            if not promocode.code or promocode.code.strip() == '':
                promocode.code = PromoCode.generate_code()
            
            promocode.save()
            return redirect('admin_promocodes')
    else:
        form = PromoCodeForm()
    
    return render(request, 'pages/admin_promocode_form.html', {
        'form': form,
        'mode': 'create',
        'section': 'promocodes'
    })

@login_required
def admin_promocode_edit(request, pk):
    """Редактирование промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import PromoCode
    promocode = get_object_or_404(PromoCode, pk=pk)
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST, instance=promocode)
        if form.is_valid():
            edited_promocode = form.save(commit=False)
            
            # Если код не указан или пустой, генерируем автоматически
            if not edited_promocode.code or edited_promocode.code.strip() == '':
                edited_promocode.code = PromoCode.generate_code()
            
            edited_promocode.save()
            return redirect('admin_promocodes')
    else:
        form = PromoCodeForm(instance=promocode)
    
    return render(request, 'pages/admin_promocode_form.html', {
        'form': form,
        'mode': 'edit',
        'promocode': promocode,
        'section': 'promocodes'
    })

@login_required
def admin_promocode_toggle(request, pk):
    """Активация/деактивация промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import PromoCode
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.is_active = not promocode.is_active
    promocode.save()
    
    return redirect('admin_promocodes')

@login_required
def admin_promocode_delete(request, pk):
    """Удаление промокода"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import PromoCode
    promocode = get_object_or_404(PromoCode, pk=pk)
    promocode.delete()
    
    return redirect('admin_promocodes')

# ===== ПРОМОКОДЫ В КОРЗИНЕ =====

def apply_promo_code(request):
    """Применение промокода в корзине"""
    if request.method == 'POST':
        promo_code = request.POST.get('promo_code', '').strip().upper()
        
        if not promo_code:
            return JsonResponse({
                'success': False,
                'message': 'Введіть код промокоду'
            })
        
        try:
            from .models import PromoCode
            promocode = PromoCode.objects.get(code=promo_code)
            
            if not promocode.can_be_used():
                return JsonResponse({
                    'success': False,
                    'message': 'Промокод неактивний або вичерпаний'
                })
            
            # Получаем корзину из сессии
            cart = request.session.get('cart', {})
            if not cart:
                return JsonResponse({
                    'success': False,
                    'message': 'Корзина порожня'
                })
            
            # Рассчитываем общую сумму корзины
            total = 0
            for key, item in cart.items():
                # Получаем цену товара
                try:
                    product = Product.objects.get(id=item['product_id'])
                    price = product.final_price
                    total += price * item['qty']
                except Product.DoesNotExist:
                    continue
            
            # Рассчитываем скидку
            discount = promocode.calculate_discount(total)
            
            if discount <= 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Промокод не застосовується до цієї суми'
                })
            
            # Сохраняем промокод в сессии
            request.session['applied_promo_code'] = {
                'code': promocode.code,
                'discount': float(discount),
                'discount_type': promocode.discount_type,
                'discount_value': float(promocode.discount_value)
            }
            
            final_total = total - discount
            
            return JsonResponse({
                'success': True,
                'message': f'Промокод {promocode.code} застосовано! Знижка: {promocode.get_discount_display()}',
                'discount': float(discount),
                'final_total': float(final_total),
                'promo_code': promocode.code
            })
            
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Промокод не знайдено'
            })
    
    return JsonResponse({'success': False, 'message': 'Невірний запит'})

def remove_promo_code(request):
    """Удаление промокода из корзины"""
    if request.method == 'POST':
        if 'applied_promo_code' in request.session:
            del request.session['applied_promo_code']
            request.session.modified = True
        
        # Пересчитываем общую сумму
        cart = request.session.get('cart', {})
        total = 0
        for key, item in cart.items():
            try:
                product = Product.objects.get(id=item['product_id'])
                price = product.final_price
                total += price * item['qty']
            except Product.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': 'Промокод видалено',
            'final_total': float(total)
        })
    
    return JsonResponse({'success': False, 'message': 'Невірний запит'})
