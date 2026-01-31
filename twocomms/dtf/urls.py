from django.urls import path

from . import views

app_name = "dtf"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("order/", views.order, name="order"),
    path("order/thanks/<str:kind>/<str:number>/", views.thanks, name="thanks"),
    path("status/", views.status, name="status"),
    path("requirements/", views.requirements, name="requirements"),
    path("price/", views.price, name="price"),
    path("delivery-payment/", views.delivery_payment, name="delivery_payment"),
    path("contacts/", views.contacts, name="contacts"),
    path("lead/fab/", views.fab_lead, name="fab_lead"),
]
