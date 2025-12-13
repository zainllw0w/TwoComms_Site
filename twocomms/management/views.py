from collections import OrderedDict
from datetime import datetime, timedelta
import json
import time
from pathlib import Path

from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.html import escape
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse, FileResponse, HttpResponse
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST

import requests
from io import BytesIO
import datetime as dt
import os
import secrets

from .models import Client, Report, ReminderRead, ReminderSent, InvoiceRejectionReasonRequest
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


def _load_env_tokens():
    """Best-effort load bot tokens from .env.production if process env is empty (shared hosting)."""
    if os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN"):
        return
    env_path = Path(__file__).resolve().parents[2] / ".env.production"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                if not line or line.strip().startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass


_load_env_tokens()


def user_is_management(user):
    if not user.is_authenticated:
        return False
    try:
        prof = user.userprofile
        is_manager = getattr(prof, 'is_manager', False)
    except UserProfile.DoesNotExist:
        is_manager = False
    return user.is_staff or user.is_superuser or is_manager


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
        is_timer = status == 'soon' and eta_raw > 0
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
            'is_timer': is_timer,
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
    if not user_is_management(request.user):
        return redirect('management_login')
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

        if not full_name:
            full_name = 'ПІБ не вказано'

        if shop_name and phone:
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
    if not user_is_management(request.user):
        return redirect('management_login')
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

    tab = (request.GET.get('tab') or 'managers').strip().lower()
    if tab not in ('managers', 'invoices'):
        tab = 'managers'

    User = get_user_model()
    today_start, today_end = get_today_range()
    admin_user_data = []
    users = User.objects.filter(is_active=True).filter(
        Q(is_staff=True) | Q(userprofile__is_manager=True)
    ).annotate(
        total_clients=Count('management_clients', distinct=True),
        today_clients=Count('management_clients', filter=Q(management_clients__created_at__gte=today_start), distinct=True),
    ).distinct()

    stats = get_user_stats(request.user)
    user_points_today = stats['points_today']
    user_points_total = stats['points_total']
    processed_today = stats['processed_today']
    report_sent_today = has_report_today(request.user)
    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    if tab == 'managers':
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
            })

    bot_username = get_manager_bot_username()
    reminders = get_reminders(request.user, stats={
        'points_today': user_points_today,
        'processed_today': processed_today,
    }, report_sent=report_sent_today)

    ctx = {
        'admin_tab': tab,
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
    }

    if tab == 'invoices':
        from orders.models import WholesaleInvoice
        invoices_for_review = WholesaleInvoice.objects.filter(
            created_by__isnull=False,
            review_status='pending',
        ).select_related('created_by', 'created_by__userprofile').order_by('-created_at')[:200]
        ctx['invoices_for_review'] = invoices_for_review

    return render(request, 'management/admin.html', ctx)


@login_required(login_url='management_login')
@require_POST
def admin_invoice_approve_api(request, invoice_id):
    if not request.user.is_staff:
        return JsonResponse({'ok': False}, status=403)

    from orders.models import WholesaleInvoice

    invoice = WholesaleInvoice.objects.filter(id=invoice_id).first()
    if not invoice:
        return JsonResponse({'ok': False, 'error': 'Накладна не знайдена'}, status=404)

    if invoice.review_status != 'pending':
        return JsonResponse({'ok': False, 'error': 'Накладна вже оброблена'}, status=400)

    invoice.review_status = 'approved'
    invoice.review_reject_reason = ''
    invoice.reviewed_at = timezone.now()
    invoice.reviewed_by = request.user
    invoice.is_approved = True
    invoice.save(update_fields=['review_status', 'review_reject_reason', 'reviewed_at', 'reviewed_by', 'is_approved'])

    InvoiceRejectionReasonRequest.objects.filter(invoice=invoice, is_active=True).update(is_active=False)
    _try_update_admin_invoice_message(invoice, final=True)
    _notify_manager_invoice(
        invoice,
        title="✅ <b>Накладна підтверджена</b>",
        body_lines=[
            f"№: <code>{escape(invoice.invoice_number)}</code>",
            f"Компанія: {escape(invoice.company_name)}",
            "Статус: ✅ Підтверджено",
            "Далі: сформуйте посилання на оплату у вкладці накладних.",
        ],
    )

    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
