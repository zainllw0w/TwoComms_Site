"""Рушій «Фінансового здоров'я» — багатошарова чесна оцінка.

Замість одного декоративного score рахуємо 4 шари:
  • Business Health   — здоров'я бізнесу (ліквідність, прибуток, cash flow,
                        робочий капітал, прогноз, борги, якість даних);
  • Personal Health   — особистий контур власника (подушка, free cash flow,
                        боргове навантаження, lifestyle);
  • Boundary Health   — чистота межі бізнес/особисте (owner draw, змішування);
  • Portfolio Health  — підсумок власника (агрегат перших трьох під cap'ами).

Підсумок проходить через:
  • critical caps (критичні блокери не дають високого score);
  • data confidence cap (неповні дані ріжуть максимум);
і завжди супроводжується lost points (чому не 100), critical alerts і
рекомендаціями з очікуваним cash/score impact.

Дані беруться з тих самих транзакцій/рахунків/магазинів/складу, що й решта
кабінету (єдине джерело правди). Все деградує безпечно: відсутність модулів
складу/магазинів не валить розрахунок.

Адаптовано під TwoComms: ФОП-рахунки (is_business=True) = бізнес-контур,
особисті картки (is_business=False) = особистий контур, борг магазинів
(consignment) = дебіторка, собівартість складу = заморожений капітал.
"""
from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal
from collections import OrderedDict

from django.db.models import Sum
from django.utils import timezone

from ..models import Account, Transaction
from . import balances as balance_service
from .timeutil import day_end, day_start


ZERO = Decimal('0')


# ===========================================================================
# Нормалізатори (мапінг метрики у 0..100)
# ===========================================================================

def score_higher_better(value, bad, good) -> float:
    """Чим більше — тим краще. value<=bad → 0, value>=good → 100."""
    value = float(value)
    bad = float(bad)
    good = float(good)
    if good == bad:
        return 100.0 if value >= good else 0.0
    if value <= bad:
        return 0.0
    if value >= good:
        return 100.0
    return 100.0 * (value - bad) / (good - bad)


def score_lower_better(value, good, bad) -> float:
    """Чим менше — тим краще. value<=good → 100, value>=bad → 0."""
    value = float(value)
    good = float(good)
    bad = float(bad)
    if bad == good:
        return 100.0 if value <= good else 0.0
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return 100.0 * (bad - value) / (bad - good)


def score_target_range(value, low_bad, low_good, high_good, high_bad) -> float:
    """Цільовий діапазон: погано і занизько, і зависоко."""
    value = float(value)
    if value < low_good:
        return score_higher_better(value, low_bad, low_good)
    if value > high_good:
        return score_lower_better(value, high_good, high_bad)
    return 100.0


def _f(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ===========================================================================
# Збір сирих метрик
# ===========================================================================

def _month_bounds(today):
    start = today.replace(day=1)
    last = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last)
    return start, end


def _prev_months(today, n):
    """Список (start, end) для n попередніх повних місяців (старіші → новіші)."""
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        last = calendar.monthrange(y, m)[1]
        out.append((dt.date(y, m, 1), dt.date(y, m, last)))
    return list(reversed(out))


def _sum(qs, field='amount_base'):
    return qs.aggregate(s=Sum(field))['s'] or ZERO


