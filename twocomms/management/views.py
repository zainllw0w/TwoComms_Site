from django.views.generic import TemplateView, CreateView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.shortcuts import render
from .models import Client

class HomeView(TemplateView):
    template_name = 'management/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clients'] = Client.objects.all().order_by('-created_at')[:50] # Покажем последние 50
        return context

class ClientCreateView(CreateView):
    model = Client
    fields = ['shop_name', 'phone', 'full_name', 'contact_role', 'source', 'last_call_result', 'last_call_result_text', 'next_call_at', 'is_non_conversion']
    
    def form_valid(self, form):
        self.object = form.save()
        # Для AJAX запросов возвращаем JSON
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or self.request.accepts('application/json'):
            return JsonResponse({
                'status': 'success',
                'client': {
                    'id': self.object.id,
                    'shop_name': self.object.shop_name,
                    'status': self.object.get_last_call_result_display(),
                }
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or self.request.accepts('application/json'):
             return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)