@require_POST
def admin_invoice_reject_api(request, invoice_id):
    if not request.user.is_staff:
        return JsonResponse({'ok': False}, status=403)

    import json
    from orders.models import WholesaleInvoice

    invoice = WholesaleInvoice.objects.filter(id=invoice_id).first()
    if not invoice:
        return JsonResponse({'ok': False, 'error': 'Накладна не знайдена'}, status=404)

    if invoice.review_status != 'pending':
        return JsonResponse({'ok': False, 'error': 'Накладна вже оброблена'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    reason = (payload.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'ok': False, 'error': 'Вкажіть причину відхилення'}, status=400)

    invoice.review_status = 'rejected'
    invoice.review_reject_reason = reason
    invoice.reviewed_at = timezone.now()
    invoice.reviewed_by = request.user
    invoice.is_approved = False
    invoice.payment_url = None
    invoice.monobank_invoice_id = None
    invoice.save(update_fields=[
        'review_status',
        'review_reject_reason',
        'reviewed_at',
        'reviewed_by',
        'is_approved',
        'payment_url',
        'monobank_invoice_id',
    ])

    InvoiceRejectionReasonRequest.objects.filter(invoice=invoice, is_active=True).update(is_active=False)
    _try_update_admin_invoice_message(invoice, final=True)
    _notify_manager_invoice(
        invoice,
        title="❌ <b>Накладна відхилена</b>",
        body_lines=[
            f"№: <code>{escape(invoice.invoice_number)}</code>",
            f"Компанія: {escape(invoice.company_name)}",
            f"Причина: {escape(reason)}",
        ],
    )

    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
def admin_user_clients(request, user_id):
    """AJAX: список клієнтів обраного менеджера для модалки 'Огляд'."""
    if not request.user.is_staff:
        return JsonResponse({'ok': False}, status=403)

    User = get_user_model()
    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'ok': False}, status=404)

    try:
        offset = int(request.GET.get('offset', '0'))
    except ValueError:
        offset = 0
    try:
        limit = int(request.GET.get('limit', '50'))
    except ValueError:
        limit = 50

    offset = max(0, offset)
    limit = max(1, min(200, limit))

    query = (request.GET.get('q') or '').strip()

    qs = Client.objects.filter(owner=target).order_by('-created_at')
    if query:
        qs = qs.filter(
            Q(shop_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(full_name__icontains=query)
        )

    total = qs.count()
    page = list(qs[offset:offset + limit])

    now = timezone.localtime(timezone.now())
    today = now.date()
    yesterday = today - timedelta(days=1)

    clients = []
    for c in page:
        created_local = timezone.localtime(c.created_at) if c.created_at else now
        if created_local.date() == today:
            created_label = 'Сьогодні'
        elif created_local.date() == yesterday:
            created_label = 'Вчора'
        else:
            created_label = created_local.strftime('%d.%m.%Y')

        next_call_label = '–'
        next_call_status = 'none'
        if c.next_call_at:
            next_local = timezone.localtime(c.next_call_at)
            next_call_label = next_local.strftime('%d.%m.%Y %H:%M')
            delta = (next_local - now).total_seconds()
            if delta <= 0:
                next_call_status = 'due'
            elif delta <= 300:
                next_call_status = 'soon'
            else:
                next_call_status = 'scheduled'

        clients.append({
            'id': c.id,
            'shop': c.shop_name,
            'phone': c.phone,
            'full_name': c.full_name,
            'role_code': c.role,
            'role': c.get_role_display(),
            'source': c.source or '',
            'result_code': c.call_result,
            'result': c.get_call_result_display(),
            'details': c.call_result_details or '',
            'points': POINTS.get(c.call_result, 0),
            'next_call': next_call_label,
            'next_call_status': next_call_status,
            'created': created_local.strftime('%d.%m.%Y %H:%M'),
            'created_date_label': created_label,
        })

    has_more = offset + limit < total
    return JsonResponse({
        'ok': True,
        'total': total,
        'offset': offset,
        'limit': limit,
        'has_more': has_more,
        'clients': clients,
    })


@login_required(login_url='management_login')
def reports(request):
    if not user_is_management(request.user):
        return redirect('management_home')
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
    if not user_is_management(request.user):
        return redirect('management_home')
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
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)
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
    if not user_is_management(request.user):
        return JsonResponse({'reminders': []})
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
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)
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
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)
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


def _tg_api_post(bot_token, method, payload, *, as_json=True, timeout=10):
    if not bot_token:
        return None
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        if as_json:
            resp = requests.post(url, json=payload, timeout=timeout)
        else:
            resp = requests.post(url, data=payload, timeout=timeout)
        return resp.json()
    except Exception:
        return None


def _tg_send_message(bot_token, chat_id, text, *, reply_markup=None, parse_mode='HTML'):
    if not bot_token or not chat_id:
        return None
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    data = _tg_api_post(bot_token, 'sendMessage', payload, as_json=True)
    if data and data.get('ok'):
        return data.get('result')
    return None


def _tg_edit_message(bot_token, chat_id, message_id, text, *, reply_markup=None, parse_mode='HTML'):
    if not bot_token or not chat_id or not message_id:
        return None
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    data = _tg_api_post(bot_token, 'editMessageText', payload, as_json=True)
    if data and data.get('ok'):
        return data.get('result')
    return None


def _tg_answer_callback(bot_token, callback_query_id, text=''):
    if not bot_token or not callback_query_id:
        return None
    payload = {'callback_query_id': callback_query_id}
    if text:
        payload['text'] = text
        payload['show_alert'] = False
    return _tg_api_post(bot_token, 'answerCallbackQuery', payload, as_json=True)


def _get_management_admin_bot_config():
    token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN") or os.environ.get("MANAGER_TG_BOT_TOKEN")
    chat_id = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID")
    return token, chat_id


def _get_manager_bot_token():
    return os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN")


