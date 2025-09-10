from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.urls import reverse
from functools import wraps

def cache_page_for_anon(timeout):
    """Кэширует только для анонимных пользователей (избегаем проблем с персональными данными)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            return cache_page(timeout)(view_func)(request, *args, **kwargs)
        return _wrapped_view
    return decorator
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Product, Category, ProductImage, PromoCode, PrintProposal
from .forms import ProductForm, CategoryForm, PrintProposalForm
from accounts.models import UserProfile, FavoriteProduct
from django import forms
from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify
from django.core.cache import cache

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
                                widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"Прізвище Ім'я По батькові"}))
    phone = forms.CharField(label="Телефон", required=True,
                            widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"+380XXXXXXXXX"}))
    email = forms.EmailField(label="Email", required=False,
                            widget=forms.EmailInput(attrs={"class":"form-control bg-elevate","placeholder":"your@email.com"}))
    telegram = forms.CharField(label="Telegram", required=False,
                              widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"@username"}))
    instagram = forms.CharField(label="Instagram", required=False,
                               widget=forms.TextInput(attrs={"class":"form-control bg-elevate","placeholder":"@username"}))
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
# Старая функция login_view удалена - используется новая ниже

# Старая функция register_view удалена - используется новая ниже

# Старая функция logout_view удалена - используется новая ниже


from django import forms

# --------- AUTH FORMS (минимум, чтобы не плодить новый файл) ---------
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



# --------- AUTH VIEWS ---------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile_setup')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
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
            
            # если профиль пустой по телефону — просим заповнення
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
    return render(request, 'pages/auth_login.html', {'form': form, 'next': request.GET.get('next')})

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
    logout(request)
    return redirect('home')



@cache_page_for_anon(300)  # Кэшируем на 5 минут только для анонимов
def home(request):
    # Оптимизированные запросы с select_related и prefetch_related
    featured = Product.objects.select_related('category').filter(featured=True).order_by('-id').first()
    categories = Category.objects.filter(is_active=True).order_by('order','name')
    # Показываем только первые 8 товаров с оптимизацией
    products = list(Product.objects.select_related('category').order_by('-id')[:8])
    # Варіанти кольорів для featured (якщо є додаток і дані)
    featured_variants = []
    # Варіанти кольорів для «Новинок»
    try:
        from productcolors.models import ProductColorVariant
        if featured:
            vset = ProductColorVariant.objects.select_related('color').prefetch_related('images').filter(product=featured).order_by('order','id')
            for v in vset:
                first_image = v.images.first()
                featured_variants.append({
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                    'is_default': v.is_default,
                    'first_image_url': first_image.image.url if first_image else '',
                })
        # Для списку новинок — підготуємо мапу
        prod_ids = [p.id for p in products]
        if prod_ids:
            vlist = ProductColorVariant.objects.select_related('color').prefetch_related('images').filter(product_id__in=prod_ids).order_by('product_id','order','id')
            colors_map = {}
            for v in vlist:
                first_image = v.images.first()
                colors_map.setdefault(v.product_id, []).append({
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                    'first_image_url': first_image.image.url if first_image else '',
                })
            for p in products:
                setattr(p, 'colors_preview', colors_map.get(p.id, []))
    except Exception:
        # якщо додаток або таблиці відсутні — просто не показуємо кольори
        for p in products:
            setattr(p, 'colors_preview', [])
        featured_variants = featured_variants or []
    # Проверяем есть ли еще товары для пагинации
    total_products = Product.objects.count()
    has_more = total_products > 8
    
    
    return render(
        request,
        'pages/index.html',
        {
            'featured': featured, 
            'categories': categories, 
            'products': products, 
            'featured_variants': featured_variants,
            'has_more_products': has_more,
            'current_page': 1,
            'total_products': total_products
        }
    )

def load_more_products(request):
    """AJAX view для загрузки дополнительных товаров"""
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        per_page = 8
        
        # Вычисляем offset
        offset = (page - 1) * per_page
        
        # Получаем товары для текущей страницы с оптимизацией
        products = list(Product.objects.select_related('category').order_by('-id')[offset:offset + per_page])
        
        
        # Подготавливаем цвета для товаров
        try:
            from productcolors.models import ProductColorVariant
            prod_ids = [p.id for p in products]
            if prod_ids:
                vlist = ProductColorVariant.objects.select_related('color').prefetch_related('images').filter(product_id__in=prod_ids).order_by('product_id','order','id')
                colors_map = {}
                for v in vlist:
                    first_image = v.images.first()
                    colors_map.setdefault(v.product_id, []).append({
                        'primary_hex': v.color.primary_hex,
                        'secondary_hex': v.color.secondary_hex or '',
                        'first_image_url': first_image.image.url if first_image else '',
                    })
                for p in products:
                    setattr(p, 'colors_preview', colors_map.get(p.id, []))
        except Exception:
            for p in products:
                setattr(p, 'colors_preview', [])
        
        # Проверяем есть ли еще товары
        total_products = Product.objects.count()
        has_more = (offset + per_page) < total_products
        
        
        # Рендерим HTML для товаров
        from django.template.loader import render_to_string
        products_html = render_to_string('partials/products_list.html', {
            'products': products,
            'page': page
        })
        
        
        return JsonResponse({
            'html': products_html,
            'has_more': has_more,
            'next_page': page + 1 if has_more else None
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@cache_page_for_anon(600)  # Кэшируем каталог на 10 минут только для анонимов
def catalog(request, cat_slug=None):
    categories = cache.get('categories_ordered')
    if categories is None:
        categories = list(Category.objects.order_by('order','name'))
        cache.set('categories_ordered', categories, 600)
    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        products = Product.objects.filter(category=category).order_by('-id')
        show_category_cards = False
    else:
        category = None
        products = Product.objects.order_by('-id')
        show_category_cards = True
    
    # Добавляем данные о цветах для товаров
    for product in products:
        try:
            from productcolors.models import ProductColorVariant
            variants = ProductColorVariant.objects.select_related('color').prefetch_related('images').filter(product=product)
            product.colors_preview = []
            for v in variants:
                first_image = v.images.first()
                product.colors_preview.append({
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                    'first_image_url': first_image.image.url if first_image else '',
                })
        except:
            product.colors_preview = []
    
    return render(request,'pages/catalog.html',{'categories':categories,'category':category,'products':products,'show_category_cards':show_category_cards})

@cache_page_for_anon(600)  # Кэшируем карточку товара на 10 минут для анонимов
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
    
    # Генерируем breadcrumbs для SEO
    breadcrumbs = [
        {'name': 'Головна', 'url': reverse('home')},
        {'name': 'Каталог', 'url': reverse('catalog')},
    ]
    
    if product.category:
        breadcrumbs.append({
            'name': product.category.name, 
            'url': reverse('catalog_by_cat', kwargs={'cat_slug': product.category.slug})
        })
    
    breadcrumbs.append({
        'name': product.title, 
        'url': reverse('product', kwargs={'slug': product.slug})
    })
    
    return render(request,'pages/product_detail.html',{
        'product': product,
        'images': images,
        'color_variants': color_variants,
        'auto_select_first_color': auto_select_first_color,
        'breadcrumbs': breadcrumbs
    })

@transaction.atomic
def add_product(request):
    """Добавление нового товара через унифицированный интерфейс"""
    if request.method == 'POST':
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
                return render(request, 'pages/add_product_new.html', {
                    'form': form,
                    'product': None,
                    'is_new': True
                })
    
    else:
        form = ProductForm()
        return render(request, 'pages/add_product_new.html', {
            'form': form,
            'product': None,
            'is_new': True
        })

@login_required
def add_category(request):
    if request.method=='POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(); return redirect('catalog')
    else:
        form = CategoryForm()
    return render(request,'pages/add_category.html',{'form':form})

def add_print(request):
    # Анти-спам: ограничим по сессии частоту отправок (не чаще 1 минуты)
    import time
    last_ts = request.session.get('print_proposal_last_ts', 0)
    now = int(time.time())
    rate_limited = now - last_ts < 60

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    proposal_form = None
    proposals = []

    if request.user.is_authenticated:
        # Список последних заявок пользователя
        proposals = PrintProposal.objects.filter(user=request.user).order_by('-created_at')[:10]

        if request.method == 'POST':
            if rate_limited:
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': 'rate_limited'}, status=429)
                else:
                    return redirect('cooperation')

            form = PrintProposalForm(request.POST, request.FILES)
            if form.is_valid():
                obj: PrintProposal = form.save(commit=False)
                obj.user = request.user
                obj.status = 'pending'
                obj.save()
                request.session['print_proposal_last_ts'] = now

                if is_ajax:
                    proposal_data = {
                        'id': obj.id,
                        'created_at': obj.created_at.strftime('%d.%m.%Y %H:%M'),
                        'status': obj.status,
                        'status_display': obj.get_status_display(),
                        'awarded_points': obj.awarded_points,
                        'awarded_promocode': obj.awarded_promocode.code if obj.awarded_promocode else None,
                        'awarded_promocode_display': obj.awarded_promocode.get_discount_display() if obj.awarded_promocode else None,
                        'description': obj.description or '',
                        'image_url': obj.image.url if obj.image else None,
                    }
                    return JsonResponse({'ok': True, 'proposal': proposal_data})
                else:
                    return redirect('cooperation')
            else:
                if is_ajax:
                    # Вернем первую ошибку для простоты
                    errors = []
                    for field, errs in form.errors.items():
                        errors.extend([str(e) for e in errs])
                    return JsonResponse({'ok': False, 'error': errors[0] if errors else 'invalid'}, status=400)
                else:
                    proposal_form = form
        else:
            proposal_form = PrintProposalForm()
    else:
        proposal_form = None

    return render(request, 'pages/add-print.html', {
        'proposal_form': proposal_form,
        'proposals': proposals,
        'rate_limited': rate_limited,
    })

def cooperation(request):
    """Страница сотрудничества с брендом TwoComms"""
    return render(request, 'pages/cooperation.html')

def about(request): return render(request,'pages/about.html')

def contacts(request): return render(request,'pages/contacts.html')

@cache_page_for_anon(120)  # Кэшируем результаты поиска на 2 минуты для анонимов
def search(request):
    q=(request.GET.get('q') or '').strip()
    qs = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images')
    if q: qs=qs.filter(title__icontains=q)
    categories = cache.get('categories_ordered')
    if categories is None:
        categories = list(Category.objects.order_by('order','name'))
        cache.set('categories_ordered', categories, 600)
    return render(request,'pages/catalog.html',{'categories':categories,'products':qs.order_by('-id'),'show_category_cards':False})

def debug_media(request):
    """Диагностика медиа-файлов"""
    import os
    from django.conf import settings
    
    # Обработка POST запроса для тестирования загрузки
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('test_file')
            if uploaded_file:
                # Создаем папку test если её нет
                test_dir = os.path.join(settings.MEDIA_ROOT, 'test')
                os.makedirs(test_dir, exist_ok=True)
                
                # Сохраняем файл
                file_path = os.path.join(test_dir, uploaded_file.name)
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                return JsonResponse({
                    'success': True,
                    'file_path': file_path,
                    'file_url': f"{settings.MEDIA_URL}test/{uploaded_file.name}",
                    'file_size': uploaded_file.size,
                    'message': 'Файл успешно загружен'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Файл не найден в запросе'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET запрос - возвращаем диагностическую информацию
    debug_info = {
        'MEDIA_URL': settings.MEDIA_URL,
        'MEDIA_ROOT': str(settings.MEDIA_ROOT),
        'DEBUG': settings.DEBUG,
        'BASE_DIR': str(settings.BASE_DIR),
    }
    
    # Проверяем существование папок
    media_root = settings.MEDIA_ROOT
    debug_info['media_root_exists'] = os.path.exists(media_root)
    
    if os.path.exists(media_root):
        debug_info['media_root_contents'] = os.listdir(media_root)
        debug_info['media_root_permissions'] = oct(os.stat(media_root).st_mode)[-3:]
    
    # Проверяем подпапки
    subfolders = ['products', 'avatars', 'category_covers', 'category_icons', 'product_colors', 'test']
    debug_info['subfolders'] = {}
    
    for folder in subfolders:
        folder_path = os.path.join(media_root, folder)
        debug_info['subfolders'][folder] = {
            'exists': os.path.exists(folder_path),
            'contents': os.listdir(folder_path) if os.path.exists(folder_path) else [],
            'permissions': oct(os.stat(folder_path).st_mode)[-3:] if os.path.exists(folder_path) else None
        }
    
    # Проверяем последние загруженные файлы
    debug_info['recent_files'] = []
    for folder in subfolders:
        folder_path = os.path.join(media_root, folder)
        if os.path.exists(folder_path):
            files = os.listdir(folder_path)
            for file in files[:5]:  # Показываем первые 5 файлов
                file_path = os.path.join(folder_path, file)
                debug_info['recent_files'].append({
                    'folder': folder,
                    'file': file,
                    'size': os.path.getsize(file_path),
                    'permissions': oct(os.stat(file_path).st_mode)[-3:],
                    'url': f"{settings.MEDIA_URL}{folder}/{file}"
                })
    
    return JsonResponse(debug_info)

def debug_media_page(request):
    """Страница диагностики медиа-файлов"""
    return render(request, 'pages/debug_media.html')

def debug_product_images(request):
    """Диагностика изображений товаров"""
    from storefront.models import Product
    
    products = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images')[:10]  # Берем первые 10 товаров
    
    debug_info = []
    for product in products:
        product_info = {
            'id': product.id,
            'title': product.title,
            'main_image': str(product.main_image) if product.main_image else None,
            'display_image': str(product.display_image) if product.display_image else None,
            'has_color_variants': product.color_variants.exists(),
            'color_variants_count': product.color_variants.count(),
        }
        
        # Проверяем цветовые варианты
        if product.color_variants.exists():
            first_variant = product.color_variants.first()
            product_info['first_variant'] = {
                'id': first_variant.id,
                'color_name': first_variant.color.name,
                'images_count': first_variant.images.count(),
                'first_image': str(first_variant.images.first().image) if first_variant.images.exists() else None,
            }
        
        debug_info.append(product_info)
    
    return JsonResponse({'products': debug_info})

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

    
    if not cart:
        return JsonResponse({'ok': True, 'count': 0, 'total': 0})
    
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
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
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart_sess)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                cart_sess.pop(key, None)
        request.session['cart'] = cart_sess
        request.session.modified = True
    
    items = []
    total = 0
    total_points = 0
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
        # Баллы за товар, если предусмотрены
        try:
            if getattr(p, 'points_reward', 0):
                total_points += int(p.points_reward) * int(it['qty'])
        except Exception:
            pass
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
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
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
    
    if not np_office or len(np_office.strip()) < 1:
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
    
    # Отправляем Telegram уведомление после создания заказа и товаров
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_new_order_notification(order)
    except Exception as e:
        # Не прерываем процесс, если уведомление не отправилось
        pass
    
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
        elif form_type == 'order_create':
            # Оформление заказа для авторизованного пользователя
            return order_create(request)
    
    cart_sess = request.session.get('cart', {})
    
    if not cart_sess:
        return render(request,'pages/cart.html',{'items':[],'total':0,'discount':0,'grand_total':0})
    
    ids = [i['product_id'] for i in cart_sess.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart_sess)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                cart_sess.pop(key, None)
        request.session['cart'] = cart_sess
        request.session.modified = True
    
    items = []
    total = 0
    total_points = 0
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
        # Баллы за товар, если предусмотрены
        try:
            if getattr(p, 'points_reward', 0):
                total_points += int(p.points_reward) * int(it['qty'])
        except Exception:
            pass
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
        'total_points': total_points,
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
        'email': prof.email or '',
        'telegram': prof.telegram or '',
        'instagram': prof.instagram or '',
        'city': prof.city or '',
        'np_office': prof.np_office or '',
        'pay_type': prof.pay_type or '',
        'is_ubd': prof.is_ubd,
    }
    form = ProfileSetupForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        prof.full_name = form.cleaned_data.get('full_name') or ''
        prof.phone = form.cleaned_data.get('phone') or ''
        prof.email = form.cleaned_data.get('email') or ''
        prof.telegram = form.cleaned_data.get('telegram') or ''
        prof.instagram = form.cleaned_data.get('instagram') or ''
        prof.city = form.cleaned_data.get('city') or ''
        prof.np_office = form.cleaned_data.get('np_office') or ''
        prof.pay_type = form.cleaned_data.get('pay_type') or ''
        prof.is_ubd = bool(form.cleaned_data.get('is_ubd'))
        
        # Отладочная информация для аватара
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
    
    # Проверяем, есть ли параметр принудительного обновления
    force_refresh = request.GET.get('_t')
    if force_refresh:
        # Очищаем кэш для принудительного обновления
        from django.core.cache import cache
        cache.clear()
    
    # Импорты для всех секций
    from django.db.models import Sum, Count, Avg
    if section == 'users':
        # Оптимизированный запрос с select_related и prefetch_related
        users = User.objects.select_related('userprofile').prefetch_related('points', 'orders').order_by('username')
        from accounts.models import UserPoints
        from orders.models import Order
        
        user_data = []
        for user in users:
            profile = getattr(user, 'userprofile', None)
            points = getattr(user, 'points', None)
            
            # Получаем заказы пользователя (уже загружены через prefetch_related)
            user_orders = user.orders.all()
            total_orders = user_orders.count()
            
            # Подсчитываем заказы по статусам
            order_status_counts = {}
            for status_code, status_name in Order.STATUS_CHOICES:
                order_status_counts[status_code] = user_orders.filter(status=status_code).count()
            
            # Подсчитываем заказы по статусам оплаты
            payment_status_counts = {}
            for payment_status_code, payment_status_name in [
                ('unpaid', 'Не оплачено'),
                ('checking', 'На перевірці'),
                ('partial', 'Внесена передплата'),
                ('paid', 'Оплачено повністю')
            ]:
                payment_status_counts[payment_status_code] = user_orders.filter(payment_status=payment_status_code).count()
            
            # Общая сумма заказов (включая предоплаты и частичные оплаты)
            total_spent = user_orders.exclude(payment_status='unpaid').aggregate(
                total=Sum('total_sum')
            )['total'] or 0
            
            # Потраченные баллы
            points_spent = points.total_spent if points else 0
            
            # Получаем промокоды пользователя (включая использованные)
            try:
                from .models import PromoCode
                # Промокоды, выданные пользователю
                user_promocodes = PromoCode.objects.filter(user=user).order_by('-created_at')
                # Промокоды, использованные в заказах пользователя
                used_promocodes = []
                for order in user_orders:
                    if order.promo_code:
                        used_promocodes.append({
                            'code': order.promo_code.code,
                            'discount': order.promo_code.discount,
                            'used_in_order': order.order_number,
                            'used_date': order.created
                        })
            except:
                user_promocodes = []
                used_promocodes = []
            
            user_data.append({
                'user': user,
                'profile': profile,
                'points': points,
                'total_orders': total_orders,
                'order_status_counts': order_status_counts,
                'payment_status_counts': payment_status_counts,
                'total_spent': total_spent,
                'points_spent': points_spent,
                'promocodes': user_promocodes,
                'used_promocodes': used_promocodes
            })
        
        ctx.update({'user_data': user_data})
    elif section == 'catalogs':
        from .models import Category, Product
        categories = Category.objects.filter(is_active=True).order_by('order','name') if hasattr(Category, 'order') else Category.objects.filter(is_active=True).order_by('name')
        products = Product.objects.select_related('category').order_by('-id')
        ctx.update({'categories': categories, 'products': products})
    elif section == 'promocodes':
        from .models import PromoCode
        promocodes = PromoCode.objects.all()
        total_promocodes = promocodes.count()
        active_promocodes = promocodes.filter(is_active=True).count()
        ctx.update({
            'promocodes': promocodes,
            'total_promocodes': total_promocodes,
            'active_promocodes': active_promocodes
        })
    elif section == 'offline_stores':
        from .models import OfflineStore
        stores = OfflineStore.objects.all()
        total_stores = stores.count()
        active_stores = stores.filter(is_active=True).count()
        ctx.update({
            'stores': stores,
            'total_stores': total_stores,
            'active_stores': active_stores
        })
    elif section == 'print_proposals':
        from .models import PrintProposal
        proposals = PrintProposal.objects.select_related('user', 'user__userprofile', 'awarded_promocode').order_by('-created_at')
        total_proposals = proposals.count()
        pending_proposals = proposals.filter(status='pending').count()
        ctx.update({
            'print_proposals': proposals,
            'total_proposals': total_proposals,
            'pending_proposals': pending_proposals
        })
    elif section == 'orders':
        # реальные замовлення
        try:
            from orders.models import Order
            
            # Получаем параметры фильтрации
            status_filter = request.GET.get('status', 'all')
            payment_filter = request.GET.get('payment', 'all')
            user_id_filter = request.GET.get('user_id', None)
            
            
            # Базовый queryset
            orders = Order.objects.select_related('user').prefetch_related('items','items__product')
            
            # Применяем фильтры
            if status_filter != 'all':
                orders = orders.filter(status=status_filter)
            
            if payment_filter != 'all':
                orders = orders.filter(payment_status=payment_filter)
            
            # Фильтр по конкретному пользователю
            user_filter_info = None
            if user_id_filter:
                orders = orders.filter(user_id=user_id_filter)
                
                # Получаем информацию о пользователе для отображения
                try:
                    user_obj = User.objects.get(id=user_id_filter)
                    
                    # Проверяем, есть ли у пользователя профиль
                    full_name = None
                    if hasattr(user_obj, 'userprofile') and user_obj.userprofile:
                        try:
                            full_name = user_obj.userprofile.full_name
                        except:
                            full_name = None
                    
                    user_filter_info = {
                        'username': user_obj.username,
                        'full_name': full_name
                    }
                except User.DoesNotExist:
                    pass
                    user_filter_info = None
            
            # Получаем отфильтрованные заказы
            orders = orders.all()
            
            # Подсчет заказов по статусам
            status_counts = {}
            for status_code, status_name in Order.STATUS_CHOICES:
                status_counts[status_code] = Order.objects.filter(status=status_code).count()
            
            # Подсчет заказов по статусам оплаты
            payment_status_counts = {}
            for payment_status_code, payment_status_name in [
                ('unpaid', 'Не оплачено'),
                ('checking', 'На перевірці'),
                ('partial', 'Внесена передплата'),
                ('paid', 'Оплачено повністю')
            ]:
                payment_status_counts[payment_status_code] = Order.objects.filter(payment_status=payment_status_code).count()
            
            # Общее количество заказов
            total_orders = Order.objects.count()
            
        except Exception:
            orders = []
            status_counts = {}
            payment_status_counts = {}
            total_orders = 0
        
        ctx.update({
            'orders': orders,
            'status_counts': status_counts,
            'payment_status_counts': payment_status_counts,
            'total_orders': total_orders,
            'status_filter': status_filter,
            'payment_filter': payment_filter,
            'user_id_filter': user_id_filter,
            'user_filter_info': user_filter_info
        })
    else:
        # stats — основная статистика с фильтрами по времени
        try:
            
            # Импорты
            from orders.models import Order
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DurationField
            
            # Импортируем опциональные модели с защитой от отсутствующих таблиц
            try:
                from accounts.models import UserPoints
            except Exception as e:
                UserPoints = None
            
            try:
                from .models import Product, Category, PrintProposal, SiteSession, PageView
            except Exception as e:
                raise
            
            # Получаем период из параметров
            period = request.GET.get('period', 'today')
            now = timezone.now()
            today = now.date()
            
            # Определяем временные рамки
            if period == 'today':
                start_date = today
                end_date = today
                period_name = 'Сьогодні'
            elif period == 'week':
                start_date = today - timedelta(days=7)
                end_date = today
                period_name = 'За тиждень'
            elif period == 'month':
                start_date = today - timedelta(days=30)
                end_date = today
                period_name = 'За місяць'
            else:  # all_time
                start_date = None
                end_date = None
                period_name = 'За весь час'
            
            # Базовые QuerySet'ы для фильтрации
            if start_date and end_date:
                orders_qs = Order.objects.filter(created__date__range=[start_date, end_date])
                users_qs = User.objects.filter(date_joined__date__range=[start_date, end_date])
            else:
                orders_qs = Order.objects.all()
                users_qs = User.objects.all()
            
            # === РАБОЧИЕ МЕТРИКИ ===
            
            # Заказы
            try:
                orders_count = orders_qs.count()
                orders_today = Order.objects.filter(created__date=today).count()
            except Exception as e:
                orders_count = 0
                orders_today = 0
            
            # Выручка
            try:
                revenue = orders_qs.filter(payment_status='paid').aggregate(
                    total=Sum('total_sum')
                )['total'] or 0
            except Exception as e:
                revenue = 0
            
            # Средний чек
            try:
                avg_order_value = orders_qs.filter(payment_status='paid').aggregate(
                    avg=Avg('total_sum')
                )['avg'] or 0
            except Exception as e:
                avg_order_value = 0
            
            # Пользователи
            try:
                total_users = User.objects.count()
                new_users_period = users_qs.count()
                active_users_today = User.objects.filter(last_login__date=today).count()
                active_users_period = User.objects.filter(last_login__date__range=[start_date, end_date]).count() if start_date and end_date else User.objects.filter(last_login__date=today).count()
            except Exception as e:
                total_users = 0
                new_users_period = 0
                active_users_today = 0
                active_users_period = 0
            
            # Товары
            try:
                total_products = Product.objects.count()
                total_categories = Category.objects.count()
            except Exception as e:
                total_products = 0
                total_categories = 0
            
            # Принты на рассмотрении
            try:
                print_proposals_pending = PrintProposal.objects.filter(status='pending').count()
            except Exception as e:
                print_proposals_pending = 0
            
            # Промокоды использованные
            try:
                promocodes_used = orders_qs.exclude(promo_code__isnull=True).count()
            except Exception as e:
                promocodes_used = 0
            
            # Баллы (защита, если таблицы ещё нет)
            if UserPoints is not None:
                try:
                    total_points_earned = UserPoints.objects.aggregate(
                        total=Sum('points')
                    )['total'] or 0
                    users_with_points = UserPoints.objects.filter(points__gt=0).count()
                except Exception as e:
                    total_points_earned = 0
                    users_with_points = 0
            else:
                total_points_earned = 0
                users_with_points = 0
            
            # === МЕТРИКИ ПОСЕЩАЕМОСТИ (встроенная лёгкая аналитика) ===
            try:
                online_threshold = timezone.now() - timedelta(minutes=5)
                
                online_users = SiteSession.objects.filter(last_seen__gte=online_threshold, is_bot=False).count()
                unique_visitors_today = SiteSession.objects.filter(first_seen__date=today, is_bot=False).count()
                page_views_today = PageView.objects.filter(when__date=today, is_bot=False).count()

                # Fallback: если по какой‑то причине онлайн/уники не посчитались через SiteSession,
                # попробуем оценить их через PageView (уникальные сессии по просмотрам)
                if online_users == 0:
                    online_users = (
                        PageView.objects
                        .filter(when__gte=online_threshold, is_bot=False)
                        .values('session_id')
                        .distinct()
                        .count()
                    )
                
                if unique_visitors_today == 0:
                    unique_visitors_today = (
                        PageView.objects
                        .filter(when__date=today, is_bot=False)
                        .values('session_id')
                        .distinct()
                        .count()
                    )
                    
            except Exception as e:
                online_users = 0
                unique_visitors_today = 0
                page_views_today = 0
            today_sessions = SiteSession.objects.filter(first_seen__date=today, is_bot=False)
            sv = today_sessions.filter(pageviews__lte=1).count()
            bounce_rate = round((sv / today_sessions.count()) * 100, 2) if today_sessions.exists() else 0
            durations = today_sessions.annotate(dur=ExpressionWrapper(F('last_seen') - F('first_seen'), output_field=DurationField())).values_list('dur', flat=True)
            if durations:
                total_seconds = sum((d.total_seconds() for d in durations if d is not None), 0)
                avg_session_duration = int(total_seconds / max(len(durations), 1))
            else:
                avg_session_duration = 0
            
            # Продажи метрики
            conversion_rate = 0  # Нужна система аналитики для расчета
            products_sold_today = 0  # Нужно считать количество товаров в заказах
            abandoned_carts = 0  # Нужна система отслеживания корзин
            
            # Контент метрики
            favorites_count = FavoriteProduct.objects.count()
            reviews_count = 0  # Нет модели отзывов
            avg_rating = 0  # Нет системы рейтингов
            
            stats = {
                # Рабочие метрики
                'orders_today': orders_today,
                'orders_count': orders_count,
                'revenue_today': revenue,
                'avg_order_value': round(avg_order_value, 2),
                'total_users': total_users,
                'new_users_today': new_users_period,
                'active_users_today': active_users_today,
                'active_users_period': active_users_period,
                'total_products': total_products,
                'total_categories': total_categories,
                'print_proposals_pending': print_proposals_pending,
                'promocodes_used_today': promocodes_used,
                'total_points_earned': total_points_earned,
                'users_with_points': users_with_points,
                'favorites_count': favorites_count,
                
                # Нерабочие метрики (заглушки)
                'online_users': online_users,
                'unique_visitors_today': unique_visitors_today,
                'page_views_today': page_views_today,
                'page_views_period': page_views_today if period == 'today' else (
                    PageView.objects.filter(when__date__range=[start_date, end_date], is_bot=False).count() if start_date and end_date 
                    else PageView.objects.filter(is_bot=False).count()
                ),
                'sessions_period': unique_visitors_today if period == 'today' else (
                    SiteSession.objects.filter(first_seen__date__range=[start_date, end_date], is_bot=False).count() if start_date and end_date 
                    else SiteSession.objects.filter(is_bot=False).count()
                ),
                'bounce_rate': bounce_rate,
                'avg_session_duration': avg_session_duration,
                'conversion_rate': conversion_rate,
                'products_sold_today': products_sold_today,
                'abandoned_carts': abandoned_carts,
                'reviews_count': reviews_count,
                'avg_rating': avg_rating,
                
                # Мета информация
                'period': period,
                'period_name': period_name,
                'start_date': start_date,
                'end_date': end_date
            }
            
        except Exception as e:
            # В случае ошибки возвращаем базовые значения
            # Получаем период из параметров для fallback
            period = request.GET.get('period', 'today')
            if period == 'today':
                period_name = 'Сьогодні'
            elif period == 'week':
                period_name = 'За тиждень'
            elif period == 'month':
                period_name = 'За місяць'
            else:
                period_name = 'За весь час'
            
            # Пытаемся получить базовые данные даже в случае ошибки
            try:
                total_users_fallback = User.objects.count()
                total_products_fallback = Product.objects.count()
                total_categories_fallback = Category.objects.count()
            except Exception as e:
                total_users_fallback = 0
                total_products_fallback = 0
                total_categories_fallback = 0
            
            stats = {
                'orders_today': 0,
                'orders_count': 0,
                'revenue_today': 0,
                'avg_order_value': 0,
                'total_users': total_users_fallback,
                'new_users_today': 0,
                'active_users_today': 0,
                'active_users_period': 0,
                'total_products': total_products_fallback,
                'total_categories': total_categories_fallback,
                'print_proposals_pending': 0,
                'promocodes_used_today': 0,
                'total_points_earned': 0,
                'users_with_points': 0,
                'favorites_count': 0,
                'online_users': 0,
                'unique_visitors_today': 0,
                'page_views_today': 0,
                'page_views_period': 0,
                'sessions_period': 0,
                'bounce_rate': 0,
                'avg_session_duration': 0,
                'conversion_rate': 0,
                'products_sold_today': 0,
                'abandoned_carts': 0,
                'reviews_count': 0,
                'avg_rating': 0,
                'period': period,
                'period_name': period_name,
                'start_date': None,
                'end_date': None
            }
        
        ctx.update({'stats': stats})
    
    # Создаем ответ с заголовками для предотвращения кэширования
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    
    html_content = render_to_string('pages/admin_panel.html', ctx, request=request)
    response = HttpResponse(html_content)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

@login_required
def admin_print_proposal_update_status(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        status = request.POST.get('status')
        
        if not proposal_id or not status:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        proposal.status = status
        proposal.save()
        
        status_text = dict(PrintProposal.STATUS_CHOICES)[status]
        
        return JsonResponse({
            'success': True, 
            'message': f'Статус принта оновлено на "{status_text}"',
            'new_status_text': status_text
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})

@login_required
def admin_print_proposal_award_points(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        points = int(request.POST.get('points', 0))
        
        if not proposal_id or points <= 0:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри або невірна кількість балів'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        proposal.awarded_points = points
        proposal.save()
        
        # Добавляем баллы пользователю
        from accounts.models import UserPoints
        user_points, created = UserPoints.objects.get_or_create(user=proposal.user)
        user_points.total_earned += points
        user_points.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Користувачу {proposal.user.username} нараховано {points} балів'
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Невірна кількість балів'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})

@login_required
def admin_print_proposal_award_promocode(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    try:
        proposal_id = request.POST.get('proposal_id')
        amount = int(request.POST.get('amount', 0))
        
        if not proposal_id or amount <= 0:
            return JsonResponse({'success': False, 'error': 'Відсутні обов\'язкові параметри або невірна сума'})
        
        proposal = PrintProposal.objects.get(id=proposal_id)
        
        # Создаем промокод
        from .models import PromoCode
        import random
        import string
        
        # Генерируем уникальный код
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not PromoCode.objects.filter(code=code).exists():
                break
        
        promocode = PromoCode.objects.create(
            code=code,
            discount_type='fixed',
            discount_amount=amount,
            user=proposal.user,
            is_active=True,
            description=f'Промокод за принт від {proposal.user.username}'
        )
        
        proposal.awarded_promocode = promocode
        proposal.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Користувачу {proposal.user.username} видано промокод {code} на суму {amount}₴'
        })
        
    except PrintProposal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Принт не знайдено'})
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Невірна сума промокоду'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'})

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
    
    # Получаем данные из формы или из профиля
    if request.method == 'POST':
        # Используем данные из формы
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        np_office = request.POST.get('np_office', '').strip()
        pay_type = request.POST.get('pay_type', '')
        
        # Валидация данных из формы
        if not full_name or len(full_name) < 3:
            from django.contrib import messages
            messages.error(request, 'ПІБ повинно містити мінімум 3 символи!')
            return redirect('cart')
        
        if not phone or len(phone.strip()) < 10:
            from django.contrib import messages
            messages.error(request, 'Введіть коректний номер телефону!')
            return redirect('cart')
        
        if not city or len(city.strip()) < 2:
            from django.contrib import messages
            messages.error(request, 'Введіть назву міста!')
            return redirect('cart')
        
        if not np_office or len(np_office.strip()) < 1:
            from django.contrib import messages
            messages.error(request, 'Введіть адресу відділення!')
            return redirect('cart')
        
        if not pay_type:
            from django.contrib import messages
            messages.error(request, 'Оберіть тип оплати!')
            return redirect('cart')
        
        # Обновляем профиль пользователя данными из формы
        prof.full_name = full_name
        prof.phone = phone
        prof.city = city
        prof.np_office = np_office
        prof.pay_type = pay_type
        prof.save()
        
    else:
        # Используем данные из профиля (для GET запросов)
        full_name = getattr(prof, 'full_name', '') or request.user.username
        phone = prof.phone
        city = prof.city
        np_office = prof.np_office
        pay_type = prof.pay_type
        
        # Проверяем обязательные поля с более строгой валидацией
        if not phone or len(phone.strip()) < 10:
            from django.contrib import messages
            messages.error(request, 'Введіть коректний номер телефону!')
            return redirect('cart')
        
        if not city or len(city.strip()) < 2:
            from django.contrib import messages
            messages.error(request, 'Введіть назву міста!')
            return redirect('cart')
        
        if not np_office or len(np_office.strip()) < 1:
            from django.contrib import messages
            messages.error(request, 'Введіть адресу відділення!')
            return redirect('cart')
        
        if not pay_type:
            from django.contrib import messages
            messages.error(request, 'Оберіть тип оплати!')
            return redirect('cart')

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

    # Пересчёт total и создание заказа в одной транзакции
    from django.db import transaction
    
    with transaction.atomic():
        ids = [i['product_id'] for i in cart.values()]
        prods = Product.objects.in_bulk(ids)
        total_sum = 0
        
        # Создаем заказ
        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            phone=phone, city=city, np_office=np_office,
            pay_type=pay_type, total_sum=0, status='new'
        )
        
        # Создаем все товары заказа
        order_items = []
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
            
            # Создаем OrderItem
            order_item = OrderItem(
                order=order, product=p, color_variant=color_variant, title=p.title, size=it.get('size', ''),
                qty=it['qty'], unit_price=unit, line_total=line
            )
            order_items.append(order_item)
        
        # Создаем все товары одним запросом
        OrderItem.objects.bulk_create(order_items)
        
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
        
        # Обновляем общую сумму заказа
        order.total_sum = total_sum
        order.save()

    # Очищаем корзину и промокод
    request.session['cart'] = {}
    request.session.pop('applied_promo_code', None)
    request.session.modified = True

    # Отправляем Telegram уведомление после создания заказа и товаров
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_new_order_notification(order)
    except Exception as e:
        # Не прерываем процесс, если уведомление не отправилось
        pass

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
    qs = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created')
    return render(request, 'pages/my_orders.html', {'orders': qs})

@login_required
@require_POST
def update_payment_method(request):
    """
    AJAX view для обновления метода оплаты заказа
    """
    from orders.models import Order
    
    order_id = request.POST.get('order_id')
    payment_method = request.POST.get('payment_method')
    
    if not order_id or not payment_method:
        return JsonResponse({
            'success': False,
            'error': 'Відсутні необхідні дані'
        })
    
    if payment_method not in ['full', 'partial']:
        return JsonResponse({
            'success': False,
            'error': 'Невірний метод оплати'
        })
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Замовлення не знайдено'
        })
    
    # Обновляем метод оплаты
    order.pay_type = payment_method
    order.save()
    
    # Определяем отображаемое название метода
    method_display = 'Повна передоплата' if payment_method == 'full' else 'Часткова передоплата'
    
    return JsonResponse({
        'success': True,
        'payment_method': payment_method,
        'method_display': method_display
    })

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
    from django.http import JsonResponse
    
    oid = request.POST.get('order_id')
    status = request.POST.get('status')
    tracking_number = request.POST.get('tracking_number', '').strip()
    
    try:
        o = Order.objects.get(pk=oid)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    old_status = o.status
    if status in dict(Order.STATUS_CHOICES):
        o.status = status
        
        # Обновляем ТТН если предоставлен
        if tracking_number:
            o.tracking_number = tracking_number
        
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
        
        # Формируем сообщение об успехе
        status_display = dict(Order.STATUS_CHOICES).get(status, status)
        message = f'Статус замовлення змінено на "{status_display}"'
        if tracking_number:
            message += f' з ТТН: {tracking_number}'
        
        return JsonResponse({
            'success': True, 
            'message': message,
            'status': status,
            'tracking_number': tracking_number
        })
    
    return JsonResponse({'success': False, 'error': 'Невірний статус'})


@login_required
def admin_update_payment_status(request):
    """Обновление статуса оплаты заказа"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    from orders.models import Order
    from django.http import JsonResponse
    
    order_id = request.POST.get('order_id')
    payment_status = request.POST.get('payment_status')
    
    if not order_id or not payment_status:
        return JsonResponse({'success': False, 'error': 'Відсутні необхідні дані'})
    
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    # Проверяем валидность статуса оплаты
    valid_payment_statuses = ['unpaid', 'checking', 'partial', 'paid']
    if payment_status not in valid_payment_statuses:
        return JsonResponse({'success': False, 'error': 'Невірний статус оплати'})
    
    # Обновляем статус оплаты
    order.payment_status = payment_status
    order.save()
    
    # Формируем сообщение об успехе
    payment_status_display = {
        'unpaid': 'Не оплачено',
        'checking': 'На перевірці',
        'partial': 'Внесена передплата',
        'paid': 'Оплачено повністю'
    }.get(payment_status, payment_status)
    
    return JsonResponse({
        'success': True,
        'message': f'Статус оплати змінено на "{payment_status_display}"',
        'payment_status': payment_status
    })


