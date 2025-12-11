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
    POINTS = {
        'order': 90,
        'test_batch': 50,
        'waiting_payment': 40,
        'waiting_prepayment': 35,
        'xml_connected': 30,
        'sent_email': 30,
        'sent_messenger': 30,
        'wrote_ig': 30,
        'thinking': 20,
        'other': 15,
        'no_answer': 10,
        'invalid_number': 10,
        'not_interested': 10,
        'expensive': 10,
    }
    TARGET_CLIENTS_DAY = 20
    TARGET_POINTS_DAY = 100

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
    # У основній панелі всі бачать тільки свої записи
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

    clients_today = clients.filter(created_at__date=today)

    def calc_points(qs):
        total = 0
        for c in qs:
            total += POINTS.get(c.call_result, 0)
        return total

    user_points_today = calc_points(clients_today)
    user_points_total = calc_points(clients)
    processed_today = clients_today.count()

    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    return render(request, 'management/home.html', {
        'grouped_clients': grouped_clients,
        'user_points_today': user_points_today,
        'user_points_total': user_points_total,
        'processed_today': processed_today,
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
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


@login_required(login_url='management_login')
def admin_overview(request):
    if not request.user.is_staff:
        return redirect('management_home')

    User = get_user_model()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    POINTS = {
        'order': 90,
        'test_batch': 50,
        'waiting_payment': 40,
        'waiting_prepayment': 35,
        'xml_connected': 30,
        'sent_email': 30,
        'sent_messenger': 30,
        'wrote_ig': 30,
        'thinking': 20,
        'other': 15,
        'no_answer': 10,
        'invalid_number': 10,
        'not_interested': 10,
        'expensive': 10,
    }

    def calc_points(qs):
        total = 0
        for c in qs:
            total += POINTS.get(c.call_result, 0)
        return total

    admin_user_data = []
    users = User.objects.filter(is_active=True).filter(
        Q(is_staff=True) | Q(management_clients__isnull=False)
    ).annotate(
        total_clients=Count('management_clients', distinct=True),
        today_clients=Count('management_clients', filter=Q(management_clients__created_at__gte=today_start), distinct=True),
    ).distinct()

    base_qs = Client.objects.filter(owner=request.user)
    user_clients_today = base_qs.filter(created_at__date=timezone.localdate())
    user_points_today = calc_points(user_clients_today)
    user_points_total = calc_points(base_qs)
    processed_today = user_clients_today.count()
    TARGET_CLIENTS_DAY = 20
    TARGET_POINTS_DAY = 100
    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0

    for u in users:
        last_login = u.last_login
        online = False
        last_login_local = None
        if last_login:
            last_login_local = timezone.localtime(last_login)
            online = (timezone.now() - last_login) <= timedelta(minutes=5)
        user_clients = Client.objects.filter(owner=u).order_by('-created_at')
        user_clients_today = user_clients.filter(created_at__gte=today_start)
        points_today = calc_points(user_clients_today)
        points_total = calc_points(user_clients)
        user_clients_preview = user_clients[:50]
        admin_user_data.append({
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'role': 'Адмін' if u.is_staff else 'Менеджер',
            'today': u.today_clients,
            'total': u.total_clients,
            'points_today': points_today,
            'points_total': points_total,
            'online': online,
            'last_login': last_login_local.strftime('%d.%m.%Y %H:%M') if last_login_local else 'Немає даних',
            'clients': [
                {
                    'shop': c.shop_name,
                    'created': timezone.localtime(c.created_at).strftime('%d.%m.%Y %H:%M'),
                } for c in user_clients_preview
            ]
        })

    return render(request, 'management/admin.html', {
        'admin_user_data': admin_user_data,
        'target_clients': 20,
        'target_points': 100,
        'user_points_today': user_points_today,
        'user_points_total': user_points_total,
        'processed_today': processed_today,
        'progress_clients_pct': progress_clients_pct,
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
    })
