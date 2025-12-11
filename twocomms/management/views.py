from collections import OrderedDict
from datetime import datetime, timedelta
import json

from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse
from django.core.files.base import ContentFile

import requests
from io import BytesIO
import datetime as dt
import os

from .models import Client, Report

POINTS = {
    'order': 45,
    'test_batch': 25,
    'waiting_payment': 20,
    'waiting_prepayment': 18,
    'xml_connected': 15,
    'sent_email': 15,
    'sent_messenger': 15,
    'wrote_ig': 15,
    'thinking': 10,
    'other': 8,
    'no_answer': 5,
    'invalid_number': 5,
    'not_interested': 5,
    'expensive': 5,
}
TARGET_CLIENTS_DAY = 20
TARGET_POINTS_DAY = 100


def calc_points(qs):
    total = 0
    for c in qs:
        total += POINTS.get(c.call_result, 0)
    return total


def get_user_stats(user):
    base_qs = Client.objects.filter(owner=user)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_qs = base_qs.filter(created_at__gte=today_start)
    return {
        'points_today': calc_points(today_qs),
        'points_total': calc_points(base_qs),
        'processed_today': today_qs.count(),
        'processed_total': base_qs.count(),
    }


def build_report_excel(user, stats, clients):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Звіт"

    title_font = Font(size=14, bold=True)
    header_font = Font(size=12, bold=True)

    ws["A1"] = "Звіт менеджера"
    ws["A1"].font = title_font
    ws.merge_cells("A1:D1")

    ws["A2"] = "Менеджер"
    ws["B2"] = user.get_full_name() or user.username
    ws["A3"] = "Дата"
    ws["B3"] = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    ws["A4"] = "Бали за сьогодні"
    ws["B4"] = stats['points_today']
    ws["A5"] = "Оброблено за сьогодні"
    ws["B5"] = stats['processed_today']
    ws["A6"] = "Бали всього"
    ws["B6"] = stats['points_total']
    ws["A7"] = "Оброблено всього"
    ws["B7"] = stats['processed_total']

    ws.append([])
    ws.append([
        "Магазин / Insta", "Телефон", "ПІБ", "Статус",
        "Джерело", "Підсумок", "Деталі", "Наступний дзвінок", "Створено"
    ])
    header_row = ws.max_row
    for col in range(1, 10):
        ws.cell(row=header_row, column=col).font = header_font
        ws.cell(row=header_row, column=col).fill = PatternFill(start_color="1f2937", end_color="1f2937", fill_type="solid")
        ws.cell(row=header_row, column=col).alignment = Alignment(horizontal="center")

    for c in clients:
        ws.append([
            c.shop_name,
            c.phone,
            c.full_name,
            c.get_role_display(),
            c.source,
            c.get_call_result_display(),
            c.call_result_details,
            timezone.localtime(c.next_call_at).strftime("%d.%m.%Y %H:%M") if c.next_call_at else "–",
            timezone.localtime(c.created_at).strftime("%d.%m.%Y %H:%M"),
        ])

    widths = [22, 16, 22, 12, 16, 20, 24, 18, 18]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


