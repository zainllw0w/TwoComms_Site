#!/usr/bin/env python
"""SEO audit production DB query"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from storefront.models import Product, Category
from django.db.models import Q

# Product stats
total = Product.objects.count()
published = Product.objects.filter(status='published').count()
draft = Product.objects.exclude(status='published').count()
no_seo_title = Product.objects.filter(status='published', seo_title='').count()
no_seo_desc = Product.objects.filter(status='published', seo_description='').count()
no_main_img = Product.objects.filter(status='published', main_image='').count()
no_alt = Product.objects.filter(status='published', main_image_alt='').count()
no_short = Product.objects.filter(status='published', short_description='').count()
no_full = Product.objects.filter(status='published', full_description='').count()

# Category stats
cats = Category.objects.filter(is_active=True).count()
cats_all = Category.objects.count()

print('=== PRODUCT STATS ===')
print(f'Total: {total}')
print(f'Published: {published}')
print(f'Draft/Other: {draft}')
print(f'Published no seo_title: {no_seo_title}')
print(f'Published no seo_desc: {no_seo_desc}')
print(f'Published no main_image: {no_main_img}')
print(f'Published no main_image_alt: {no_alt}')
print(f'Published no short_desc: {no_short}')
print(f'Published no full_desc: {no_full}')
print(f'=== CATEGORY STATS ===')
print(f'Active: {cats}')
print(f'Total: {cats_all}')

# List categories with details
print('\n=== CATEGORY DETAILS ===')
for c in Category.objects.filter(is_active=True):
    seo_title = getattr(c, 'seo_title', '') or ''
    seo_desc = getattr(c, 'seo_description', '') or ''
    seo_h1 = getattr(c, 'seo_h1', '') or ''
    has_cover = bool(c.cover) if hasattr(c, 'cover') else False
    prod_count = Product.objects.filter(category=c, status='published').count()
    print(f'  {c.name} (slug={c.slug}): products={prod_count}, has_cover={has_cover}, seo_title="{seo_title[:60]}", seo_desc="{seo_desc[:60]}"')

# Product slug issues
print('\n=== SLUG ISSUES ===')
for p in Product.objects.filter(status='published').only('slug', 'title'):
    issues = []
    if p.slug.startswith('-'):
        issues.append('starts_with_hyphen')
    if p.slug.endswith('-'):
        issues.append('ends_with_hyphen')
    if '_' in p.slug:
        issues.append('has_underscore')
    if p.slug != p.slug.lower():
        issues.append('has_uppercase')
    if '--' in p.slug:
        issues.append('double_hyphen')
    if issues:
        print(f'  {p.slug}: {", ".join(issues)}')

# FAQ check
print('\n=== PRODUCT FAQ STATS ===')
try:
    from storefront.models import ProductFAQ
    total_faqs = ProductFAQ.objects.count()
    products_with_faq = ProductFAQ.objects.values('product').distinct().count()
    print(f'Total FAQ items: {total_faqs}')
    print(f'Products with FAQ: {products_with_faq}')
    # Sample FAQ questions
    print('Sample FAQ questions:')
    for faq in ProductFAQ.objects.all()[:10]:
        print(f'  Q: {faq.question[:80]}')
except Exception as e:
    print(f'FAQ error: {e}')

# Sample product titles and SEO data
print('\n=== SAMPLE PRODUCTS SEO ===')
for p in Product.objects.filter(status='published').only('title', 'slug', 'seo_title', 'seo_description')[:10]:
    print(f'  Title: {p.title}')
    print(f'  Slug: {p.slug}')
    print(f'  SEO Title: {p.seo_title[:80] if p.seo_title else "EMPTY"}')
    print(f'  SEO Desc: {p.seo_description[:80] if p.seo_description else "EMPTY"}')
    print()
