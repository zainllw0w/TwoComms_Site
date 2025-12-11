from collections import OrderedDict
from datetime import datetime, timedelta
import json
import time

from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST

import requests
from io import BytesIO
import datetime as dt
import os
import secrets

from .models import Client, Report, ReminderRead, ReminderSent
from accounts.models import UserProfile
from django.views.decorators.csrf import csrf_exempt

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
REMINDER_WINDOW_MINUTES = 15

_BOT_USERNAME_CACHE = {"username": "", "ts": 0, "token": ""}


def calc_points(qs):
    total = 0
    for c in qs:
        total += POINTS.get(c.call_result, 0)
    return total


def get_manager_bot_username():
    """Try MANAGER_TG_BOT_USERNAME, else fetch via token. Fall back to report bot token if needed."""
    name = os.environ.get("MANAGER_TG_BOT_USERNAME", "")
    if name:
        return name
    token = os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN")
    if not token:
        return ""
    now = time.time()
    if _BOT_USERNAME_CACHE["username"] and _BOT_USERNAME_CACHE["token"] == token and now - _BOT_USERNAME_CACHE["ts"] < 600:
        return _BOT_USERNAME_CACHE["username"]
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=4)
        data = resp.json()
        if data.get("ok") and data.get("result", {}).get("username"):
            username = data["result"]["username"]
            _BOT_USERNAME_CACHE.update({"username": username, "ts": now, "token": token})
            return username
    except Exception:
        pass
    return ""


def get_today_range():
    """Localized start/end of current day for consistent filters."""
    now = timezone.localtime(timezone.now())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def has_report_today(user):
    start, end = get_today_range()
    return Report.objects.filter(owner=user, created_at__gte=start, created_at__lt=end).exists()