def gather_metrics(company) -> dict:
    """Збирає всі сирі фінансові метрики для розрахунку score."""
    today = timezone.localdate()
    month_start, month_end = _month_bounds(today)

    actual = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)
              .exclude(excluded_from_reports=True))
    actual_noxfer = actual.exclude(type=Transaction.TYPE_TRANSFER)

    # ---------- Рахунки / cash ----------
    business_accounts = company.accounts.filter(is_active=True, is_archived=False, is_business=True)
    personal_accounts = company.accounts.filter(is_active=True, is_archived=False, is_business=False)
    total_cash = balance_service.total_actual_balance(company)
    business_cash = ZERO
    for a in business_accounts:
        from . import currency as cur_svc
        business_cash += cur_svc.convert(company, a.current_balance, a.currency)
    personal_cash = ZERO
    for a in personal_accounts:
        from . import currency as cur_svc
        personal_cash += cur_svc.convert(company, a.current_balance, a.currency)

    # ---------- Бізнес P&L поточного місяця ----------
    biz_month = actual_noxfer.filter(is_business=True,
                                     date_actual__gte=day_start(month_start),
                                     date_actual__lte=day_end(month_end))
    biz_income_m = _sum(biz_month.filter(type=Transaction.TYPE_INCOME))
    biz_expense_m = _sum(biz_month.filter(type=Transaction.TYPE_EXPENSE))
    biz_profit_m = biz_income_m - biz_expense_m

    # ---------- Бізнес по 6 попередніх місяцях (тренди, середні) ----------
    monthly_profit = []
    monthly_revenue = []
    monthly_expense = []
    for (s, e) in _prev_months(today, 6):
        mqs = actual_noxfer.filter(is_business=True,
                                   date_actual__gte=day_start(s), date_actual__lte=day_end(e))
        inc = _sum(mqs.filter(type=Transaction.TYPE_INCOME))
        exp = _sum(mqs.filter(type=Transaction.TYPE_EXPENSE))
        monthly_revenue.append(inc)
        monthly_expense.append(exp)
        monthly_profit.append(inc - exp)

    # Середньомісячні витрати бізнесу (для runway). Беремо середнє по непорожніх.
    nonzero_exp = [x for x in monthly_expense if x > 0]
    avg_monthly_expense = (sum(nonzero_exp, ZERO) / len(nonzero_exp)) if nonzero_exp else biz_expense_m
    if avg_monthly_expense <= 0:
        avg_monthly_expense = biz_expense_m

    nonzero_rev = [x for x in monthly_revenue if x > 0]
    avg_monthly_revenue = (sum(nonzero_rev, ZERO) / len(nonzero_rev)) if nonzero_rev else biz_income_m

    # ---------- Особисті витрати/доходи місяця ----------
    pers_month = actual_noxfer.filter(is_business=False,
                                      date_actual__gte=day_start(month_start),
                                      date_actual__lte=day_end(month_end))
    personal_income_m = _sum(pers_month.filter(type=Transaction.TYPE_INCOME))
    personal_expense_m = _sum(pers_month.filter(type=Transaction.TYPE_EXPENSE))

    # ---------- Розбір особистих витрат: житло, продукти, needs/wants ----------
    # Класифікуємо особисті витрати за назвою категорії (ключові слова), щоб
    # окремо бачити найважливіші статті: оренда житла та продукти. Для власника
    # бізнесу це найбільші фіксовані витрати, тож аналізуємо їх окремо.
    personal_essentials = _personal_essentials_breakdown(
        pers_month.filter(type=Transaction.TYPE_EXPENSE), personal_expense_m)

    # Середні особисті витрати за 6 міс.
    pers_monthly_exp = []
    for (s, e) in _prev_months(today, 6):
        pqs = actual_noxfer.filter(is_business=False, type=Transaction.TYPE_EXPENSE,
                                   date_actual__gte=day_start(s), date_actual__lte=day_end(e))
        pers_monthly_exp.append(_sum(pqs))
    nonzero_pers = [x for x in pers_monthly_exp if x > 0]
    avg_personal_expense = (sum(nonzero_pers, ZERO) / len(nonzero_pers)) if nonzero_pers else personal_expense_m

    # ---------- Дебіторка: борг магазинів + планові доходи ----------
    receivables_total = ZERO
    overdue_receivables = ZERO
    ar_aging = {'not_due': ZERO, 'd0_30': ZERO, 'd31_60': ZERO, 'd61_90': ZERO, 'd90_plus': ZERO}
    try:
        from . import consignment as cons
        receivables_total += cons.resellers_debt_total(company)
    except Exception:
        pass
    # Планові income (дебіторка) з aging за датою.
    planned_income = (Transaction.objects.filter(
        company=company, status=Transaction.STATUS_PLANNED, type=Transaction.TYPE_INCOME)
        .exclude(excluded_from_reports=True))
    for t in planned_income:
        amt = t.amount_base or t.amount or ZERO
        receivables_total += amt
        due = t.date_actual.date() if t.date_actual else None
        if due is None:
            ar_aging['not_due'] += amt
            continue
        overdue_days = (today - due).days
        if overdue_days <= 0:
            ar_aging['not_due'] += amt
        elif overdue_days <= 30:
            ar_aging['d0_30'] += amt
            overdue_receivables += amt
        elif overdue_days <= 60:
            ar_aging['d31_60'] += amt
            overdue_receivables += amt
        elif overdue_days <= 90:
            ar_aging['d61_90'] += amt
            overdue_receivables += amt
        else:
            ar_aging['d90_plus'] += amt
            overdue_receivables += amt

    # ---------- Кредиторка: планові витрати ----------
    payables_total = ZERO
    payables_30d = ZERO
    horizon_30 = today + dt.timedelta(days=30)
    planned_expense = (Transaction.objects.filter(
        company=company, status=Transaction.STATUS_PLANNED, type=Transaction.TYPE_EXPENSE)
        .exclude(excluded_from_reports=True))
    for t in planned_expense:
        amt = t.amount_base or t.amount or ZERO
        payables_total += amt
        due = t.date_actual.date() if t.date_actual else None
        if due and due <= horizon_30:
            payables_30d += amt

    # ---------- Склад (заморожений капітал) ----------
    inventory_value = ZERO
    try:
        from . import warehouse_link
        inventory_value = warehouse_link.frozen_in_warehouse()
    except Exception:
        pass
    try:
        from . import consignment as cons
        inventory_value += cons.consignment_frozen_total(company)
    except Exception:
        pass

    # ---------- Прогноз 30 днів (мінімальний cash) ----------
    forecast_30_min = _forecast_min_cash(company, total_cash, days=30)

    # ---------- Owner draw (перекази ФОП → особиста картка) ----------
    owner_draw_m = _owner_draw_month(company, month_start, month_end)

    # ---------- Якість даних ----------
    dq = _data_quality(company, actual_noxfer, business_accounts, personal_accounts)

    # ---------- Boundary: змішування ----------
    boundary = _boundary_metrics(company, actual_noxfer, today)

    # Прибуткові місяці поспіль (для caps).
    loss_streak = 0
    for p in reversed(monthly_profit):
        if p < 0:
            loss_streak += 1
        else:
            break

    return {
        'today': today,
        'total_cash': total_cash,
        'business_cash': business_cash,
        'personal_cash': personal_cash,
        'biz_income_m': biz_income_m,
        'biz_expense_m': biz_expense_m,
        'biz_profit_m': biz_profit_m,
        'monthly_profit': monthly_profit,
        'monthly_revenue': monthly_revenue,
        'monthly_expense': monthly_expense,
        'avg_monthly_expense': avg_monthly_expense,
        'avg_monthly_revenue': avg_monthly_revenue,
        'loss_streak': loss_streak,
        'personal_income_m': personal_income_m,
        'personal_expense_m': personal_expense_m,
        'avg_personal_expense': avg_personal_expense,
        'personal_essentials': personal_essentials,
        'receivables_total': receivables_total,
        'overdue_receivables': overdue_receivables,
        'ar_aging': ar_aging,
        'payables_total': payables_total,
        'payables_30d': payables_30d,
        'inventory_value': inventory_value,
        'forecast_30_min': forecast_30_min,
        'owner_draw_m': owner_draw_m,
        'has_personal_accounts': personal_accounts.exists(),
        'has_business_accounts': business_accounts.exists(),
        'data_quality': dq,
        'boundary': boundary,
    }