def send_telegram_report(user, stats, clients, file_bytes, filename):
    token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN")
    chat_id = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID")
    if not token or not chat_id:
        return
    text = (
        f"Звіт менеджера\n"
        f"👤 {user.get_full_name() or user.username}\n"
        f"📅 {timezone.localtime().strftime('%d.%m.%Y %H:%M')}\n"
        f"Бали за сьогодні: {stats['points_today']}\n"
        f"Оброблено за сьогодні: {stats['processed_today']}\n"
        f"Клієнтів всього: {stats['processed_total']}"
    )
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {
        'document': (filename, file_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    data = {
        'chat_id': chat_id,
        'caption': text,
        'parse_mode': 'HTML'
    }
    try:
        requests.post(url, data=data, files=files, timeout=10)
    except Exception:
        pass

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
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Сформируем актуальные данные после операции
            stats = get_user_stats(request.user)
            user_points_today = stats['points_today']
            user_points_total = stats['points_total']
            processed_today = stats['processed_today']
            progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
            progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

            latest = Client.objects.filter(owner=request.user).order_by('-created_at').first()
            latest_data = None
            if latest:
                latest_data = {
                    'id': latest.id,
                    'shop': latest.shop_name,
                    'phone': latest.phone,
                    'full_name': latest.full_name,
                    'role': latest.role,
                    'role_display': latest.get_role_display(),
                    'source': latest.source,
                    'call_result': latest.call_result,
                    'call_result_display': latest.get_call_result_display(),
                    'call_result_details': latest.call_result_details,
                    'next_call': timezone.localtime(latest.next_call_at).strftime('%d.%m.%Y %H:%M') if latest.next_call_at else '–',
                    'created_date_label': 'Сьогодні' if timezone.localtime(latest.created_at).date() == today else timezone.localtime(latest.created_at).strftime('%d.%m.%Y'),
                }

            return JsonResponse({
                'success': True,
                'user_points_today': user_points_today,
                'user_points_total': user_points_total,
                'processed_today': processed_today,
                'target_clients': TARGET_CLIENTS_DAY,
                'target_points': TARGET_POINTS_DAY,
                'progress_clients_pct': progress_clients_pct,
                'progress_points_pct': progress_points_pct,
                'latest': latest_data,
            })
        return redirect('management_home')

    base_qs = Client.objects.select_related('owner').order_by('-created_at')
    # У основній панелі всі бачать тільки свої записи
    clients_qs = base_qs.filter(owner=request.user)
    clients = clients_qs

    today = timezone.localdate()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
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

    clients_today = clients_qs.filter(created_at__gte=today_start)

    user_stats = get_user_stats(request.user)
    user_points_today = user_stats['points_today']
    user_points_total = user_stats['points_total']
    processed_today = user_stats['processed_today']

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

    stats = get_user_stats(request.user)
    user_points_today = stats['points_today']
    user_points_total = stats['points_total']
    processed_today = stats['processed_today']
    TARGET_CLIENTS_DAY = 20
    TARGET_POINTS_DAY = 100
    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

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
                    'full_name': c.full_name,
                    'phone': c.phone,
                    'role': c.get_role_display(),
                    'created': timezone.localtime(c.created_at).strftime('%d.%m.%Y %H:%M'),
                    'source': c.source,
                    'result': c.get_call_result_display(),
                    'result_code': c.call_result,
                    'details': c.call_result_details,
                    'next_call': timezone.localtime(c.next_call_at).strftime('%d.%m.%Y %H:%M') if c.next_call_at else '–',
                } for c in user_clients_preview
            ]
        })

    return render(request, 'management/admin.html', {
        'admin_user_data': admin_user_data,
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'user_points_today': user_points_today,
        'user_points_total': user_points_total,
        'processed_today': processed_today,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
    })


@login_required(login_url='management_login')
def reports(request):
    if not (request.user.is_staff or Client.objects.filter(owner=request.user).exists()):
        return render(request, 'management/reports.html', {'denied': True})

    qs = Report.objects.select_related('owner').order_by('-created_at')
    if not request.user.is_staff:
        qs = qs.filter(owner=request.user)

    reports_list = []
    for r in qs:
        clients = Client.objects.filter(
            owner=r.owner,
            created_at__date=timezone.localdate(r.created_at)
        ).order_by('-created_at')[:100]
        reports_list.append({
            'id': r.id,
            'created_at': r.created_at,
            'owner': r.owner,
            'points': r.points,
            'processed': r.processed,
            'file': r.file,
            'clients': [
                {
                    'shop': c.shop_name,
                    'full_name': c.full_name,
                    'phone': c.phone,
                    'role': c.get_role_display(),
                    'source': c.source,
                    'result': c.get_call_result_display(),
                    'result_code': c.call_result,
                    'details': c.call_result_details,
                    'next_call': timezone.localtime(c.next_call_at).strftime('%d.%m.%Y %H:%M') if c.next_call_at else '–',
                    'created': timezone.localtime(c.created_at).strftime('%d.%m.%Y %H:%M'),
                } for c in clients
            ]
        })

    stats = get_user_stats(request.user)
    progress_clients_pct = min(100, int(stats['processed_today'] / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(stats['points_today'] / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    return render(request, 'management/reports.html', {
        'reports': reports_list,
        'user_points_today': stats['points_today'],
        'user_points_total': stats['points_total'],
        'processed_today': stats['processed_today'],
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
    })


@login_required(login_url='management_login')
def send_report(request):
    if request.method != 'POST':
        return redirect('management_reports')
    if not (request.user.is_staff or Client.objects.filter(owner=request.user).exists()):
        return redirect('management_reports')

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    clients_today = Client.objects.filter(owner=request.user, created_at__gte=today_start).order_by('-created_at')
    stats = get_user_stats(request.user)

    file_bytes = build_report_excel(request.user, stats, clients_today)
    filename = f"report_{request.user.username}_{timezone.localtime().strftime('%Y%m%d_%H%M')}.xlsx"

    report = Report.objects.create(
        owner=request.user,
        points=stats['points_today'],
        processed=stats['processed_today'],
    )
    report.file.save(filename, ContentFile(file_bytes), save=True)

    send_telegram_report(request.user, stats, clients_today, file_bytes, filename)

    return redirect('management_reports')