def _format_admin_invoice_message(invoice, *, status_line=None, include_links=True):
    manager_name = ""
    if getattr(invoice, 'created_by', None):
        manager_name = invoice.created_by.get_full_name() or invoice.created_by.username
    company_name = escape(invoice.company_name or '')
    company_number = escape(invoice.company_number or '—')
    phone = escape(invoice.contact_phone or '—')
    address = escape(invoice.delivery_address or '—')
    amount = escape(str(invoice.total_amount))
    tshirts = invoice.total_tshirts or 0
    hoodies = invoice.total_hoodies or 0

    lines = [
        "🧾 <b>Накладна на перевірку</b>",
        "",
        f"<b>№</b>: <code>{escape(invoice.invoice_number)}</code>",
        f"<b>Менеджер</b>: {escape(manager_name) if manager_name else '—'}",
        f"<b>Компанія</b>: {company_name}",
        f"<b>ЄДРПОУ/ІПН</b>: {company_number}",
        f"<b>Телефон</b>: {phone}",
        f"<b>Адреса</b>: {address}",
        f"<b>Сума</b>: {amount} грн",
        f"<b>Футболки</b>: {tshirts} • <b>Худі</b>: {hoodies}",
    ]
    if status_line:
        lines += ["", status_line]

    if include_links:
        lines += [
            "",
            f"🌐 Адмін-панель: <a href=\"https://management.twocomms.shop/admin-panel/?tab=invoices\">відкрити</a>",
            f"📥 Excel: <a href=\"https://management.twocomms.shop/invoices/{invoice.id}/download/\">скачати</a>",
        ]

    return "\n".join(lines)


def _notify_manager_invoice(invoice, *, title, body_lines):
    try:
        manager = invoice.created_by
        profile = manager.userprofile
    except Exception:
        return
    chat_id = getattr(profile, 'tg_manager_chat_id', None)
    bot_token = _get_manager_bot_token()
    if not bot_token or not chat_id:
        return
    text = "\n".join([title, *body_lines])
    _tg_send_message(bot_token, chat_id, text, parse_mode='HTML')


def _try_update_admin_invoice_message(invoice, *, bot_token=None, final=False):
    if not invoice.admin_tg_chat_id or not invoice.admin_tg_message_id:
        return
    token = bot_token or (os.environ.get("MANAGEMENT_TG_BOT_TOKEN") or os.environ.get("MANAGER_TG_BOT_TOKEN"))
    if not token:
        return
    status_line = None
    if invoice.review_status == 'approved':
        status_line = "✅ <b>ПІДТВЕРДЖЕНО</b>"
    elif invoice.review_status == 'rejected':
        reason = escape((invoice.review_reject_reason or '').strip() or '—')
        status_line = f"❌ <b>ВІДХИЛЕНО</b>\n<b>Причина</b>: {reason}"
    elif invoice.review_status == 'pending':
        status_line = "⏳ <b>НА ПЕРЕВІРЦІ</b>"
    else:
        status_line = None

    text = _format_admin_invoice_message(invoice, status_line=status_line, include_links=True)
    reply_markup = {'inline_keyboard': []} if final else None
    _tg_edit_message(token, invoice.admin_tg_chat_id, invoice.admin_tg_message_id, text, reply_markup=reply_markup, parse_mode='HTML')


def _send_invoice_review_request_to_admin(invoice, *, request=None):
    token, chat_id = _get_management_admin_bot_config()
    if not token or not chat_id:
        return
    try:
        chat_id_int = int(chat_id)
    except Exception:
        return

    text = _format_admin_invoice_message(invoice, status_line="Оберіть дію нижче ⬇️", include_links=True)
    keyboard = {
        'inline_keyboard': [[
            {'text': '✅ Підтвердити', 'callback_data': f'inv:approve:{invoice.id}'},
            {'text': '❌ Відхилити', 'callback_data': f'inv:reject:{invoice.id}'},
        ]]
    }
    sent = _tg_send_message(token, chat_id_int, text, reply_markup=keyboard, parse_mode='HTML')
    if sent and sent.get('message_id'):
        invoice.admin_tg_chat_id = chat_id_int
        invoice.admin_tg_message_id = sent.get('message_id')
        invoice.save(update_fields=['admin_tg_chat_id', 'admin_tg_message_id'])