def _forecast_min_cash(company, current_cash, days=30):
    """Мінімальний прогнозований cash на горизонті (день за днем).

    Враховує планові доходи (з вірогідністю 0.9 для not-overdue, 0.6 для overdue)
    та планові витрати (повністю). Повертає найнижчу точку балансу.
    """
    today = timezone.localdate()
    horizon = today + dt.timedelta(days=days)
    planned = (Transaction.objects.filter(
        company=company, status=Transaction.STATUS_PLANNED,
        date_actual__lte=day_end(horizon))
        .exclude(excluded_from_reports=True)
        .exclude(type=Transaction.TYPE_TRANSFER)
        .order_by('date_actual'))
    running = Decimal(current_cash)
    min_cash = running
    for t in planned:
        amt = t.amount_base or t.amount or ZERO
        if t.type == Transaction.TYPE_INCOME:
            # Дисконтуємо ймовірність надходження.
            due = t.date_actual.date() if t.date_actual else today
            prob = Decimal('0.6') if due < today else Decimal('0.9')
            running += amt * prob
        elif t.type == Transaction.TYPE_EXPENSE:
            running -= amt
        if running < min_cash:
            min_cash = running
    return min_cash


def _owner_draw_month(company, month_start, month_end):
    """Виводи власника за місяць: перекази з бізнес-рахунку на особистий."""
    today = timezone.localdate()
    transfers = (Transaction.objects.filter(
        company=company, status=Transaction.STATUS_ACTUAL, type=Transaction.TYPE_TRANSFER,
        date_actual__gte=day_start(month_start), date_actual__lte=day_end(month_end))
        .select_related('account', 'to_account'))
    total = ZERO
    for t in transfers:
        src = t.account
        dst = t.to_account
        if src and dst and src.is_business and not dst.is_business:
            total += t.amount_base or t.amount or ZERO
    return total


