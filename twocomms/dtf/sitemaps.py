from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import KnowledgePost


class DtfStaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return [
            "dtf:landing",
            "dtf:order",
            "dtf:status",
            "dtf:gallery",
            "dtf:requirements",
            "dtf:price",
            "dtf:delivery_payment",
            "dtf:contacts",
            "dtf:quality",
            "dtf:templates",
            "dtf:how_to_press",
            "dtf:preflight",
            "dtf:blog",
        ]

    def location(self, item):
        return reverse(item)


class KnowledgePostSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return KnowledgePost.objects.published().only("slug", "updated_at")

    def location(self, item):
        return reverse("dtf:blog_post", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at
