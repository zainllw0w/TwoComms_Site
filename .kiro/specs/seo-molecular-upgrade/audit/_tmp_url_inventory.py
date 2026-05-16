"""
Server-side script to collect URL inventory (executed via manage.py shell -c).
"""
import json
from django.apps import apps

Product = apps.get_model('storefront', 'Product')
Category = apps.get_model('storefront', 'Category')
ProductColorVariant = apps.get_model('productcolors', 'ProductColorVariant')
try:
    CategoryColorLanding = apps.get_model('storefront', 'CategoryColorLanding')
except LookupError:
    CategoryColorLanding = None

result = {'products': [], 'categories': [], 'color_variants': [], 'category_color_landings': [], 'stats': {}}

for p in Product.objects.all().select_related('category').order_by('id'):
    result['products'].append({
        'id': p.id, 'slug': p.slug, 'title': p.title,
        'status': p.status,
        'category_slug': p.category.slug if p.category_id else None,
        'category_id': p.category_id,
    })
for c in Category.objects.all().order_by('id'):
    result['categories'].append({'id': c.id, 'slug': c.slug, 'name': c.name})
for v in ProductColorVariant.objects.all().select_related('product', 'color').order_by('product_id', 'order', 'id'):
    result['color_variants'].append({
        'id': v.id, 'product_id': v.product_id,
        'product_slug': v.product.slug if v.product_id else None,
        'color_id': v.color_id,
        'color_name': v.color.name if v.color else None,
        'slug': v.slug, 'order': v.order, 'is_default': v.is_default,
    })
if CategoryColorLanding is not None:
    for L in CategoryColorLanding.objects.all().select_related('category', 'color').order_by('id'):
        result['category_color_landings'].append({
            'id': L.id,
            'category_slug': L.category.slug if L.category_id else None,
            'color_slug': L.color_slug,
            'is_published': getattr(L, 'is_published', None),
        })

result['stats']['total_products'] = len(result['products'])
result['stats']['published_products'] = sum(1 for p in result['products'] if str(p['status']).lower() == 'published')
result['stats']['total_categories'] = len(result['categories'])
result['stats']['total_color_variants'] = len(result['color_variants'])
result['stats']['total_category_color_landings'] = len(result['category_color_landings'])

print('===JSON_START===')
print(json.dumps(result, ensure_ascii=False))
print('===JSON_END===')