# Ключові слова категорій для класифікації особистих витрат.
_HOUSING_KW = ('оренд', 'житл', 'квартир', 'комунал', 'коммунал', 'rent', 'аренд',
               'іпотек', 'ипотек', 'mortgage', 'електроенерг', 'газ', 'опаленн')
_GROCERY_KW = ('продукт', 'їжа', 'еда', 'groceries', 'супермаркет', 'магазин продукт',
               'food', 'харчуванн', 'продукти')
# «Wants» (бажання) — дискреційні витрати, які можна оптимізувати.
_WANTS_KW = ('ресторан', 'кафе', 'розваг', 'розвлеч', 'подорож', 'travel', 'кіно',
             'бар', 'алкогол', 'тютюн', 'підписк', 'subscription', 'ігри', 'хобі',
             'краса', 'салон', 'shopping', 'одяг', 'взуття')


def _personal_essentials_breakdown(expense_qs, total_personal):
    """Розбиває особисті витрати на ключові статті за назвою категорії.

    Повертає суми: housing (житло/оренда/комуналка), groceries (продукти),
    wants (дискреційні), other; + частки від загальних особистих витрат.
    Класифікація за ключовими словами категорії — наближена, але дає корисний
    зріз найважливіших статей (житло й продукти — найбільші для більшості).
    """
    housing = groceries = wants = ZERO
    for row in expense_qs.values('category__name').annotate(s=Sum('amount_base')):
        name = (row['category__name'] or '').lower()
        amt = row['s'] or ZERO
        if any(k in name for k in _HOUSING_KW):
            housing += amt
        elif any(k in name for k in _GROCERY_KW):
            groceries += amt
        elif any(k in name for k in _WANTS_KW):
            wants += amt
    total = total_personal or ZERO
    other = total - housing - groceries - wants
    if other < 0:
        other = ZERO

    def _share(v):
        return float(v / total * 100) if total > 0 else 0.0

    return {
        'housing': housing, 'housing_share': _share(housing),
        'groceries': groceries, 'groceries_share': _share(groceries),
        'wants': wants, 'wants_share': _share(wants),
        'other': other, 'other_share': _share(other),
    }


def _data_quality(company, actual_noxfer, business_accounts, personal_accounts):
    """Метрики повноти даних (для data confidence)."""
    today = timezone.localdate()
    recent_start = today - dt.timedelta(days=90)
    recent = actual_noxfer.filter(date_actual__gte=day_start(recent_start))

    total_count = recent.count()
    total_amount = abs(_f(_sum(recent)))

    categorized_count = recent.filter(category__isnull=False).count()
    categorized_amount = abs(_f(_sum(recent.filter(category__isnull=False))))

    cp_count = recent.filter(counterparty__isnull=False).count()

    cat_share_count = (categorized_count / total_count) if total_count else 1.0
    cat_share_amount = (categorized_amount / total_amount) if total_amount else 1.0
    cp_share = (cp_count / total_count) if total_count else 1.0

    has_personal = personal_accounts.exists()
    has_business = business_accounts.exists()
    account_coverage = 1.0
    if not has_business:
        account_coverage -= 0.5
    if not has_personal:
        account_coverage -= 0.3
    account_coverage = max(0.0, account_coverage)

    # Чи є хоч якісь особисті витрати (інакше особистий контур неповний).
    personal_has_activity = actual_noxfer.filter(
        is_business=False, date_actual__gte=day_start(recent_start)).exists()

    # Data Confidence (зважена).
    confidence = (
        0.35 * cat_share_amount +
        0.20 * cat_share_count +
        0.20 * cp_share +
        0.15 * account_coverage +
        0.10 * (1.0 if personal_has_activity else 0.0)
    )
    confidence = max(0.0, min(1.0, confidence))

    return {
        'total_count': total_count,
        'categorized_share_count': cat_share_count,
        'categorized_share_amount': cat_share_amount,
        'counterparty_share': cp_share,
        'account_coverage': account_coverage,
        'has_personal_accounts': has_personal,
        'has_business_accounts': has_business,
        'personal_has_activity': personal_has_activity,
        'confidence': confidence,
        'uncategorized_count': total_count - categorized_count,
    }