def _time_label(dt_local, now):
    delta = (now - dt_local).total_seconds()
    if delta >= 0:
        minutes = int(delta // 60)
        hours = int(delta // 3600)
        days = int(delta // 86400)
        if minutes < 1:
            return "щойно"
        if minutes < 60:
            return f"{minutes} хв тому"
        if hours < 24:
            return f"{hours} год тому"
        return f"{days} дн тому"
    else:
        delta_abs = abs(delta)
        minutes = int(delta_abs // 60)
        hours = int(delta_abs // 3600)
        days = int(delta_abs // 86400)
        if minutes < 1:
            return "за кілька секунд"
        if minutes < 60:
            return f"через {minutes} хв"
        if hours < 24:
            return f"через {hours} год"
        return f"через {days} дн"


def get_reminders(user, stats=None, report_sent=False):
    """Return upcoming/due follow-ups + report reminder."""
    now = timezone.localtime(timezone.now())
    read_keys = set(ReminderRead.objects.filter(user=user).values_list('key', flat=True))
    qs = Client.objects.filter(
        owner=user,
        next_call_at__isnull=False
    ).select_related('owner').order_by('-next_call_at')
    reminders = []
    for c in qs:
        dt_local = timezone.localtime(c.next_call_at)
        status = 'due' if dt_local <= now else 'soon'
        status_key = 'due' if status == 'due' else 'soon'
        eta_raw = max(0, int((dt_local - now).total_seconds()))
        # Пропускаємо майбутні дзвінки, якщо більше ніж 5 хв
        if status == 'soon' and eta_raw > 300:
            continue
        reminder = {
            'shop': c.shop_name,
            'name': c.full_name,
            'phone': c.phone,
            'when': dt_local.strftime('%d.%m %H:%M'),
            'time_label': _time_label(dt_local, now),
            'status': status,
            'kind': 'call',
            'dt': dt_local,
            'dt_iso': dt_local.isoformat(),
            'eta_seconds': eta_raw,
            'key': f"call-{c.id}-{int(dt_local.timestamp())}-{status_key}",
        }
        # Таймерные (soon) всегда считаем непрочитанными, чтобы не блекли
        reminder['read'] = False if status == 'soon' else reminder['key'] in read_keys
        # "soon" таймер и due показываем всегда, read влияет только на прозрачность у due
        reminders.append(reminder)
    # Додаємо нагадування про звіт після 19:00 у будні, якщо є клієнти і звіт не відправлений
    weekday = now.weekday()  # 0 Mon ... 6 Sun
    if stats and stats.get('processed_today', 0) > 0 and not report_sent and weekday < 5 and now.hour >= 19:
        dt_local = now
        reminder = {
            'shop': 'Звітність',
            'name': '',
            'phone': '',
            'when': dt_local.strftime('%d.%m %H:%M'),
            'time_label': "щойно",
            'status': 'report',
            'kind': 'report',
            'title': 'Потрібно відправити звіт',
            'dt': dt_local,
            'dt_iso': dt_local.isoformat(),
            'eta_seconds': 0,
            'key': f"report-{dt_local.strftime('%Y%m%d')}",
        }
        reminder['read'] = reminder['key'] in read_keys
        reminders.append(reminder)
    reminders.sort(key=lambda x: x.get('dt', now), reverse=True)
    return reminders


def get_user_stats(user):
    base_qs = Client.objects.filter(owner=user)
    today_start, today_end = get_today_range()
    today_qs = base_qs.filter(created_at__gte=today_start, created_at__lt=today_end)
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
        today = timezone.localdate()

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
    today_start, today_end = get_today_range()
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

    clients_today = clients_qs.filter(created_at__gte=today_start, created_at__lt=today_end)

    user_stats = get_user_stats(request.user)
    user_points_today = user_stats['points_today']
    user_points_total = user_stats['points_total']
    processed_today = user_stats['processed_today']
    report_sent_today = has_report_today(request.user)
    reminders = get_reminders(request.user, stats=user_stats, report_sent=report_sent_today)

    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    bot_username = get_manager_bot_username()
    return render(request, 'management/home.html', {
        'grouped_clients': grouped_clients,
        'user_points_today': user_points_today,
        'user_points_total': user_points_total,
        'processed_today': processed_today,
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
        'has_report_today': report_sent_today,
        'reminders': reminders,
        'manager_bot_username': bot_username,
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
    today_start, today_end = get_today_range()
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
        user_clients_today = user_clients.filter(created_at__gte=today_start, created_at__lt=today_end)
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

    bot_username = get_manager_bot_username()
    reminders = get_reminders(request.user, stats={
        'points_today': user_points_today,
        'processed_today': processed_today,
    }, report_sent=report_sent_today)

    return render(request, 'management/admin.html', {
        'admin_user_data': admin_user_data,
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'user_points_today': user_points_today,
        'user_points_total': user_points_total,
        'processed_today': processed_today,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
        'reminders': reminders,
        'manager_bot_username': bot_username,
    })


@login_required(login_url='management_login')
def reports(request):
    if not (request.user.is_staff or Client.objects.filter(owner=request.user).exists()):
        return render(request, 'management/reports.html', {'denied': True})

    today_start, today_end = get_today_range()
    report_sent_today = has_report_today(request.user)

    qs = Report.objects.select_related('owner').order_by('-created_at')
    if not request.user.is_staff:
        qs = qs.filter(owner=request.user)

    reports_list = []
    for r in qs:
        report_day_start = timezone.localtime(r.created_at).replace(hour=0, minute=0, second=0, microsecond=0)
        report_day_end = report_day_start + timedelta(days=1)
        clients_qs = Client.objects.filter(
            owner=r.owner,
            created_at__gte=report_day_start,
            created_at__lt=report_day_end
        ).order_by('-created_at')
        clients = list(clients_qs[:100])
        # fallback: якщо записів за дату немає, але processed > 0, показуємо останніх клієнтів
        if not clients and r.processed > 0:
            fallback_limit = max(1, min(100, r.processed))
            clients = list(Client.objects.filter(owner=r.owner).order_by('-created_at')[:fallback_limit])
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
                    'role_code': c.role,
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
    bot_username = get_manager_bot_username()
    reminders = get_reminders(request.user, stats=stats, report_sent=report_sent_today)

    return render(request, 'management/reports.html', {
        'reports': reports_list,
        'user_points_today': stats['points_today'],
        'user_points_total': stats['points_total'],
        'processed_today': stats['processed_today'],
        'target_clients': TARGET_CLIENTS_DAY,
        'target_points': TARGET_POINTS_DAY,
        'progress_clients_pct': progress_clients_pct,
        'progress_points_pct': progress_points_pct,
        'has_report_today': report_sent_today,
        'reminders': reminders,
        'manager_bot_username': bot_username,
    })


@login_required(login_url='management_login')
def send_report(request):
    if request.method != 'POST':
        return redirect('management_reports')
    if not (request.user.is_staff or Client.objects.filter(owner=request.user).exists()):
        return redirect('management_reports')

    today_start, today_end = get_today_range()
    clients_today = Client.objects.filter(
        owner=request.user,
        created_at__gte=today_start,
        created_at__lt=today_end
    ).order_by('-created_at')
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


@login_required(login_url='management_login')
def reminder_read(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=400)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False}, status=400)
    key = body.get('key')
    if not key:
        return JsonResponse({'ok': False}, status=400)
    ReminderRead.objects.get_or_create(user=request.user, key=key)
    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
def reminder_feed(request):
    stats = get_user_stats(request.user)
    report_sent = has_report_today(request.user)
    reminders = get_reminders(request.user, stats=stats, report_sent=report_sent)
    _send_manager_bot_notifications(request.user, reminders)
    serialized = []
    for r in reminders:
        eta = int(r.get('eta_seconds', 0) or 0)
        if eta > 300:
            eta = 0
        serialized.append({
            'shop': r.get('shop', ''),
            'title': r.get('title', ''),
            'name': r.get('name', ''),
            'phone': r.get('phone', ''),
            'time_label': r.get('time_label', ''),
            'status': r.get('status', ''),
            'eta_seconds': eta,
            'key': r.get('key', ''),
            'read': r.get('read', False),
            'dt_iso': r.get('dt_iso', ''),
        })
    return JsonResponse({'reminders': serialized})


@login_required(login_url='management_login')
@require_POST
def profile_update(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    full_name = request.POST.get('full_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    if full_name:
        profile.full_name = full_name
    if email:
        profile.email = email
    if phone:
        profile.phone = phone
    profile.save()
    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
@require_POST
def profile_bind_code(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    code = secrets.token_hex(3)
    expires_at = timezone.now() + timedelta(minutes=10)
    profile.tg_manager_bind_code = code
    profile.tg_manager_bind_expires_at = expires_at
    profile.save()
    bot_username = get_manager_bot_username()
    return JsonResponse({
        'ok': True,
        'code': code,
        'expires': expires_at.strftime('%d.%m.%Y %H:%M'),
        'bot_username': bot_username,
    })


def _send_telegram_message(bot_token, chat_id, text):
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=5)
    except Exception:
        pass


def _send_manager_bot_notifications(user, reminders):
    """Send new reminders (<=5 мин) to manager bot."""
    if not reminders:
        return
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        return
    chat_id = profile.tg_manager_chat_id
    bot_token = os.environ.get("MANAGER_TG_BOT_TOKEN")
    if not chat_id or not bot_token:
        return
    for r in reminders:
        eta = int(r.get('eta_seconds') or 0)
        if eta == 0 and r.get('status') != 'due':
            continue
        if eta > 300:
            continue
        key = r.get('key')
        if not key:
            continue
        if ReminderSent.objects.filter(key=key, chat_id=chat_id).exists():
            continue
        when = 'зараз' if eta == 0 else (f"через {eta//60} хв {eta%60:02d} с" if eta >= 60 else f"через {eta} с")
        text = (
            "Нагадування\n"
            f"Магазин: {r.get('shop','')}\n"
            f"Клієнт: {r.get('name','')}\n"
            f"Телефон: {r.get('phone','')}\n"
            f"Коли: {when}\n"
        )
        _send_telegram_message(bot_token, chat_id, text)
        ReminderSent.objects.create(key=key, chat_id=chat_id)


@csrf_exempt
def management_bot_webhook(request, token):
    bot_token = os.environ.get("MANAGER_TG_BOT_TOKEN")
    if not bot_token or token != bot_token:
        return JsonResponse({'ok': False}, status=403)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False}, status=400)
    message = payload.get('message') or {}
    text = message.get('text', '')
    chat = message.get('chat') or {}
    from_user = message.get('from') or {}
    chat_id = chat.get('id')
    username = from_user.get('username') or ''
    if text.startswith('/start'):
        code = ''
        if ' ' in text:
            code = text.split(' ', 1)[1].strip()
        now = timezone.now()
        if code:
            profile = UserProfile.objects.filter(
                tg_manager_bind_code=code,
                tg_manager_bind_expires_at__gte=now
            ).first()
            if profile:
                profile.tg_manager_chat_id = chat_id
                profile.tg_manager_username = username
                profile.tg_manager_bind_code = ''
                profile.tg_manager_bind_expires_at = None
                profile.save()
                _send_telegram_message(bot_token, chat_id, "Готово! Бот привʼязаний. Нагадування будуть тут.")
            else:
                _send_telegram_message(bot_token, chat_id, "Код не дійсний або прострочений. Згенеруйте новий у кабінеті і натисніть 'Привʼязати бота'.")
        else:
            _send_telegram_message(bot_token, chat_id, "Не отримав код. Згенеруйте його у кабінеті й натисніть 'Привʼязати бота' або надішліть /start <код>.")
    return JsonResponse({'ok': True})
