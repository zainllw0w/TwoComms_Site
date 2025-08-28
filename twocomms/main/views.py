from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from .models import Product, Category, ProductImage
from .forms import ProductForm, CategoryForm

# --- Главная ---
def home(request):
    featured = Product.objects.filter(featured=True).order_by("-id").first()
    categories = Category.objects.order_by("order", "name")
    products = Product.objects.order_by("-id")[:12]  # последние товары

    ctx = {
        "featured": featured,
        "categories": categories,
        "products": products,
    }
    return render(request, "pages/index.html", ctx)

# --- Каталог ---
def catalog(request, cat_slug=None):
    categories = Category.objects.order_by("order", "name")

    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        products = Product.objects.filter(category=category).order_by("-id")
        show_category_cards = False
    else:
        category = None
        products = Product.objects.order_by("-id")
        # на корне каталога хотим показать карточки категорий
        show_category_cards = True

    return render(request, "pages/catalog.html", {
        "categories": categories,
        "category": category,
        "products": products,
        "show_category_cards": show_category_cards,
    })

# --- Карточка товара ---
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    images = product.images.all()
    return render(request, "pages/product_detail.html", {"product": product, "images": images})

# --- Простое добавление товара (временно без авторизации) ---
@transaction.atomic
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            # сохранить дополнительные фото
            extra_files = request.FILES.getlist("extra_images")
            for f in extra_files:
                ProductImage.objects.create(product=product, image=f)
            return redirect("product", slug=product.slug)
    else:
        form = ProductForm()
    return render(request, "pages/add_product.html", {"form": form})

# --- Добавление категории (по желанию) ---
def add_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("catalog")
    else:
        form = CategoryForm()
    return render(request, "pages/add_category.html", {"form": form})

# --- Прочие страницы ---
def cooperation(request):
    return render(request, "pages/cooperation.html")

def about(request):
    return render(request, "pages/about.html")

def contacts(request):
    return render(request, "pages/contacts.html")

def search(request):
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.all()
    if q:
        qs = qs.filter(title__icontains=q)
    return render(request, "pages/catalog.html", {
        "categories": Category.objects.order_by("order", "name"),
        "products": qs.order_by("-id"),
        "show_category_cards": False
    })

def cart(request):
    # Заглушка — оформим позже
    return render(request, "pages/cart.html", {"items": [], "total": 0, "discount": 0, "grand_total": 0})

def checkout(request):
    return render(request, "pages/cart.html", {"items": [], "total": 0, "discount": 0, "grand_total": 0})
