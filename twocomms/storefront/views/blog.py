from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from storefront.forms import BlogCategoryForm, BlogPostForm
from storefront.models import BlogCategory, BlogPost, BlogPostView
from storefront.tracking import is_bot
from storefront.utm_utils import get_client_ip


BLOG_SOURCE_URL = "https://veteranfund.com.ua/stories-of-winner/artem-sinilo-istoriia-veterana/"


def _absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _published_posts():
    return BlogPost.objects.published().order_by("-published_at", "-id")


def _active_categories():
    return BlogCategory.objects.filter(is_active=True).order_by("order", "name")


def _blog_context(request, *, title: str | None = None) -> dict:
    categories = list(_active_categories())
    return {
        "blog_title": title or _("Новини та блог"),
        "blog_categories": categories,
        "is_blog_admin": bool(getattr(request.user, "is_staff", False)),
        "admin_blog_url": f"{reverse('admin_panel')}?section=blog",
        "admin_blog_post_create_url": reverse("admin_blog_post_create"),
    }


def _make_viewer_key(request, user_agent: str, ip: str | None) -> str:
    if getattr(request, "analytics_visitor_id", ""):
        raw = f"analytics:{request.analytics_visitor_id}"
    elif getattr(request, "session", None) and request.session.session_key:
        raw = f"session:{request.session.session_key}"
    elif getattr(request, "user", None) and request.user.is_authenticated:
        raw = f"user:{request.user.pk}"
    else:
        raw = f"anon:{ip or ''}:{user_agent}"
    return hashlib.sha256(f"{settings.SECRET_KEY}:{raw}".encode("utf-8")).hexdigest()


def record_blog_post_view(request, post: BlogPost) -> None:
    if request.method != "GET":
        return
    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:1000]
    if is_bot(user_agent):
        return

    ip = get_client_ip(request)
    visitor_key = _make_viewer_key(request, user_agent, ip)
    user = request.user if getattr(request.user, "is_authenticated", False) else None

    with transaction.atomic():
        BlogPost.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        try:
            view, created = BlogPostView.objects.get_or_create(
                post_id=post.pk,
                visitor_key=visitor_key,
                defaults={
                    "user": user,
                    "ip_address": ip or None,
                    "user_agent": user_agent,
                    "path": (request.path or "")[:300],
                },
            )
        except IntegrityError:
            created = False
            view = BlogPostView.objects.get(post_id=post.pk, visitor_key=visitor_key)

        if created:
            BlogPost.objects.filter(pk=post.pk).update(unique_view_count=F("unique_view_count") + 1)
        else:
            BlogPostView.objects.filter(pk=view.pk).update(
                views=F("views") + 1,
                last_seen=timezone.now(),
                user_id=(user.pk if user else view.user_id),
                path=(request.path or "")[:300],
            )


def legacy_blog_redirect(request):
    return HttpResponsePermanentRedirect(reverse("blog"))


def blog_index(request):
    posts = list(_published_posts())
    context = _blog_context(request)
    context.update(
        {
            "posts": posts,
            "active_category": None,
            "meta_title": _("Новини та блог | TwoComms"),
            "meta_description": _(
                "Новини TwoComms, блог бренда, огляди продукції та корисні матеріали про український одяг зі змістом."
            ),
            "canonical_path": reverse("blog"),
            "collection_schema": _json(
                {
                    "@context": "https://schema.org",
                    "@type": "CollectionPage",
                    "name": "Новини та блог TwoComms",
                    "url": _absolute_url(request, reverse("blog")),
                    "hasPart": [
                        {
                            "@type": "BlogPosting",
                            "headline": post.title,
                            "url": _absolute_url(request, post.get_absolute_url()),
                            "datePublished": post.published_at.isoformat(),
                        }
                        for post in posts[:12]
                    ],
                }
            ),
        }
    )
    return render(request, "pages/blog/index.html", context)


