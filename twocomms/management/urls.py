from django.urls import path
from .views import HomeView, ClientCreateView

app_name = 'management'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('api/clients/create/', ClientCreateView.as_view(), name='client_create'),
]
