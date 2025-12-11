from collections import OrderedDict
from datetime import datetime, timedelta
import json

from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from .models import Client

@login_required(login_url='management_login')
def home(request):
    if request.method == 'POST':
        data = request.POST
        client_id = data.get('client_id')
        shop_name = data.get('shop_name', '').strip()
        phone = data.get('phone', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', Client.Role.MANAGER)
        role_custom = data.get('role_custom', '').strip()
        source = data.get('source', '').strip()
        source_link = data.get('source_link', '').strip()
        source_other = data.get('source_other', '').strip()
        call_result = data.get('call_result', Client.CallResult.THINKING)
        call_result_other = data.get('call_result_other', '').strip()
        next_call_type = data.get('next_call_type', 'scheduled')
        next_call_date = data.get('next_call_date', '').strip()
        next_call_time = data.get('next_call_time', '').strip()

        source_display = {
            'instagram': 'Instagram',
            'prom_ua': 'Prom.ua',
            'google_maps': 'Google Карти',
            'forums': f"Сайти/Форуми: {source_link}" if source_link else 'Сайти/Форуми',
            'other': source_other or 'Інше',
        }.get(source, source or '')

        call_result_details_parts = []
        if role == Client.Role.OTHER and role_custom:
            call_result_details_parts.append(f"Роль: {role_custom}")
        if call_result == Client.CallResult.OTHER and call_result_other:
            call_result_details_parts.append(f"Інше: {call_result_other}")

        next_call_at = None
        if next_call_type == 'scheduled' and next_call_date and next_call_time:
            try:
                naive = datetime.strptime(f"{next_call_date} {next_call_time}", "%Y-%m-%d %H:%M")
                next_call_at = timezone.make_aware(naive, timezone.get_current_timezone())
            except ValueError:
                next_call_at = None
        elif next_call_type == 'no_follow':
            next_call_at = None

        if shop_name and phone and full_name:
            details = "\n".join(call_result_details_parts)
            if client_id:
                try:
                    client = Client.objects.get(id=client_id)
                    if request.user.is_staff or client.owner == request.user:
                        client.shop_name = shop_name
                        client.phone = phone
                        client.full_name = full_name
                        client.role = role
                        client.source = source_display
                        client.call_result = call_result
                        client.call_result_details = details
                        client.next_call_at = next_call_at
                        client.owner = client.owner or request.user
                        client.save()
                except Client.DoesNotExist:
                    pass
            else:
                Client.objects.create(
                    shop_name=shop_name,
                    phone=phone,
                    full_name=full_name,
                    role=role,
                    source=source_display,
                    call_result=call_result,
                    call_result_details=details,
                    next_call_at=next_call_at,
                    owner=request.user,
                )
        return redirect('management_home')

    base_qs = Client.objects.select_related('owner').order_by('-created_at')
    if request.user.is_staff:
        # Адміни в основній панелі бачать свої власні записи, як і звичайні менеджери
        clients = base_qs.filter(owner=request.user)[:200]
    else:
        clients = base_qs.filter(owner=request.user)[:200]

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    grouped = OrderedDict()

    for client in clients:
        local_date = timezone.localtime(client.created_at).date()
        if local_date == today:
            label = 'Сьогодні'
        elif local_date == yesterday:
            label = 'Вчора'
        else:
            label = local_date.strftime('%d.%m.%Y')

        grouped.setdefault(label, []).append(client)

    grouped_clients = list(grouped.items())

    admin_user_data = []
    if request.user.is_staff:
        User = get_user_model()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        users = User.objects.filter(is_active=True).filter(
            Q(is_staff=True) | Q(management_clients__isnull=False)
        ).annotate(
            total_clients=Count('management_clients', distinct=True),
            today_clients=Count('management_clients', filter=Q(management_clients__created_at__gte=today_start), distinct=True),
        ).distinct()
        for u in users:
            last_login = u.last_login
            online = False
            last_login_local = None
            if last_login:
                last_login_local = timezone.localtime(last_login)
                online = (timezone.now() - last_login) <= timedelta(minutes=5)
            user_clients = Client.objects.filter(owner=u).order_by('-created_at')[:50]
            admin_user_data.append({
                'id': u.id,
                'name': u.get_full_name() or u.username,
                'role': 'Адмін' if u.is_staff else 'Менеджер',
                'today': u.today_clients,
                'total': u.total_clients,
                'online': online,
                'last_login': last_login_local.isoformat() if last_login_local else None,
                'last_login_display': last_login_local.strftime('%d.%m.%Y %H:%M') if last_login_local else 'Немає даних',
                'clients': [
                    {
                        'shop': c.shop_name,
                        'created': timezone.localtime(c.created_at).strftime('%d.%m.%Y %H:%M'),
                    } for c in user_clients
                ]
            })

    return render(request, 'management/home.html', {
        'grouped_clients': grouped_clients,
        'admin_user_data': admin_user_data,
    })


@login_required(login_url='management_login')
def delete_client(request, client_id):
    if request.method != 'POST':
        return redirect('management_home')
    try:
        client = Client.objects.get(id=client_id)
        if request.user.is_staff or client.owner == request.user:
            client.delete()
    except Client.DoesNotExist:
        pass
    return redirect('management_home')