def _send_manager_bot_notifications(user, reminders):
    """Send new reminders (<=5 мин) to manager bot."""
    if not reminders:
        return
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        return
    chat_id = profile.tg_manager_chat_id
    bot_token = os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN")
    if not chat_id or not bot_token:
        return
    for r in reminders:
        eta = int(r.get('eta_seconds') or 0)
        status = r.get('status')
        if eta == 0 and status not in ('due', 'report'):
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
    manager_token = os.environ.get("MANAGER_TG_BOT_TOKEN")
    admin_token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN")
    valid_tokens = {t for t in (manager_token, admin_token) if t}
    if not valid_tokens or token not in valid_tokens:
        return JsonResponse({'ok': False}, status=403)
    bot_token = token
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    # ==================== CALLBACK QUERIES (ADMIN INVOICE REVIEW) ====================
    callback = payload.get('callback_query')
    if callback:
        cb_id = callback.get('id')
        data = (callback.get('data') or '').strip()
        msg = callback.get('message') or {}
        msg_chat = msg.get('chat') or {}
        chat_id = msg_chat.get('id')
        message_id = msg.get('message_id')

        admin_chat_cfg = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID")
        if admin_chat_cfg and str(chat_id) != str(admin_chat_cfg):
            _tg_answer_callback(bot_token, cb_id, "Недостатньо прав")
            return JsonResponse({'ok': True})

        if not data.startswith('inv:') or ':' not in data:
            _tg_answer_callback(bot_token, cb_id, "Невідома дія")
            return JsonResponse({'ok': True})

        parts = data.split(':', 2)
        if len(parts) != 3:
            _tg_answer_callback(bot_token, cb_id, "Невідома дія")
            return JsonResponse({'ok': True})

        action = parts[1]
        try:
            invoice_id = int(parts[2])
        except Exception:
            _tg_answer_callback(bot_token, cb_id, "Невірний ID")
            return JsonResponse({'ok': True})

        from orders.models import WholesaleInvoice
        invoice = WholesaleInvoice.objects.filter(id=invoice_id).select_related('created_by', 'created_by__userprofile').first()
        if not invoice:
            _tg_answer_callback(bot_token, cb_id, "Накладна не знайдена")
            return JsonResponse({'ok': True})

        # Persist message reference for later sync (site actions)
        if chat_id and message_id and (not invoice.admin_tg_chat_id or not invoice.admin_tg_message_id):
            invoice.admin_tg_chat_id = chat_id
            invoice.admin_tg_message_id = message_id
            invoice.save(update_fields=['admin_tg_chat_id', 'admin_tg_message_id'])

        if invoice.review_status != 'pending':
            _tg_answer_callback(bot_token, cb_id, "Вже оброблено")
            _try_update_admin_invoice_message(invoice, bot_token=bot_token, final=True)
            return JsonResponse({'ok': True})

        if action == 'approve':
            invoice.review_status = 'approved'
            invoice.review_reject_reason = ''
            invoice.reviewed_at = timezone.now()
            invoice.reviewed_by = None
            invoice.is_approved = True
            invoice.save(update_fields=['review_status', 'review_reject_reason', 'reviewed_at', 'reviewed_by', 'is_approved'])
            InvoiceRejectionReasonRequest.objects.filter(invoice=invoice, is_active=True).update(is_active=False)
            _try_update_admin_invoice_message(invoice, bot_token=bot_token, final=True)
            _notify_manager_invoice(
                invoice,
                title="✅ <b>Накладна підтверджена</b>",
                body_lines=[
                    f"№: <code>{escape(invoice.invoice_number)}</code>",
                    f"Компанія: {escape(invoice.company_name)}",
                    "Статус: ✅ Підтверджено",
                    "Далі: сформуйте посилання на оплату у вкладці накладних.",
                ],
            )
            _tg_answer_callback(bot_token, cb_id, "Підтверджено")
            return JsonResponse({'ok': True})

        if action == 'reject':
            InvoiceRejectionReasonRequest.objects.filter(admin_chat_id=chat_id, is_active=True).update(is_active=False)
            req = InvoiceRejectionReasonRequest.objects.create(invoice=invoice, admin_chat_id=chat_id, is_active=True)

            # Update original message: remove buttons and mark waiting reason
            waiting_text = _format_admin_invoice_message(invoice, status_line="✍️ <b>Очікую причину відхилення</b>", include_links=True)
            _tg_edit_message(bot_token, chat_id, message_id, waiting_text, reply_markup={'inline_keyboard': []}, parse_mode='HTML')

            prompt = _tg_send_message(
                bot_token,
                chat_id,
                f"❌ <b>Відхилення накладної</b> <code>{escape(invoice.invoice_number)}</code>\n\nНапишіть причину одним повідомленням.",
                reply_markup={'force_reply': True, 'input_field_placeholder': 'Причина відхилення…'},
                parse_mode='HTML',
            )
            if prompt and prompt.get('message_id'):
                req.prompt_message_id = prompt.get('message_id')
                req.save(update_fields=['prompt_message_id'])

            _tg_answer_callback(bot_token, cb_id, "Вкажіть причину")
            return JsonResponse({'ok': True})

        _tg_answer_callback(bot_token, cb_id, "Невідома дія")
        return JsonResponse({'ok': True})

    # ==================== MESSAGES ====================
    message = payload.get('message') or {}
    text = (message.get('text') or '').strip()
    chat = message.get('chat') or {}
    from_user = message.get('from') or {}
    chat_id = chat.get('id')
    username = from_user.get('username') or ''

    # Admin: rejection reason flow
    if chat_id and text and not text.startswith('/'):
        active_req = InvoiceRejectionReasonRequest.objects.select_related('invoice').filter(
            admin_chat_id=chat_id,
            is_active=True
        ).first()
        if active_req:
            invoice = active_req.invoice
            active_req.is_active = False
            active_req.save(update_fields=['is_active'])

            if invoice and invoice.review_status == 'pending':
                reason = text.strip()
                invoice.review_status = 'rejected'
                invoice.review_reject_reason = reason
                invoice.reviewed_at = timezone.now()
                invoice.reviewed_by = None
                invoice.is_approved = False
                invoice.payment_url = None
                invoice.monobank_invoice_id = None
                invoice.save(update_fields=[
                    'review_status',
                    'review_reject_reason',
                    'reviewed_at',
                    'reviewed_by',
                    'is_approved',
                    'payment_url',
                    'monobank_invoice_id',
                ])
                _try_update_admin_invoice_message(invoice, bot_token=bot_token, final=True)
                _notify_manager_invoice(
                    invoice,
                    title="❌ <b>Накладна відхилена</b>",
                    body_lines=[
                        f"№: <code>{escape(invoice.invoice_number)}</code>",
                        f"Компанія: {escape(invoice.company_name)}",
                        f"Причина: {escape(reason)}",
                    ],
                )
                _tg_send_message(bot_token, chat_id, "Готово ✅ Накладну відхилено.", parse_mode='HTML')
            else:
                _tg_send_message(bot_token, chat_id, "Накладна вже оброблена або недоступна.", parse_mode='HTML')
            return JsonResponse({'ok': True})

    # Manager bot binding
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


