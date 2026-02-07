from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "dtf"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("estimate/", views.estimate, name="estimate"),
    path("api/quote/", views.api_quote, name="api_quote"),
    path("order/", views.order, name="order"),
    path("order/thanks/<str:kind>/<str:number>/", views.thanks, name="thanks"),
    path("status/", views.status, name="status"),
    path("status/<str:order_number>/", views.status, name="status_code"),
    path("gallery/", views.gallery, name="gallery"),
    path("sample/", views.sample, name="sample"),
    path("about/", views.about, name="about"),
    path("products/", views.products, name="products"),
    path("constructor/", views.constructor_landing, name="constructor"),
    path("constructor/app/", views.constructor_app, name="constructor_app"),
    path("constructor/submit/", views.constructor_submit, name="constructor_submit"),
    path("constructor/sessions/<uuid:session_id>/", views.constructor_session_detail, name="constructor_session"),
    path("blog/", views.blog, name="blog"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
    path("requirements/", views.requirements, name="requirements"),
    path("quality/", views.quality, name="quality"),
    path("templates/", views.templates, name="templates"),
    path("effects-lab/", views.effects_lab, name="effects_lab"),
    path("how-to-press/", views.how_to_press, name="how_to_press"),
    path("preflight/", views.preflight, name="preflight"),
    path("price/", views.price, name="price"),
    path("prices/", RedirectView.as_view(pattern_name="dtf:price", permanent=True), name="prices"),
    path("delivery-payment/", views.delivery_payment, name="delivery_payment"),
    path("contacts/", views.contacts, name="contacts"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("returns/", views.returns, name="returns"),
    path("requisites/", views.requisites, name="requisites"),
    path("cabinet/", views.cabinet_home, name="cabinet"),
    path("cabinet/orders/", views.cabinet_orders, name="cabinet_orders"),
    path("cabinet/sessions/", views.cabinet_sessions, name="cabinet_sessions"),
    path("lead/fab/", views.fab_lead, name="fab_lead"),
    path("sitemap.xml", views.sitemap_xml, name="dtf-sitemap"),
]