def _boundary_metrics(company, actual_noxfer, today):
    """Метрики чистоти межі бізнес/особисте за останні 90 днів."""
    recent_start = today - dt.timedelta(days=90)
    recent = actual_noxfer.filter(date_actual__gte=day_start(recent_start))

    total_amount = abs(_f(_sum(recent)))
    # Особисті витрати з бізнес-рахунку (змішування).
    personal_from_business = recent.filter(
        is_business=False, account__is_business=True, type=Transaction.TYPE_EXPENSE)
    pfb_amount = abs(_f(_sum(personal_from_business)))
    # Бізнес-витрати з особистого рахунку.
    business_from_personal = recent.filter(
        is_business=True, account__is_business=False)
    bfp_amount = abs(_f(_sum(business_from_personal)))

    mixed_amount = pfb_amount + bfp_amount
    mixed_share = (mixed_amount / total_amount) if total_amount else 0.0

    return {
        'mixed_amount': Decimal(str(mixed_amount)),
        'mixed_share': mixed_share,
        'personal_from_business': Decimal(str(pfb_amount)),
        'business_from_personal': Decimal(str(bfp_amount)),
    }


# ===========================================================================
# Шари здоров'я
# ===========================================================================

def _weighted(parts):
    """parts = [(score0_100, weight), ...] → зважене середнє 0..100."""
    total_w = sum(w for _, w in parts)
    if total_w <= 0:
        return 100.0
    return sum(s * w for s, w in parts) / total_w


def business_health(m) -> dict:
    """Business Health: ліквідність, прибуток, cash flow, робочий капітал,
    прогноз, борги, якість даних."""
    lost = []
    cash = m['business_cash'] if m['business_cash'] > 0 else m['total_cash']
    avg_exp = m['avg_monthly_expense']

    # 1. Ліквідність / runway (вага 20).
    runway = float(cash / avg_exp) if avg_exp > 0 else (6.0 if cash > 0 else 0.0)
    s_runway = score_higher_better(runway, 0.5, 4.0)
    if s_runway < 70:
        lost.append(('business', 'runway', round((100 - s_runway) * 0.20 / 100 * 20),
                     f'Запас ходу ~{runway:.1f} міс. (ціль ≥3–4 міс.)'))

    # 2. Прибутковість (вага 18).
    profit = m['biz_profit_m']
    revenue = m['biz_income_m']
    margin = float(profit / revenue * 100) if revenue > 0 else 0.0
    if revenue <= 0 and m['avg_monthly_revenue'] <= 0:
        s_profit = 30.0  # немає виручки = невідома прибутковість
        lost.append(('business', 'profitability', 9, 'Немає підтвердженої виручки за місяць'))
    elif profit < 0:
        s_profit = score_higher_better(margin, -30, 0)
        lost.append(('business', 'profitability', 9, f'Збиток за місяць ({margin:.0f}% маржі)'))
    else:
        s_profit = score_higher_better(margin, 0, 25)
        if s_profit < 70:
            lost.append(('business', 'margin', round((100 - s_profit) * 0.18 / 100 * 18),
                         f'Низька маржа {margin:.0f}% (ціль ≥20%)'))

    # 3. Якість cash flow (вага 17) — чи перетворюється прибуток у гроші.
    # Проксі: позитивний прибуток + позитивний баланс.
    if profit > 0 and cash > 0:
        s_cashflow = 90.0
    elif cash > 0:
        s_cashflow = 60.0
    else:
        s_cashflow = 20.0
        lost.append(('business', 'cashflow', 8, 'Від\'ємний бізнес-баланс'))

    # 4. Робочий капітал (вага 15): дебіторка + склад не мають душити.
    ar_to_cash = float(m['receivables_total'] / cash) if cash > 0 else 5.0
    s_ar = score_lower_better(ar_to_cash, 0.5, 2.0)
    inv_to_exp = float(m['inventory_value'] / avg_exp) if avg_exp > 0 else 0.0
    s_inv = score_lower_better(inv_to_exp, 1.0, 4.0)
    s_wc = (s_ar + s_inv) / 2
    if s_ar < 60:
        lost.append(('business', 'receivables', 6,
                     f'Дебіторка ~{ar_to_cash:.1f}× від доступного cash'))
    if s_inv < 60:
        lost.append(('business', 'inventory', 4,
                     f'У складі заморожено ~{inv_to_exp:.1f}× міс. витрат'))

    # 5. Прогноз / план-факт (вага 10).
    if m['forecast_30_min'] < 0:
        s_forecast = 10.0
        lost.append(('business', 'forecast', 6, 'Прогнозний касовий розрив у 30 днів'))
    elif m['forecast_30_min'] < m['avg_monthly_expense'] * Decimal('0.5'):
        s_forecast = 55.0
        lost.append(('business', 'forecast', 3, 'Тонкий запас cash у прогнозі на 30 днів'))
    else:
        s_forecast = 90.0

    # 6. Борги / зобов'язання (вага 8).
    pay_to_cash = float(m['payables_30d'] / cash) if cash > 0 else 2.0
    s_debt = score_lower_better(pay_to_cash, 0.3, 1.0)
    if s_debt < 60:
        lost.append(('business', 'payables', 3, 'Великі найближчі зобов\'язання відносно cash'))

    # 7. Якість даних (вага 12).
    s_dq = m['data_quality']['confidence'] * 100
    if s_dq < 80:
        lost.append(('business', 'data', round((100 - s_dq) * 0.12 / 100 * 12),
                     'Неповна категоризація/контрагенти'))

    score = _weighted([
        (s_runway, 20), (s_profit, 18), (s_cashflow, 17), (s_wc, 15),
        (s_forecast, 10), (s_debt, 8), (s_dq, 12),
    ])
    return {
        'score': round(score),
        'lost': lost,
        'metrics': {
            'runway_months': round(runway, 1),
            'margin': round(margin, 1),
            'ar_to_cash': round(ar_to_cash, 2),
            'inventory_to_expense': round(inv_to_exp, 2),
        },
        'subscores': {
            'liquidity': round(s_runway), 'profitability': round(s_profit),
            'cashflow': round(s_cashflow), 'working_capital': round(s_wc),
            'forecast': round(s_forecast), 'debt': round(s_debt), 'data': round(s_dq),
        },
    }