def _get_wholesale_products_for_invoice():
    from django.db.models import Q
    from storefront.models import Product, Category

    tshirt_categories = Category.objects.filter(
        Q(name__icontains='футболка') |
        Q(name__icontains='tshirt') |
        Q(name__icontains='t-shirt') |
        Q(slug__icontains='футболка') |
        Q(slug__icontains='tshirt') |
        Q(slug__icontains='t-shirt')
    )
    hoodie_categories = Category.objects.filter(
        Q(name__icontains='худи') |
        Q(name__icontains='hoodie') |
        Q(name__icontains='hooded') |
        Q(slug__icontains='худи') |
        Q(slug__icontains='hoodie') |
        Q(slug__icontains='hooded')
    )

    tshirt_products = Product.objects.filter(category__in=tshirt_categories).select_related('category').prefetch_related(
        'color_variants__color',
        'color_variants__images',
    )
    hoodie_products = Product.objects.filter(category__in=hoodie_categories).select_related('category').prefetch_related(
        'color_variants__color',
        'color_variants__images',
    )
    return tshirt_products, hoodie_products


def _get_wholesale_price_context():
    tshirt_prices = {
        'drop': 570,
        'wholesale': [540, 520, 500, 490, 480],
        'ranges': ['8–15 шт.', '16–31 шт.', '32–63 шт.', '64–99 шт.', '100+ шт.']
    }
    hoodie_prices = {
        'drop': 1350,
        'wholesale': [1300, 1250, 1200, 1175, 1150],
        'ranges': ['8–15 шт.', '16–31 шт.', '32–63 шт.', '64–99 шт.', '100+ шт.']
    }
    return tshirt_prices, hoodie_prices