@login_required
def admin_approve_payment(request):
    """Подтверждение или отклонение оплаты заказа"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Невірний метод запиту'})
    
    from orders.models import Order
    from django.http import JsonResponse
    
    order_id = request.POST.get('order_id')
    action = request.POST.get('action')  # 'approve' или 'reject'
    
    if not order_id or not action:
        return JsonResponse({'success': False, 'error': 'Відсутні необхідні дані'})
    
    if action not in ['approve', 'reject']:
        return JsonResponse({'success': False, 'error': 'Невірна дія'})
    
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено'})
    
    if action == 'approve':
        # Подтверждаем оплату
        order.payment_status = 'paid'
        message = 'Оплату підтверджено'
        new_status = 'paid'
    else:
        # Отклоняем оплату
        order.payment_status = 'unpaid'
        message = 'Оплату відхилено'
        new_status = 'unpaid'
    
    order.save()
    
    return JsonResponse({
        'success': True,
        'message': message,
        'new_status': new_status
    })





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
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Обработка формы товара
        if form_type == 'product':
            if form.is_valid():
                prod = form.save()
                # возможно добавление дополнительных изображений позже
                
                # Если это AJAX запрос, возвращаем JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({
                        'success': True,
                        'product_id': prod.id,
                        'message': 'Товар успішно створено!'
                    })
                
                return redirect('/admin-panel/?section=catalogs')
            else:
                # Если это AJAX запрос с ошибками, возвращаем JSON с ошибками
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({
                        'success': False,
                        'errors': form.errors,
                        'message': 'Помилка валідації форми'
                    })
        
        # Обработка формы цвета
        elif form_type == 'color':
            product_id = request.POST.get('product_id')
            if not product_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Не вказано ID товару'
                })
            
            try:
                product = Product.objects.get(id=product_id)
                from productcolors.models import Color, ProductColorVariant, ProductColorImage
                
                color_name = request.POST.get('color_name')
                primary_hex = request.POST.get('primary_hex')
                secondary_hex = request.POST.get('secondary_hex', '')
                color_images = request.FILES.getlist('color_images')
                
                if color_name and primary_hex and color_images:
                    
                    # Проверяем, существует ли уже такой цвет
                    color = Color.objects.filter(
                        primary_hex=primary_hex,
                        secondary_hex=secondary_hex if secondary_hex else None
                    ).first()
                    
                    
                    if color:
                        # Если цвет существует, обновляем его название
                        color.name = color_name
                        color.save()
                    else:
                        # Создаем новый цвет с HEX кодами
                        color = Color.objects.create(
                            name=color_name,
                            primary_hex=primary_hex,
                            secondary_hex=secondary_hex if secondary_hex else None
                        )
                    
                    # Проверяем, не существует ли уже такой вариант цвета для этого товара
                    color_variant, created = ProductColorVariant.objects.get_or_create(
                        product=product,
                        color=color
                    )
                    
                    
                    # Добавляем изображения (всегда, если они есть)
                    if color_images:
                        for i, image_file in enumerate(color_images):
                            ProductColorImage.objects.create(
                                color_variant=color_variant,
                                image=image_file
                            )
                    
                    if created:
                        message = 'Колір успішно додано!'
                    else:
                        message = 'Колір вже існує для цього товару, але зображення додано!'
                    
                    return JsonResponse({
                        'success': True,
                        'color': {
                            'id': color.id,
                            'name': color.name,
                            'image_url': color_variant.images.first().image.url if color_variant.images.exists() else ''
                        },
                        'message': message
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Не всі обов\'язкові поля заповнені'
                    })
                    
            except Product.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Товар не знайдено'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Помилка створення кольору: {str(e)}'
                })
        
        # Обработка формы изображения
        elif form_type == 'image':
            product_id = request.POST.get('product_id')
            if not product_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Не вказано ID товару'
                })
            
            try:
                product = Product.objects.get(id=product_id)
                additional_image = request.FILES.get('additional_image')
                
                if additional_image:
                    from .models import ProductImage
                    ProductImage.objects.create(
                        product=product,
                        image=additional_image
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'image': {
                            'id': 'new',
                            'image_url': ProductImage.objects.filter(product=product).last().image.url
                        },
                        'message': 'Зображення успішно додано!'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Не вибрано зображення'
                    })
                    
            except Product.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Товар не знайдено'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Помилка додавання зображення: {str(e)}'
                })
    return render(request, 'pages/add_product_new.html', {'form': form, 'mode': 'new'})

@login_required
def admin_product_edit(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    from .forms import ProductForm
    from .models import Product
    obj = get_object_or_404(Product, pk=pk)
    
    # Если пришло действие с цветами — обрабатываем и возвращаемся на эту же страницу
    action = (request.POST.get('action') or '').strip() if request.method == 'POST' else ''
    
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
        
        # Проверяем, что это не запрос для цветов
        if not request.POST.get('action'):
            
            if form.is_valid():
                product = form.save(commit=False)
                # Автогенерація slug, якщо порожній
                if not getattr(product, 'slug', None):
                    base = slugify(product.title or '')
                    product.slug = unique_slugify(Product, base)
                product.save()
                return redirect('/admin-panel/?section=catalogs')
            else:
                # Обработка ошибок формы
                pass
        else:
            # Это запрос для цветов, пропускаем обработку основной формы
            pass

    # Данные для блока «Кольори»
    used_colors = []
    variants = []
    try:
        from productcolors.models import Color, ProductColorVariant
        used_colors = Color.objects.order_by('primary_hex', 'secondary_hex').all()
        variants = (ProductColorVariant.objects.select_related('color')
                    .prefetch_related('images')
                    .filter(product=obj).order_by('order', 'id'))
    except Exception as e:
        # Возвращаем базовые значения
        used_colors = []
        variants = []

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
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'product':
            form = ProductForm(request.POST, request.FILES, instance=obj)
            
            if form.is_valid():
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
                
                product.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Товар успішно збережено!'})
                return redirect('/admin-panel/?section=catalogs')
            else:
                # Возвращаем форму с ошибками для отображения пользователю
                return render(request, 'pages/admin_product_edit_unified.html', {
                    'form': form, 
                    'obj': obj
                })
        
        elif form_type == 'color':
            color_name = request.POST.get('color_name')
            primary_hex = request.POST.get('primary_hex')
            secondary_hex = request.POST.get('secondary_hex', '')
            color_images = request.FILES.getlist('color_images')
            
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
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': f'Колір успішно додано з {len(color_images)} зображеннями!'})
                return redirect(request.path)
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Колір успішно додано!'})
                return redirect(request.path)
        
        elif form_type == 'image':
            additional_image = request.FILES.get('additional_image')
            
            if additional_image:
                ProductImage.objects.create(
                    product=obj,
                    image=additional_image
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': 'Зображення успішно додано!'})
                return redirect(request.path)
            else:
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
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            product = form.save(commit=False)
            # Автогенерація slug, якщо порожній
            if not getattr(product, 'slug', None):
                base = slugify(product.title or '')
                product.slug = unique_slugify(Product, base)
            product.save()
            return redirect('/admin-panel/?section=catalogs')
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

# ===== ИЗБРАННЫЕ ТОВАРЫ =====
@require_POST
def toggle_favorite(request, product_id):
    """Добавить/удалить товар из избранного"""
    try:
        product = get_object_or_404(Product, id=product_id)
        
        if request.user.is_authenticated:
            # Для авторизованных пользователей - используем базу данных
            favorite, created = FavoriteProduct.objects.get_or_create(
                user=request.user,
                product=product
            )
            
            if not created:
                # Если запись уже существует, удаляем её
                favorite.delete()
                is_favorite = False
                message = 'Товар видалено з обраного'
            else:
                is_favorite = True
                message = 'Товар додано до обраного'
        else:
            # Для неавторизованных пользователей - используем сессии
            session_favorites = request.session.get('favorites', [])
            # Преобразуем product_id в int для корректного сравнения
            product_id_int = int(product_id)
            
            if product_id_int in session_favorites:
                # Удаляем из избранного
                session_favorites.remove(product_id_int)
                is_favorite = False
                message = 'Товар видалено з обраного'
            else:
                # Добавляем в избранное
                session_favorites.append(product_id_int)
                is_favorite = True
                message = 'Товар додано до обраного'
            
            # Сохраняем в сессии
            request.session['favorites'] = session_favorites
            request.session.modified = True
        
        # Подсчитываем общее количество избранных товаров
        if request.user.is_authenticated:
            favorites_count = FavoriteProduct.objects.filter(user=request.user).count()
        else:
            favorites_count = len(request.session.get('favorites', []))
        
        return JsonResponse({
            'success': True,
            'is_favorite': is_favorite,
            'message': message,
            'favorites_count': favorites_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Помилка: ' + str(e)
        }, status=400)


def favorites_list(request):
    """Страница с избранными товарами"""
    if request.user.is_authenticated:
        # Для авторизованных пользователей - получаем из базы данных
        favorites = FavoriteProduct.objects.filter(user=request.user).select_related('product', 'product__category')
    else:
        # Для неавторизованных пользователей - получаем из сессии
        session_favorites = request.session.get('favorites', [])
        favorites = []
        
        if session_favorites:
            # Получаем товары по ID из сессии
            products = Product.objects.filter(id__in=session_favorites).select_related('category')
            
            # Создаем объекты, похожие на FavoriteProduct
            for product in products:
                favorite = type('FavoriteProduct', (), {
                    'product': product,
                    'color_variants_data': []
                })()
                favorites.append(favorite)
    
    # Получаем варианты цветов для избранных товаров
    for favorite in favorites:
        try:
            from productcolors.models import ProductColorVariant
            variants = ProductColorVariant.objects.select_related('color').filter(product=favorite.product)
            # Создаем список словарей с данными о цветах
            color_variants_data = [
                {
                    'primary_hex': v.color.primary_hex,
                    'secondary_hex': v.color.secondary_hex or '',
                }
                for v in variants
            ]
            # Добавляем как атрибут к объекту favorite
            favorite.color_variants_data = color_variants_data
        except:
            favorite.color_variants_data = []
    
    return render(request, 'pages/favorites.html', {
        'favorites': favorites,
        'title': 'Обрані товари'
    })


def check_favorite_status(request, product_id):
    """Проверить статус избранного для товара"""
    try:
        if request.user.is_authenticated:
            # Для авторизованных пользователей - проверяем в базе данных
            is_favorite = FavoriteProduct.objects.filter(
                user=request.user,
                product_id=product_id
            ).exists()
        else:
            # Для неавторизованных пользователей - проверяем в сессии
            session_favorites = request.session.get('favorites', [])
            product_id_int = int(product_id)
            is_favorite = product_id_int in session_favorites
        
        return JsonResponse({'is_favorite': is_favorite})
    except:
        return JsonResponse({'is_favorite': False})


def favorites_count(request):
    """Получить количество товаров в избранном"""
    try:
        if request.user.is_authenticated:
            # Для авторизованных пользователей - считаем в базе данных
            count = FavoriteProduct.objects.filter(user=request.user).count()
        else:
            # Для неавторизованных пользователей - считаем в сессии
            session_favorites = request.session.get('favorites', [])
            count = len(session_favorites)
        
        return JsonResponse({
            'count': count
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)

@login_required
@require_POST
def confirm_payment(request):
    """
    AJAX view для подтверждения оплаты заказа
    """
    from orders.models import Order
    
    order_id = request.POST.get("order_id")
    payment_screenshot = request.FILES.get("payment_screenshot")
    
    if not order_id:
        return JsonResponse({
            "success": False,
            "error": "Відсутній ID замовлення"
        })
    
    if not payment_screenshot:
        return JsonResponse({
            "success": False,
            "error": "Будь ласка, завантажте скріншот оплати"
        })
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Замовлення не знайдено"
        })
    
    # Сохраняем скриншот оплаты
    order.payment_screenshot = payment_screenshot
    order.payment_status = "checking"
    order.save()
    
    return JsonResponse({
        "success": True,
        "message": "Скріншот оплати успішно завантажено"
    })


# ===== ОФФЛАЙН МАГАЗИНЫ =====

@login_required
def admin_offline_stores(request):
    """Список оффлайн магазинов"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore
    stores = OfflineStore.objects.all()
    
    # Подсчитываем статистику
    total_stores = stores.count()
    active_stores = stores.filter(is_active=True).count()
    
    return render(request, 'pages/admin_offline_stores.html', {
        'stores': stores,
        'total_stores': total_stores,
        'active_stores': active_stores,
        'section': 'offline_stores'
    })