def personal_health(m) -> dict:
    """Personal Health: подушка, free cash flow, lifestyle. Якщо контур
    порожній — incomplete (не excellent)."""
    lost = []
    dq = m['data_quality']
    incomplete = not dq['personal_has_activity'] or not dq['has_personal_accounts']

    cash = m['personal_cash']
    essential = m['avg_personal_expense']
    # Емоційна подушка (місяців).
    emergency_months = float(cash / essential) if essential > 0 else (3.0 if cash > 0 else 0.0)
    s_cushion = score_higher_better(emergency_months, 0.5, 6.0)
    if s_cushion < 70:
        lost.append(('personal', 'emergency_fund', 7,
                     f'Особиста подушка ~{emergency_months:.1f} міс. (ціль ≥3)'))

    # Особистий free cash flow.
    pfcf = m['personal_income_m'] - m['personal_expense_m']
    if m['personal_income_m'] > 0:
        pfcf_rate = float(pfcf / m['personal_income_m'] * 100)
        s_fcf = score_higher_better(pfcf_rate, -10, 30)
    else:
        s_fcf = 50.0
    if s_fcf < 60:
        lost.append(('personal', 'free_cash_flow', 5, 'Особистий free cash flow низький/від\'ємний'))

    # Lifestyle: особисті витрати vs бізнес-дохід.
    if m['biz_income_m'] > 0:
        pers_ratio = float(m['personal_expense_m'] / m['biz_income_m'] * 100)
        s_lifestyle = score_lower_better(pers_ratio, 30, 80)
        if s_lifestyle < 60:
            lost.append(('personal', 'lifestyle', 4,
                         f'Особисті витрати {pers_ratio:.0f}% від бізнес-доходу'))
    else:
        s_lifestyle = 60.0

    if incomplete:
        lost.append(('personal', 'incomplete', 6,
                     'Особистий контур неповний (немає особистих рахунків/операцій)'))

    score = _weighted([(s_cushion, 35), (s_fcf, 30), (s_lifestyle, 20),
                       (100.0 if not incomplete else 40.0, 15)])

    # Частка житла (оренда + комуналка) у особистих витратах і відносно доходу.
    ess = m.get('personal_essentials') or {}
    housing = ess.get('housing', ZERO)
    housing_ratio_income = (float(housing / m['personal_income_m'] * 100)
                            if m['personal_income_m'] > 0 else 0.0)
    housing_share = float(ess.get('housing_share', 0.0))
    # Норма витрат на житло — до 30–35% доходу. Вище — тисне на бюджет.
    if m['personal_income_m'] > 0 and housing_ratio_income > 35:
        lost.append(('personal', 'housing', 3,
                     f'Житло з\'їдає {housing_ratio_income:.0f}% особистого доходу (норма ≤30%)'))

    # Норма заощаджень (savings rate) — частка вільного потоку від доходу.
    savings_rate = (float(pfcf / m['personal_income_m'] * 100)
                    if m['personal_income_m'] > 0 else 0.0)

    return {
        'score': round(score),
        'incomplete': incomplete,
        'lost': lost,
        'metrics': {
            'emergency_months': round(emergency_months, 1),
            'personal_fcf': float(pfcf),
            'savings_rate': round(savings_rate, 1),
            'housing': float(housing),
            'housing_ratio_income': round(housing_ratio_income, 1),
            'housing_share': round(housing_share, 1),
            'groceries': float(ess.get('groceries', ZERO)),
            'groceries_share': round(float(ess.get('groceries_share', 0.0)), 1),
            'wants_share': round(float(ess.get('wants_share', 0.0)), 1),
        },
        'subscores': {
            'cushion': round(s_cushion), 'free_cash_flow': round(s_fcf),
            'lifestyle': round(s_lifestyle),
        },
    }


