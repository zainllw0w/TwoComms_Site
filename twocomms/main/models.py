from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to="category_icons/", blank=True, null=True)  # картинка категории (по желанию)
    cover = models.ImageField(upload_to="category_covers/", blank=True, null=True)  # крупное изображение для карточки каталога
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

class Product(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    price = models.PositiveIntegerField()
    has_discount = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(blank=True, null=True)  # 5..90
    featured = models.BooleanField(default=False)  # для «предложенного» товара на главной
    description = models.TextField(blank=True)

    # главное изображение (покажем в карточках)
    main_image = models.ImageField(upload_to="products/", blank=True, null=True)

    @property
    def final_price(self):
        if self.has_discount and self.discount_percent:
            return int(self.price * (100 - self.discount_percent) / 100)
        return self.price

    def __str__(self):
        return self.title

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/extra/")

    def __str__(self):
        return f"Image for {self.product_id}"