@login_required(login_url='management_login')
def invoices(request):
    if not user_is_management(request.user):
        return redirect('management_login')

    from orders.models import WholesaleInvoice

    try:
        tshirt_products, hoodie_products = _get_wholesale_products_for_invoice()
    except Exception:
        tshirt_products, hoodie_products = [], []

    tshirt_prices, hoodie_prices = _get_wholesale_price_context()

    qs = WholesaleInvoice.objects.filter(created_by=request.user).order_by('-created_at')
    last_invoice = qs.first()
    company_data = {
        'company_name': getattr(last_invoice, 'company_name', '') if last_invoice else '',
        'company_number': getattr(last_invoice, 'company_number', '') if last_invoice else '',
        'delivery_address': getattr(last_invoice, 'delivery_address', '') if last_invoice else '',
        'phone_number': getattr(last_invoice, 'contact_phone', '') if last_invoice else '',
        'store_link': getattr(last_invoice, 'store_link', '') if last_invoice else '',
    }
    tshirt_count = tshirt_products.count() if hasattr(tshirt_products, 'count') else len(tshirt_products)
    hoodie_count = hoodie_products.count() if hasattr(hoodie_products, 'count') else len(hoodie_products)
    user_invoice_stats = {
        'total_invoices': qs.count(),
        'last_invoice_date': timezone.localtime(last_invoice.created_at).strftime('%d.%m.%Y %H:%M') if last_invoice else 'Немає накладних',
        'total_products_available': tshirt_count + hoodie_count,
        'tshirt_count': tshirt_count,
        'hoodie_count': hoodie_count,
    }

    stats = get_user_stats(request.user)
    report_sent_today = has_report_today(request.user)
    progress_clients_pct = min(100, int(stats['processed_today'] / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(stats['points_today'] / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0
    bot_username = get_manager_bot_username()
    reminders = get_reminders(request.user, stats=stats, report_sent=report_sent_today)

    return render(request, 'management/invoices.html', {
        'tshirt_products': tshirt_products,
        'hoodie_products': hoodie_products,
        'tshirt_prices': tshirt_prices,
        'hoodie_prices': hoodie_prices,
        'company_data': company_data,
        'user_invoice_stats': user_invoice_stats,
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
def invoices_list_api(request):
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)

    from orders.models import WholesaleInvoice

    invoices = WholesaleInvoice.objects.filter(created_by=request.user).order_by('-created_at')[:200]
    data = []
    for inv in invoices:
        data.append({
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'company_name': inv.company_name,
            'company_number': inv.company_number,
            'contact_phone': inv.contact_phone,
            'delivery_address': inv.delivery_address,
            'store_link': inv.store_link,
            'total_amount': float(inv.total_amount),
            'total_tshirts': inv.total_tshirts,
            'total_hoodies': inv.total_hoodies,
            'created_at': timezone.localtime(inv.created_at).strftime('%d.%m.%Y %H:%M') if inv.created_at else '',
            'status': inv.status,
            'status_display': inv.get_status_display(),
            'review_status': inv.review_status,
            'review_status_display': inv.get_review_status_display(),
            'review_reject_reason': inv.review_reject_reason,
            'is_approved': inv.is_approved,
            'payment_status': inv.payment_status,
            'payment_url': inv.payment_url,
        })
    return JsonResponse({'ok': True, 'invoices': data})


@login_required(login_url='management_login')
@require_POST
def invoices_generate_api(request):
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)

    import json
    import os
    import pytz
    import secrets
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.conf import settings
    from orders.models import WholesaleInvoice

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Невірний формат даних'}, status=400)

    company_data = payload.get('companyData') or {}
    order_items = payload.get('orderItems') or []

    company_name = (company_data.get('companyName') or '').strip()
    contact_phone = (company_data.get('contactPhone') or '').strip()
    delivery_address = (company_data.get('deliveryAddress') or '').strip()
    if not company_name or not contact_phone or not delivery_address:
        return JsonResponse({'ok': False, 'error': 'Заповніть: назву компанії, телефон та адресу доставки'}, status=400)

    if not order_items:
        return JsonResponse({'ok': False, 'error': 'Немає товарів для накладної'}, status=400)

    kiev_tz = pytz.timezone('Europe/Kiev')
    now = timezone.now().astimezone(kiev_tz)
    timestamp = now.strftime('%Y%m%d_%H%M%S')
    nonce = secrets.token_hex(2).upper()
    invoice_number = f"МЕН_{timestamp}_{nonce}"

    safe_company = company_name or 'Company'
    beautiful_date = now.strftime('%d.%m.%Y_%H-%M')
    file_name = f"{safe_company}_накладнаОПТ_{beautiful_date}.xlsx"

    total_tshirts = 0
    total_hoodies = 0
    total_amount = 0

    wb = Workbook()
    ws = wb.active
    ws.title = "Оптова накладна"

    header_font = Font(name='Arial', size=14, bold=True, color='FFFFFF')
    title_font = Font(name='Arial', size=12, bold=True)
    normal_font = Font(name='Arial', size=10)
    company_font = Font(name='Arial', size=11, bold=True, color='366092')

    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    light_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    company_fill = PatternFill(start_color='E8F4FD', end_color='E8F4FD', fill_type='solid')

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    center_alignment = Alignment(horizontal='center', vertical='center')
    left_alignment = Alignment(horizontal='left', vertical='center')
    right_alignment = Alignment(horizontal='right', vertical='center')

    ws.merge_cells('A1:G1')
    ws['A1'] = 'ОПТОВА НАКЛАДНА'
    ws['A1'].font = Font(name='Arial', size=16, bold=True, color='366092')
    ws['A1'].alignment = center_alignment
    ws['A1'].fill = company_fill

    row = 3
    ws[f'A{row}'] = 'Інформація про замовника:'
    ws[f'A{row}'].font = title_font

    row += 1
    ws[f'A{row}'] = 'Назва компанії/ФОП/ПІБ:'
    ws[f'A{row}'].font = normal_font
    ws[f'B{row}'] = company_name
    ws[f'B{row}'].font = company_font
    ws[f'B{row}'].fill = company_fill

    if (company_data.get('companyNumber') or '').strip():
        row += 1
        ws[f'A{row}'] = 'Номер компанії/ЄДРПОУ/ІПН:'
        ws[f'A{row}'].font = normal_font
        ws[f'B{row}'] = (company_data.get('companyNumber') or '').strip()
        ws[f'B{row}'].font = normal_font

    row += 1
    ws[f'A{row}'] = 'Номер телефону:'
    ws[f'A{row}'].font = normal_font
    ws[f'B{row}'] = contact_phone
    ws[f'B{row}'].font = normal_font

    row += 1
    ws[f'A{row}'] = 'Адреса доставки:'
    ws[f'A{row}'].font = normal_font
    ws[f'B{row}'] = delivery_address
    ws[f'B{row}'].font = normal_font

    store_link = (company_data.get('storeLink') or '').strip()
    if store_link:
        row += 1
        ws[f'A{row}'] = 'Посилання на магазин:'
        ws[f'A{row}'].font = normal_font
        ws[f'B{row}'] = store_link
        ws[f'B{row}'].font = normal_font

    row += 2
    ws[f'A{row}'] = f'Номер накладної: {invoice_number}'
    ws[f'A{row}'].font = title_font

    row += 1
    ws[f'A{row}'] = f'Дата створення: {now.strftime("%d.%m.%Y о %H:%M")}'
    ws[f'A{row}'].font = normal_font

    row += 2
    headers = ['№', 'Назва товару', 'Розмір', 'Колір', 'Кількість', 'Ціна за од.', 'Сума']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
        cell.border = thin_border

    item_number = 1
    row += 1
    for item in order_items:
        product = item.get('product', {}) or {}
        quantity = int(item.get('quantity', 0) or 0)
        price = float(item.get('price', 0) or 0)
        total = float(item.get('total', 0) or 0)

        if product.get('type') == 'tshirt':
            total_tshirts += quantity
        elif product.get('type') == 'hoodie':
            total_hoodies += quantity
        total_amount += total

        ws.cell(row=row, column=1, value=item_number).font = normal_font
        ws.cell(row=row, column=1).alignment = center_alignment
        ws.cell(row=row, column=1).border = thin_border

        ws.cell(row=row, column=2, value=product.get('title', '')).font = normal_font
        ws.cell(row=row, column=2).alignment = left_alignment
        ws.cell(row=row, column=2).border = thin_border

        ws.cell(row=row, column=3, value=item.get('size', '')).font = normal_font
        ws.cell(row=row, column=3).alignment = center_alignment
        ws.cell(row=row, column=3).border = thin_border

        ws.cell(row=row, column=4, value=item.get('color', '')).font = normal_font
        ws.cell(row=row, column=4).alignment = center_alignment
        ws.cell(row=row, column=4).border = thin_border

        ws.cell(row=row, column=5, value=quantity).font = normal_font
        ws.cell(row=row, column=5).alignment = center_alignment
        ws.cell(row=row, column=5).border = thin_border

        ws.cell(row=row, column=6, value=f"{price}₴").font = normal_font
        ws.cell(row=row, column=6).alignment = center_alignment
        ws.cell(row=row, column=6).border = thin_border

        ws.cell(row=row, column=7, value=f"{total}₴").font = normal_font
        ws.cell(row=row, column=7).alignment = center_alignment
        ws.cell(row=row, column=7).border = thin_border

        if item_number % 2 == 0:
            for col in range(1, 8):
                ws.cell(row=row, column=col).fill = light_fill

        item_number += 1
        row += 1

    row += 1
    ws.merge_cells(f'A{row}:F{row}')
    ws[f'A{row}'] = 'РАЗОМ:'
    ws[f'A{row}'].font = title_font
    ws[f'A{row}'].alignment = right_alignment
    ws[f'A{row}'].border = thin_border
    ws[f'A{row}'].fill = company_fill

    ws[f'G{row}'] = f"{total_amount}₴"
    ws[f'G{row}'].font = title_font
    ws[f'G{row}'].alignment = center_alignment
    ws[f'G{row}'].border = thin_border
    ws[f'G{row}'].fill = company_fill

    row += 2
    ws[f'A{row}'] = 'Статистика замовлення:'
    ws[f'A{row}'].font = title_font

    row += 1
    ws[f'A{row}'] = f'Футболки: {total_tshirts} шт.'
    ws[f'A{row}'].font = normal_font

    row += 1
    ws[f'A{row}'] = f'Худі: {total_hoodies} шт.'
    ws[f'A{row}'].font = normal_font

    row += 1
    ws[f'A{row}'] = f'Загальна сума: {total_amount}₴'
    ws[f'A{row}'].font = title_font

    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        adjusted_width = max(max_length + 2, 12)
        adjusted_width = min(adjusted_width, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    invoice = WholesaleInvoice.objects.create(
        invoice_number=invoice_number,
        company_name=company_name,
        company_number=(company_data.get('companyNumber') or '').strip(),
        contact_phone=contact_phone,
        delivery_address=delivery_address,
        store_link=store_link,
        total_tshirts=total_tshirts,
        total_hoodies=total_hoodies,
        total_amount=total_amount,
        status='draft',
        created_by=request.user,
        review_status='draft',
        order_details={'company_data': company_data, 'order_items': order_items},
    )

    user_folder = f"invoices/management/user_{request.user.id}"
    invoice_dir = os.path.join(settings.MEDIA_ROOT, user_folder)
    os.makedirs(invoice_dir, exist_ok=True)
    file_path = os.path.join(invoice_dir, file_name)
    wb.save(file_path)

    invoice.file_path = file_path
    invoice.save(update_fields=['file_path'])

    return JsonResponse({
        'ok': True,
        'invoice': {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'company_name': invoice.company_name,
            'total_amount': float(invoice.total_amount),
            'total_tshirts': invoice.total_tshirts,
            'total_hoodies': invoice.total_hoodies,
            'created_at': timezone.localtime(invoice.created_at).strftime('%d.%m.%Y %H:%M'),
            'review_status': invoice.review_status,
            'review_status_display': invoice.get_review_status_display(),
            'payment_status': invoice.payment_status,
            'payment_url': invoice.payment_url,
        }
    })


@login_required(login_url='management_login')
def invoices_download(request, invoice_id):
    if not user_is_management(request.user):
        return redirect('management_login')

    from orders.models import WholesaleInvoice
    import os

    invoice = WholesaleInvoice.objects.filter(id=invoice_id).first()
    if not invoice:
        return HttpResponse('Накладна не знайдена', status=404)

    if not (request.user.is_staff or invoice.created_by_id == request.user.id):
        return HttpResponse('Доступ заборонено', status=403)

    if not invoice.file_path or not os.path.exists(invoice.file_path):
        return HttpResponse('Файл накладної не знайдено', status=404)

    filename = os.path.basename(invoice.file_path)
    return FileResponse(open(invoice.file_path, 'rb'), as_attachment=True, filename=filename)


@login_required(login_url='management_login')
@require_POST
def invoices_delete_api(request, invoice_id):
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)

    from orders.models import WholesaleInvoice
    import os

    invoice = WholesaleInvoice.objects.filter(id=invoice_id, created_by=request.user).first()
    if not invoice:
        return JsonResponse({'ok': False, 'error': 'Накладна не знайдена'}, status=404)

    if invoice.review_status == 'pending' or invoice.payment_status == 'paid':
        return JsonResponse({'ok': False, 'error': 'Накладну не можна видалити в цьому статусі'}, status=400)

    try:
        if invoice.file_path and os.path.isabs(invoice.file_path) and os.path.exists(invoice.file_path):
            os.remove(invoice.file_path)
    except Exception:
        pass

    invoice.delete()
    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
@require_POST
def invoices_submit_for_review_api(request, invoice_id):
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)

    from orders.models import WholesaleInvoice

    invoice = WholesaleInvoice.objects.filter(id=invoice_id, created_by=request.user).first()
    if not invoice:
        return JsonResponse({'ok': False, 'error': 'Накладна не знайдена'}, status=404)

    if invoice.review_status != 'draft':
        return JsonResponse({'ok': False, 'error': 'Накладна вже відправлена або оброблена'}, status=400)

    invoice.review_status = 'pending'
    invoice.review_reject_reason = ''
    invoice.reviewed_at = None
    invoice.reviewed_by = None
    invoice.is_approved = False
    invoice.payment_url = None
    invoice.monobank_invoice_id = None
    invoice.status = 'pending'
    invoice.save(update_fields=[
        'review_status',
        'review_reject_reason',
        'reviewed_at',
        'reviewed_by',
        'is_approved',
        'payment_url',
        'monobank_invoice_id',
        'status',
    ])

    _send_invoice_review_request_to_admin(invoice, request=request)
    _notify_manager_invoice(
        invoice,
        title="📤 <b>Накладна відправлена на перевірку</b>",
        body_lines=[
            f"№: <code>{escape(invoice.invoice_number)}</code>",
            f"Компанія: {escape(invoice.company_name)}",
            "Статус: ⏳ На перевірці",
        ],
    )

    return JsonResponse({'ok': True})


@login_required(login_url='management_login')
@require_POST
def invoices_create_payment_api(request, invoice_id):
    if not user_is_management(request.user):
        return JsonResponse({'ok': False}, status=403)

    from decimal import Decimal
    import json
    from orders.models import WholesaleInvoice
    from storefront.views.monobank import _monobank_api_request, MonobankAPIError

    invoice = WholesaleInvoice.objects.filter(id=invoice_id, created_by=request.user).first()
    if not invoice:
        return JsonResponse({'ok': False, 'error': 'Накладна не знайдена'}, status=404)

    if invoice.payment_status == 'paid':
        return JsonResponse({'ok': False, 'error': 'Накладна вже оплачена'}, status=400)

    if invoice.review_status != 'approved' or not invoice.is_approved:
        return JsonResponse({'ok': False, 'error': 'Накладна ще не підтверджена адміністратором'}, status=400)

    if invoice.payment_url:
        return JsonResponse({'ok': True, 'payment_url': invoice.payment_url, 'monobank_invoice_id': invoice.monobank_invoice_id})

    try:
        amount_decimal = Decimal(str(invoice.total_amount))
        if amount_decimal <= 0:
            return JsonResponse({'ok': False, 'error': 'Невірна сума накладної'}, status=400)
        amount_kopecks = int(amount_decimal * 100)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Невірна сума накладної'}, status=400)

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = {}

    destination = (body.get('description') or '').strip() or f'Оплата накладної {invoice.invoice_number}'
    payload = {
        'amount': amount_kopecks,
        'ccy': 980,
        'merchantPaymInfo': {
            'reference': f'MGMT-INV-{invoice.id}',
            'destination': destination,
            'basketOrder': [
                {
                    'name': f'Накладна {invoice.invoice_number}',
                    'qty': 1,
                    'sum': amount_kopecks,
                    'icon': '',
                    'unit': 'шт',
                }
            ]
        },
    }

    try:
        creation_data = _monobank_api_request('POST', '/api/merchant/invoice/create', json_payload=payload)
    except MonobankAPIError as exc:
        return JsonResponse({'ok': False, 'error': f'Помилка створення платежу: {str(exc)}'}, status=500)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Помилка створення платежу'}, status=500)

    payment_url = creation_data.get('invoiceUrl') or creation_data.get('pageUrl')
    monobank_invoice_id = creation_data.get('invoiceId') or creation_data.get('invoice_id')
    if not payment_url:
        return JsonResponse({'ok': False, 'error': 'Не отримано URL для оплати'}, status=500)

    invoice.payment_status = 'pending'
    invoice.payment_url = payment_url
    invoice.monobank_invoice_id = monobank_invoice_id
    invoice.save(update_fields=['payment_status', 'payment_url', 'monobank_invoice_id'])

    return JsonResponse({'ok': True, 'payment_url': payment_url, 'monobank_invoice_id': monobank_invoice_id})