def boundary_health(m) -> dict:
    """Boundary Health: чистота межі + owner draw дисципліна."""
    lost = []
    b = m['boundary']
    mixed_share = b['mixed_share']
    s_mixed = score_lower_better(mixed_share * 100, 2, 10)
    if s_mixed < 70:
        lost.append(('boundary', 'mixed', round((100 - s_mixed) * 0.40 / 100 * 40),
                     f'Змішано бізнес/особисте: {mixed_share * 100:.1f}% обороту'))

    # Owner draw дисципліна: чи виводить власник, але не вимиває оборотку.
    draw = m['owner_draw_m']
    avg_exp = m['avg_monthly_expense']
    if draw <= 0:
        s_draw = 60.0  # не платить собі — нейтрально-погано
    else:
        draw_ratio = float(draw / avg_exp) if avg_exp > 0 else 0.0
        # Здорово якщо виводи помірні відносно витрат.
        s_draw = score_lower_better(draw_ratio, 0.5, 2.0)
        if s_draw < 50:
            lost.append(('boundary', 'owner_draw', 3,
                         'Великі виводи власника відносно витрат — ризик вимивання оборотки'))

    # Reimbursements: бізнес-витрати з особистої картки (борг бізнесу власнику).
    if b['business_from_personal'] > 0:
        s_reimb = 60.0
    else:
        s_reimb = 90.0

    score = _weighted([(s_mixed, 40), (s_draw, 30), (s_reimb, 20),
                       (90.0, 10)])
    return {
        'score': round(score),
        'lost': lost,
        'metrics': {
            'mixed_share': round(mixed_share * 100, 1),
            'owner_draw_month': float(draw),
        },
        'subscores': {'separation': round(s_mixed), 'owner_draw': round(s_draw),
                      'reimbursements': round(s_reimb)},
    }


# ===========================================================================
# Caps та підсумок
# ===========================================================================

def compute_caps(m, biz, pers, bound) -> list:
    """Критичні обмеження максимального score (повертає список cap'ів)."""
    caps = []
    dq = m['data_quality']
    conf = dq['confidence']

    # Data confidence caps.
    if conf < 0.50:
        caps.append({'type': 'data_confidence', 'cap': 49,
                     'reason': 'Дуже низька довіра до даних (<50%)'})
    elif conf < 0.70:
        caps.append({'type': 'data_confidence', 'cap': 69,
                     'reason': 'Низька довіра до даних (<70%)'})
    elif conf < 0.85:
        caps.append({'type': 'data_confidence', 'cap': 84,
                     'reason': 'Неповні дані (довіра <85%)'})

    if dq['categorized_share_amount'] < 0.80:
        caps.append({'type': 'categorization', 'cap': 59,
                     'reason': 'Категоризовано менше 80% обороту'})

    # Прогнозний касовий розрив.
    if m['forecast_30_min'] < 0:
        caps.append({'type': 'forecast_gap', 'cap': 59,
                     'reason': 'Прогнозний касовий розрив у найближчі 30 днів'})

    # Runway < 0.5 міс.
    cash = m['business_cash'] if m['business_cash'] > 0 else m['total_cash']
    if m['avg_monthly_expense'] > 0 and float(cash / m['avg_monthly_expense']) < 0.5:
        caps.append({'type': 'cash_reserve', 'cap': 59,
                     'reason': 'Запас cash менше 0.5 місяця витрат'})

    # Збиток 2 місяці поспіль.
    if m['loss_streak'] >= 2:
        caps.append({'type': 'losses', 'cap': 69,
                     'reason': f'Збиток {m["loss_streak"]} місяці поспіль'})

    # Дебіторка 90+.
    ar_total = m['receivables_total']
    if ar_total > 0:
        share_90 = float(m['ar_aging']['d90_plus'] / ar_total)
        if share_90 > 0.15:
            caps.append({'type': 'ar_90', 'cap': 59,
                         'reason': f'Прострочена дебіторка 90+ становить {share_90 * 100:.0f}%'})
        overdue_share = float(m['overdue_receivables'] / ar_total)
        if overdue_share > 0.30:
            caps.append({'type': 'ar_overdue', 'cap': 69,
                         'reason': f'Прострочено {overdue_share * 100:.0f}% дебіторки'})

    # Negative total cash.
    if m['total_cash'] < 0:
        caps.append({'type': 'negative_cash', 'cap': 39,
                     'reason': 'Від\'ємний загальний баланс'})

    # Mixed share > 10%.
    if bound['metrics']['mixed_share'] > 10:
        caps.append({'type': 'boundary', 'cap': 69,
                     'reason': 'Бізнес і особисте сильно змішані (>10%)'})

    # Особиста подушка < 1 міс.
    if not pers['incomplete'] and pers['metrics']['emergency_months'] < 1:
        caps.append({'type': 'personal_cushion', 'cap': 74,
                     'reason': 'Особиста подушка менше 1 місяця'})

    return caps


