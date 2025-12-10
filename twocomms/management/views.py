from django.shortcuts import render
from django.http import HttpResponse

def home(request):
    return HttpResponse("<h1>TwoComms Management Subdomain</h1><p>Work in progress...</p>")
