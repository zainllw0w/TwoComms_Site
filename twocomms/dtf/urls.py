from django.urls import path
from django.contrib.sitemaps.views import sitemap

from .sitemaps import DtfStaticSitemap

from . import views

app_name = "dtf"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("estimate/", views.estimate, name="estimate"),
    path("order/", views.order, name="order"),
    path("order/thanks/<str:kind>/<str:number>/", views.thanks, name="thanks"),
    path("status/", views.status, name="status"),
    path("status/<str:order_number>/", views.status, name="status_code"),
    path("gallery/", views.gallery, name="gallery"),
    path("requirements/", views.requirements, name="requirements"),
    path("quality/", views.quality, name="quality"),
    path("templates/", views.templates, name="templates"),
    path("how-to-press/", views.how_to_press, name="how_to_press"),
    path("preflight/", views.preflight, name="preflight"),
    path("price/", views.price, name="price"),
    path("delivery-payment/", views.delivery_payment, name="delivery_payment"),
    path("contacts/", views.contacts, name="contacts"),
    path("lead/fab/", views.fab_lead, name="fab_lead"),
    path("sitemap.xml", sitemap, {"sitemaps": {"dtf": DtfStaticSitemap}}, name="dtf-sitemap"),
]