def calculate_health(company) -> dict:
    """Головна функція: повертає повний результат score engine."""
    m = gather_metrics(company)
    biz = business_health(m)
    pers = personal_health(m)
    bound = boundary_health(m)

    portfolio_raw = (0.60 * biz['score'] + 0.25 * pers['score'] + 0.15 * bound['score'])

    caps = compute_caps(m, biz, pers, bound)
    cap_value = min([c['cap'] for c in caps], default=100)
    portfolio_final = min(round(portfolio_raw), cap_value)
    portfolio_final = max(0, min(100, portfolio_final))

    # Lost points — агрегуємо з усіх шарів, сортуємо за вагою.
    lost_points = []
    for layer in (biz, pers, bound):
        for (scope, metric, points, reason) in layer['lost']:
            if points > 0:
                lost_points.append({'scope': scope, 'metric': metric,
                                    'points': points, 'reason': reason})
    lost_points.sort(key=lambda x: x['points'], reverse=True)

    # Critical alerts.
    alerts = _build_alerts(m, caps)

    # Рекомендації.
    from . import health_advisor
    recommendations = health_advisor.build_recommendations(m, biz, pers, bound)

    # Label.
    label, status_class = _label(portfolio_final)

    return {
        'period': {'today': m['today'].isoformat()},
        'scores': {
            'business': biz['score'],
            'personal': pers['score'],
            'boundary': bound['score'],
            'portfolio_raw': round(portfolio_raw),
            'portfolio_final': portfolio_final,
            'data_confidence': round(m['data_quality']['confidence'] * 100),
            'label': label,
            'status_class': status_class,
        },
        'personal_incomplete': pers['incomplete'],
        'caps': caps,
        'lost_points': lost_points,
        'critical_alerts': alerts,
        'recommendations': recommendations,
        'metrics': m,
        'layer_metrics': {
            'business': biz['metrics'], 'personal': pers['metrics'], 'boundary': bound['metrics'],
        },
        'subscores': {
            'business': biz['subscores'], 'personal': pers['subscores'], 'boundary': bound['subscores'],
        },
    }


def _label(score):
    if score >= 85:
        return 'Відмінно', 'excellent'
    if score >= 70:
        return 'Стабільно', 'good'
    if score >= 55:
        return 'Потрібна увага', 'fair'
    if score >= 40:
        return 'Зона ризику', 'warn'
    return 'Критично', 'poor'


def _build_alerts(m, caps):
    alerts = []
    if m['forecast_30_min'] < 0:
        alerts.append({
            'severity': 'critical',
            'title': 'Можливий касовий розрив',
            'message': f'У найближчі 30 днів прогнозний мінімум балансу '
                       f'{m["forecast_30_min"]:.0f} ₴. Перегляньте графік платежів.',
        })
    if m['receivables_total'] > 0 and m['overdue_receivables'] > 0:
        alerts.append({
            'severity': 'high',
            'title': 'Прострочена дебіторка',
            'message': f'Прострочено {m["overdue_receivables"]:.0f} ₴ від магазинів/контрагентів.',
        })
    if not m['data_quality']['personal_has_activity']:
        alerts.append({
            'severity': 'medium',
            'title': 'Особистий контур неповний',
            'message': 'Немає особистих операцій — оцінка особистого здоров\'я неточна.',
        })
    if m['loss_streak'] >= 2:
        alerts.append({
            'severity': 'high',
            'title': 'Збитковість',
            'message': f'Бізнес збитковий {m["loss_streak"]} місяці поспіль.',
        })
    return alerts
