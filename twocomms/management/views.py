from django.shortcuts import render
from django.http import HttpResponse

from .models import Client

def home(request):
    clients = Client.objects.all().order_by('-created_at')[:10]
    return render(request, 'management/home.html', {'clients': clients})