class OfflineStoreForm(forms.ModelForm):
    class Meta:
        from .models import OfflineStore
        model = OfflineStore
        fields = ['name', 'address', 'phone', 'email', 'working_hours', 'description', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Назва магазину'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control bg-elevate',
                'rows': 3,
                'placeholder': 'Повна адреса магазину'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Телефон магазину'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Email магазину'
            }),
            'working_hours': forms.TextInput(attrs={
                'class': 'form-control bg-elevate',
                'placeholder': 'Наприклад: Пн-Пт 9:00-18:00, Сб 10:00-16:00'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control bg-elevate',
                'rows': 4,
                'placeholder': 'Опис магазину, особливості, послуги'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control bg-elevate',
                'min': '0',
                'placeholder': 'Порядок відображення'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@login_required
def admin_offline_store_create(request):
    """Создание нового оффлайн магазина"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore
    
    if request.method == 'POST':
        form = OfflineStoreForm(request.POST)
        if form.is_valid():
            store = form.save()
            return redirect('admin_store_management', store_id=store.id)
    else:
        form = OfflineStoreForm()
    
    return render(request, 'pages/admin_offline_store_form.html', {
        'form': form,
        'mode': 'create',
        'section': 'offline_stores'
    })


@login_required
def admin_offline_store_edit(request, pk):
    """Редактирование оффлайн магазина"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore
    store = get_object_or_404(OfflineStore, pk=pk)
    
    if request.method == 'POST':
        form = OfflineStoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            return redirect('admin_offline_stores')
    else:
        form = OfflineStoreForm(instance=store)
    
    return render(request, 'pages/admin_offline_store_form.html', {
        'form': form,
        'mode': 'edit',
        'store': store,
        'section': 'offline_stores'
    })


@login_required
def admin_offline_store_toggle(request, pk):
    """Активация/деактивация оффлайн магазина"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore
    store = get_object_or_404(OfflineStore, pk=pk)
    store.is_active = not store.is_active
    store.save()
    
    return redirect('admin_offline_stores')


@login_required
def admin_offline_store_delete(request, pk):
    """Удаление оффлайн магазина"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore
    store = get_object_or_404(OfflineStore, pk=pk)
    store.delete()
    
    return redirect('admin_offline_stores')


# ===== Новые views для функционала оффлайн магазинов =====

@login_required
def admin_store_management(request, store_id):
    """Главная страница управления оффлайн магазином"""
    if not request.user.is_staff:
        return redirect('home')
    
    from .models import OfflineStore, Product, Category, StoreProduct, StoreOrder, StoreOrderItem
    from productcolors.models import Color
    
    store = get_object_or_404(OfflineStore, pk=store_id)
    
    # Получаем все товары с их цветами и изображениями
    products = Product.objects.select_related('category').prefetch_related(
        'color_variants__color',
        'color_variants__images'
    ).all()
    
    # Получаем категории для фильтрации
    categories = Category.objects.filter(is_active=True).order_by('order', 'name')
    
    # Получаем товары в магазине
    store_products = StoreProduct.objects.filter(store=store, is_active=True).select_related(
        'product__category', 'color'
    )
    
    # Получаем активные заказы
    active_orders = StoreOrder.objects.filter(store=store, status='draft').prefetch_related(
        'order_items__product__category', 'order_items__color'
    )
    
    # Статистика магазина
    store_stats = {
        'total_products': store_products.count(),
        'total_cost': sum(sp.total_cost for sp in store_products),
        'total_selling_price': sum(sp.total_selling_price for sp in store_products),
        'total_margin': sum(sp.total_margin for sp in store_products),
        'categories_count': store_products.values('product__category__name').distinct().count(),
    }
    
    # Статистика по категориям
    category_stats = {}
    for sp in store_products:
        cat_name = sp.product.category.name
        if cat_name not in category_stats:
            category_stats[cat_name] = {
                'count': 0,
                'total_cost': 0,
                'total_selling_price': 0,
                'total_margin': 0
            }
        category_stats[cat_name]['count'] += sp.quantity
        category_stats[cat_name]['total_cost'] += sp.total_cost
        category_stats[cat_name]['total_selling_price'] += sp.total_selling_price
        category_stats[cat_name]['total_margin'] += sp.total_margin
    
    return render(request, 'pages/admin_store_management.html', {
        'store': store,
        'products': products,
        'categories': categories,
        'store_products': store_products,
        'active_orders': active_orders,
        'store_stats': store_stats,
        'category_stats': category_stats,
        'section': 'offline_stores'
    })


@login_required
def admin_store_get_order_items(request, store_id, order_id):
    """Получение товаров заказа для AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    from .models import OfflineStore, StoreOrder
    
    try:
        store = OfflineStore.objects.get(id=store_id)
        order = StoreOrder.objects.get(id=order_id, store=store)
        
        items = []
        for item in order.order_items.all():
            items.append({
                'id': item.id,
                'product_name': item.product.name,
                'size': item.size,
                'color_name': item.color.name if item.color else None,
                'quantity': item.quantity,
                'cost_price': float(item.cost_price),
                'selling_price': float(item.selling_price),
            })
        
        return JsonResponse({'success': True, 'items': items})
    
    except (OfflineStore.DoesNotExist, StoreOrder.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def admin_store_add_product_to_order(request, store_id):
    """Добавление товара в заказ через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    from .models import OfflineStore, Product, StoreOrder, StoreOrderItem
    from productcolors.models import Color
    
    try:
        store = get_object_or_404(OfflineStore, pk=store_id)
        product_id = request.POST.get('product_id')
        size = request.POST.get('size', '').strip()
        color_id = request.POST.get('color_id')
        cost_price = int(request.POST.get('cost_price', 0))
        selling_price = int(request.POST.get('selling_price', 0))
        quantity = int(request.POST.get('quantity', 1))
        
        product = get_object_or_404(Product, pk=product_id)
        color = None
        if color_id and color_id != 'default':
            color = get_object_or_404(Color, pk=color_id)
        elif color_id == 'default':
            # Создаем или получаем дефолтный черный цвет
            color, created = Color.objects.get_or_create(
                name='Чорний',
                defaults={'hex_code': '#000000'}
            )
        
        # Получаем или создаем черновик заказа
        order, created = StoreOrder.objects.get_or_create(
            store=store,
            status='draft',
            defaults={'notes': ''}
        )
        
        # Проверяем, есть ли уже такой товар в заказе
        existing_item = StoreOrderItem.objects.filter(
            order=order,
            product=product,
            size=size or None,
            color=color
        ).first()
        
        if existing_item:
            # Обновляем существующий товар
            existing_item.cost_price = cost_price
            existing_item.selling_price = selling_price
            existing_item.quantity += quantity
            existing_item.save()
            item = existing_item
        else:
            # Создаем новый товар в заказе
            item = StoreOrderItem.objects.create(
                order=order,
                product=product,
                size=size or None,
                color=color,
                cost_price=cost_price,
                selling_price=selling_price,
                quantity=quantity
            )
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'item': {
                'id': item.id,
                'product_name': item.product.title,
                'size': item.size or '',
                'color_name': item.color.name if item.color else None,
                'quantity': item.quantity,
                'cost_price': float(item.cost_price),
                'selling_price': float(item.selling_price),
                'product_image': item.product.display_image.url if item.product.display_image else None,
            },
            'message': 'Товар добавлен в заказ'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_store_remove_product_from_order(request, store_id, order_id, item_id):
    """Удаление товара из заказа"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    from .models import StoreOrder, StoreOrderItem
    
    try:
        order = get_object_or_404(StoreOrder, pk=order_id, store_id=store_id)
        item = get_object_or_404(StoreOrderItem, pk=item_id, order=order)
        item.delete()
        
        return JsonResponse({'success': True, 'message': 'Товар удален из заказа'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_store_add_products_to_store(request, store_id):
    """Добавление товаров из заказа в магазин"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    from .models import OfflineStore, StoreOrder, StoreOrderItem, StoreProduct
    
    try:
        store = get_object_or_404(OfflineStore, pk=store_id)
        order_id = request.POST.get('order_id')
        
        order = get_object_or_404(StoreOrder, pk=order_id, store=store)
        
        added_count = 0
        for item in order.order_items.all():
            # Проверяем, есть ли уже такой товар в магазине
            existing_product = StoreProduct.objects.filter(
                store=store,
                product=item.product,
                size=item.size,
                color=item.color
            ).first()
            
            if existing_product:
                # Обновляем существующий товар
                existing_product.cost_price = item.cost_price
                existing_product.selling_price = item.selling_price
                existing_product.quantity += item.quantity
                existing_product.is_active = True
                existing_product.save()
            else:
                # Создаем новый товар в магазине
                StoreProduct.objects.create(
                    store=store,
                    product=item.product,
                    size=item.size,
                    color=item.color,
                    cost_price=item.cost_price,
                    selling_price=item.selling_price,
                    quantity=item.quantity
                )
            added_count += 1
        
        # Обновляем статус заказа
        order.status = 'completed'
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Добавлено {added_count} товаров в магазин'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_store_generate_invoice(request, store_id):
    """Генерация Excel накладной"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    from .models import OfflineStore, StoreOrder, StoreInvoice
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment
    from datetime import datetime
    import os
    
    try:
        store = get_object_or_404(OfflineStore, pk=store_id)
        order_id = request.POST.get('order_id')
        
        order = get_object_or_404(StoreOrder, pk=order_id, store=store)
        
        # Создаем Excel файл
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Накладна"
        
        # Заголовки
        ws['A1'] = f"Накладна для магазину: {store.name}"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A2'] = f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        ws['A2'].font = Font(size=12)
        
        # Заголовки таблицы
        headers = ['Товар', 'Ціна продажу (грн)']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Данные товаров
        row = 5
        category_totals = {}
        
        for item in order.order_items.all():
            # Формируем название товара
            product_name = item.product.title
            if item.size:
                product_name += f" ({item.size})"
            if item.color:
                product_name += f" [{item.color}]"
            
            ws.cell(row=row, column=1, value=product_name)
            ws.cell(row=row, column=2, value=item.selling_price)
            
            # Подсчитываем по категориям
            category = item.product.category.name
            if category not in category_totals:
                category_totals[category] = {'count': 0, 'total': 0}
            category_totals[category]['count'] += item.quantity
            category_totals[category]['total'] += item.selling_price * item.quantity
            
            row += 1
        
        # Итоги по категориям
        row += 1
        ws.cell(row=row, column=1, value="Підсумки по категоріях:")
        ws.cell(row=row, column=1).font = Font(bold=True)
        row += 1
        
        for category, totals in category_totals.items():
            ws.cell(row=row, column=1, value=f"{category}: {totals['count']} шт., сума {totals['total']} грн")
            row += 1
        
        # Общий итог
        row += 1
        total_amount = sum(totals['total'] for totals in category_totals.values())
        ws.cell(row=row, column=1, value=f"ВСЬОГО: {total_amount} грн")
        ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        
        # Настройка ширины колонок
        ws.column_dimensions['A'].width = 50
        ws.column_dimensions['B'].width = 20
        
        # Сохраняем файл
        filename = f"invoice_{store.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(settings.MEDIA_ROOT, 'invoices', filename)
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        wb.save(filepath)
        
        # Сохраняем информацию о накладной в БД
        StoreInvoice.objects.create(
            store=store,
            order=order,
            file_name=filename,
            file_path=filepath
        )
        
        # Обновляем статус заказа
        order.status = 'completed'
        order.save()
        
        # Возвращаем файл для скачивания
        with open(filepath, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_store_update_product(request, store_id, product_id):
    """Обновление товара в магазине"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    from .models import StoreProduct
    
    try:
        store_product = get_object_or_404(StoreProduct, pk=product_id, store_id=store_id)
        
        cost_price = request.POST.get('cost_price')
        selling_price = request.POST.get('selling_price')
        quantity = request.POST.get('quantity')
        
        if cost_price:
            store_product.cost_price = int(cost_price)
        if selling_price:
            store_product.selling_price = int(selling_price)
        if quantity:
            store_product.quantity = int(quantity)
        
        store_product.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Товар обновлен',
            'data': {
                'total_cost': store_product.total_cost,
                'total_selling_price': store_product.total_selling_price,
                'total_margin': store_product.total_margin
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_store_remove_product(request, store_id, product_id):
    """Удаление товара из магазина"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    from .models import StoreProduct
    
    try:
        store_product = get_object_or_404(StoreProduct, pk=product_id, store_id=store_id)
        store_product.delete()
        
        return JsonResponse({'success': True, 'message': 'Товар удален из магазина'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def robots_txt(request):
    host = request.get_host() or "twocomms.shop"
    scheme = "https"
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Disallow: /admin/",
        "Disallow: /admin-panel/",
        "Disallow: /debug/",
        "Disallow: /media/debug/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /orders/",
        "Disallow: /my/",
        "Disallow: /login/",
        "Disallow: /logout/",
        "Disallow: /register/",
        "Disallow: /profile/",
        "Disallow: /search/",
        "",
        f"Sitemap: {scheme}://{host}/sitemap.xml",
    ]
    resp = HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
    # Снимаем кэш, чтобы поисковики и CDN не держали старый редирект
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    resp["Content-Disposition"] = 'inline; filename="robots.txt"'
    return resp

@login_required
def admin_order_delete(request, pk: int):
    if not request.user.is_staff:
        return redirect('home')
    try:
        from orders.models import Order
        order = Order.objects.get(pk=pk)
        order.delete()
        from django.contrib import messages
        messages.success(request, f"Замовлення #{order.order_number} видалено")
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Помилка видалення: {e}")
    return redirect('admin_panel')


def delivery_view(request):
    """Страница доставки и оплаты"""
    # FAQ данные для структурированных данных
    faq_items = [
        {
            "question": "Як довго триває доставка по Україні?",
            "answer": "Доставка по Україні зазвичай триває 1-5 робочих днів залежно від регіону. У великих містах доставка може бути швидшою."
        },
        {
            "question": "Чи можна оплатити товар при отриманні?",
            "answer": "Так, ми пропонуємо накладений платіж для доставки по Україні. Варто врахувати, що при цьому способі оплати додається комісія перевізника."
        },
        {
            "question": "Як відстежити замовлення?",
            "answer": "Після відправки замовлення ви отримаєте номер ТТН на email або в Telegram. Ви можете відстежити посилку на сайті перевізника або через наш Telegram бот."
        },
        {
            "question": "Чи можлива доставка за кордон?",
            "answer": "Так, ми здійснюємо міжнародну доставку через Укрпошту та Нову пошту. Термін доставки 7-21 робочий день залежно від країни."
        },
        {
            "question": "Які способи оплати доступні?",
            "answer": "Ми приймаємо оплату на банківську картку, накладений платіж при отриманні, а також бали за купони для зареєстрованих користувачів."
        }
    ]
    
    return render(request, 'pages/delivery.html', {
        'faq_items': faq_items
    })


def google_merchant_feed(request):
    """Генерирует XML фид для Google Merchant Center"""
    from django.http import HttpResponse
    from django.utils import timezone
    import xml.etree.ElementTree as ET
    
    # Создаем корневой элемент RSS
    rss = ET.Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:g', 'http://base.google.com/ns/1.0')

    # Создаем канал
    channel = ET.SubElement(rss, 'channel')
    
    # Заголовок канала
    title = ET.SubElement(channel, 'title')
    title.text = 'TwoComms - Стріт & Мілітарі Одяг'
    
    link = ET.SubElement(channel, 'link')
    link.text = 'https://twocomms.shop'
    
    description = ET.SubElement(channel, 'description')
    description.text = 'Магазин стріт & мілітарі одягу з ексклюзивним дизайном'

    # Получаем все товары
    products = Product.objects.select_related('category').all()

    for product in products:
        # Создаем элемент товара
        item = ET.SubElement(channel, 'item')

        # Обязательные поля
        g_id = ET.SubElement(item, 'g:id')
        g_id.text = f"TC-{product.id}"

        g_title = ET.SubElement(item, 'g:title')
        g_title.text = product.title

        g_description = ET.SubElement(item, 'g:description')
        g_description.text = product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms"

        g_link = ET.SubElement(item, 'g:link')
        g_link.text = f"https://twocomms.shop/product/{product.slug}/"

        g_image_link = ET.SubElement(item, 'g:image_link')
        if product.display_image:
            g_image_link.text = f"https://twocomms.shop{product.display_image.url}"
        else:
            g_image_link.text = "https://twocomms.shop/static/img/placeholder.jpg"

        g_availability = ET.SubElement(item, 'g:availability')
        g_availability.text = 'in stock'

        g_price = ET.SubElement(item, 'g:price')
        g_price.text = f"{product.final_price} UAH"

        g_condition = ET.SubElement(item, 'g:condition')
        g_condition.text = 'new'

        g_brand = ET.SubElement(item, 'g:brand')
        g_brand.text = 'TwoComms'

        # Дополнительные поля
        g_mpn = ET.SubElement(item, 'g:mpn')
        g_mpn.text = f"TC-{product.id}"

        g_gtin = ET.SubElement(item, 'g:gtin')
        g_gtin.text = f"TC{product.id:08d}"

        # Категория
        if product.category:
            g_product_type = ET.SubElement(item, 'g:product_type')
            g_product_type.text = product.category.name

            g_google_product_category = ET.SubElement(item, 'g:google_product_category')
            g_google_product_category.text = '1604'  # Apparel & Accessories > Clothing

        # Возрастная группа и пол
        g_age_group = ET.SubElement(item, 'g:age_group')
        g_age_group.text = 'adult'

        g_gender = ET.SubElement(item, 'g:gender')
        if product.category:
            category_name = product.category.name.lower()
            if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                g_gender.text = 'male'
            elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                g_gender.text = 'female'
            else:
                g_gender.text = 'unisex'
        else:
            g_gender.text = 'unisex'

        # Размеры
        g_size = ET.SubElement(item, 'g:size')
        g_size.text = 'S,M,L,XL,XXL'

        # Материал
        g_material = ET.SubElement(item, 'g:material')
        g_material.text = '100% cotton'

        # Цвета
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product)
            colors = []
            for variant in color_variants:
                if variant.color and variant.color.name:
                    colors.append(variant.color.name)
            
            if colors:
                g_color = ET.SubElement(item, 'g:color')
                g_color.text = ','.join(colors[:3])  # Максимум 3 цвета
        except:
            pass

        # Дополнительные изображения
        try:
            for i, img in enumerate(product.images.all()[:9]):  # До 9 дополнительных изображений
                g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
                g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
        except:
            pass

    # Форматируем XML
    ET.indent(rss, space="  ", level=0)
    
    # Создаем XML строку
    xml_string = ET.tostring(rss, encoding='utf-8', xml_declaration=True).decode('utf-8')
    
    # Возвращаем XML ответ
    response = HttpResponse(xml_string, content_type='application/xml; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="google_merchant_feed.xml"'
    return response