def blog_category(request, slug):
    category = get_object_or_404(_active_categories(), slug=slug)
    posts = list(_published_posts().filter(category=category))
    title = category.seo_h1 or category.name
    context = _blog_context(request, title=title)
    context.update(
        {
            "posts": posts,
            "active_category": category,
            "meta_title": category.seo_title or f"{category.name} | Новини та блог TwoComms",
            "meta_description": category.seo_description or category.description,
            "canonical_path": category.get_absolute_url(),
            "collection_schema": _json(
                {
                    "@context": "https://schema.org",
                    "@type": "CollectionPage",
                    "name": title,
                    "description": category.seo_description or category.description,
                    "url": _absolute_url(request, category.get_absolute_url()),
                    "isPartOf": {"@type": "Blog", "name": "Новини та блог TwoComms"},
                    "hasPart": [
                        {
                            "@type": "BlogPosting",
                            "headline": post.title,
                            "url": _absolute_url(request, post.get_absolute_url()),
                            "datePublished": post.published_at.isoformat(),
                        }
                        for post in posts[:12]
                    ],
                }
            ),
        }
    )
    return render(request, "pages/blog/category.html", context)


def blog_post(request, slug):
    post = get_object_or_404(_published_posts(), slug=slug)
    record_blog_post_view(request, post)
    post.refresh_from_db(fields=["view_count", "unique_view_count"])
    related = list(
        _published_posts()
        .filter(category=post.category)
        .exclude(pk=post.pk)
        .order_by("-published_at", "-id")[:3]
    )
    if len(related) < 3:
        related.extend(
            list(
                _published_posts()
                .exclude(pk=post.pk)
                .exclude(pk__in=[item.pk for item in related])
                .order_by("-published_at", "-id")[: 3 - len(related)]
            )
        )

    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.seo_title or post.title,
        "description": post.seo_description or post.excerpt,
        "datePublished": post.published_at.isoformat(),
        "dateModified": post.updated_at.isoformat(),
        "author": {"@type": "Organization", "name": "TwoComms"},
        "publisher": {"@type": "Organization", "name": "TwoComms"},
        "mainEntityOfPage": _absolute_url(request, post.get_absolute_url()),
        "articleSection": post.category.name,
    }
    if post.cover_image:
        article_schema["image"] = [_absolute_url(request, post.cover_image.url)]

    context = _blog_context(request, title=post.title)
    context.update(
        {
            "post": post,
            "related_posts": related,
            "active_category": post.category,
            "meta_title": post.seo_title or f"{post.title} | TwoComms",
            "meta_description": post.seo_description or post.excerpt,
            "canonical_path": post.get_absolute_url(),
            "article_schema": _json(article_schema),
            "breadcrumb_schema": _json(
                {
                    "@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "TwoComms", "item": _absolute_url(request, reverse("home"))},
                        {"@type": "ListItem", "position": 2, "name": "Новини та блог", "item": _absolute_url(request, reverse("blog"))},
                        {"@type": "ListItem", "position": 3, "name": post.category.name, "item": _absolute_url(request, post.category.get_absolute_url())},
                        {"@type": "ListItem", "position": 4, "name": post.title, "item": _absolute_url(request, post.get_absolute_url())},
                    ],
                }
            ),
        }
    )
    return render(request, "pages/blog/post.html", context)


def build_admin_blog_context():
    return {
        "blog_categories": BlogCategory.objects.order_by("order", "name"),
        "blog_posts": BlogPost.objects.select_related("category").order_by("-published_at", "-id"),
        "blog_category_form": BlogCategoryForm(),
        "blog_post_form": BlogPostForm(),
    }


def _admin_redirect():
    return redirect(f"{reverse('admin_panel')}?section=blog")


@staff_member_required
def admin_blog_category_create(request):
    form = BlogCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Категорію блогу створено.")
        return _admin_redirect()
    return render(request, "pages/blog/editor.html", {"form": form, "editor_title": "Нова категорія блогу"})


@staff_member_required
def admin_blog_category_update(request, pk):
    category = get_object_or_404(BlogCategory, pk=pk)
    form = BlogCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Категорію блогу оновлено.")
        return _admin_redirect()
    return render(request, "pages/blog/editor.html", {"form": form, "editor_title": "Редагування категорії блогу"})


@staff_member_required
def admin_blog_post_create(request):
    form = BlogPostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Пост блогу створено.")
        return _admin_redirect()
    return render(request, "pages/blog/editor.html", {"form": form, "editor_title": "Новий пост блогу"})


@staff_member_required
def admin_blog_post_update(request, pk):
    post = get_object_or_404(BlogPost, pk=pk)
    form = BlogPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Пост блогу оновлено.")
        return _admin_redirect()
    return render(request, "pages/blog/editor.html", {"form": form, "editor_title": "Редагування поста блогу", "post": post})
