from django.contrib.sitemaps import Sitemap
from django.urls import reverse


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
        ]

    def location(self, item):
        return reverse(item)
