/* TwoComms Finance — модалка push-звітів (deep-link).
   Відкриває збережений звіт повідомлення у красивій модалці:
   • ?fin_report=<id> в URL (клік по push, що відкрив сторінку);
   • повідомлення OPEN_REPORT від Service Worker (коли вкладка вже відкрита).
   Рендер за report_data.kind: daily / weekly / debts / health / planned.
*/
(function () {
    'use strict';

    var modal, backdrop, bodyEl, titleEl, dateEl, eyebrowEl, ackBtn;
    var currentId = null;

    document.addEventListener('DOMContentLoaded', function () {
        modal = document.getElementById('fin-report-modal');
        if (!modal) return;
        backdrop = document.getElementById('fin-report-backdrop');
        bodyEl = document.getElementById('fin-report-body');
        titleEl = document.getElementById('fin-report-title');
        dateEl = document.getElementById('fin-report-date');
        eyebrowEl = document.getElementById('fin-report-eyebrow');
        ackBtn = document.getElementById('fin-report-ack');

        var closeBtn = document.getElementById('fin-report-close');
        var dismissBtn = document.getElementById('fin-report-dismiss');
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (dismissBtn) dismissBtn.addEventListener('click', close);
        if (backdrop) backdrop.addEventListener('click', close);
        if (ackBtn) ackBtn.addEventListener('click', acknowledge);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) close();
        });

        // Deep-link із URL.
        var params = new URLSearchParams(window.location.search);
        var rid = params.get('fin_report');
        if (rid) {
            openReport(rid);
            // Прибираємо параметр, щоб перезавантаження не відкривало знову.
            params.delete('fin_report');
            var qs = params.toString();
            var clean = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
            window.history.replaceState({}, '', clean);
        }

        // Повідомлення від Service Worker (вкладка вже відкрита).
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', function (event) {
                if (event.data && event.data.type === 'OPEN_REPORT' && event.data.reportId) {
                    openReport(event.data.reportId);
                }
            });
        }
    });

    function openReport(id) {
        currentId = id;
        showLoading();
        open();
        fetch('/api/notifications/' + id + '/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.success) { renderError(); return; }
                render(data);
            })
            .catch(renderError);
    }

    function open() {
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('fin-report-open');
        requestAnimationFrame(function () { modal.classList.add('is-open'); });
    }

    function close() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('fin-report-open');
        setTimeout(function () { modal.hidden = true; }, 260);
        currentId = null;
    }

    function showLoading() {
        bodyEl.innerHTML = '<div class="fin-report-modal__loading">Завантаження звіту…</div>';
    }

    function renderError() {
        bodyEl.innerHTML = '<div class="fin-report-empty">Не вдалося завантажити звіт. '
            + 'Можливо, він застарів.</div>';
    }

    function acknowledge() {
        if (!currentId) { close(); return; }
        ackBtn.disabled = true;
        fetch('/api/notifications/' + currentId + '/ack/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        }).then(function () {}).catch(function () {}).finally(function () {
            ackBtn.disabled = false;
            close();
        });
    }

    // ===== Рендер =====
    function render(payload) {
        var rep = payload.report || {};
        var kind = rep.kind || payload.type || 'custom';
        eyebrowEl.textContent = eyebrowFor(kind);
        titleEl.textContent = payload.title || 'Фінансовий звіт';
        dateEl.textContent = rep.date_label || rep.period_label || '';
        modal.setAttribute('data-kind', kind);

        if (kind === 'daily') bodyEl.innerHTML = renderDaily(rep);
        else if (kind === 'weekly') bodyEl.innerHTML = renderWeekly(rep);
        else if (kind === 'debts') bodyEl.innerHTML = renderDebts(rep);
        else if (kind === 'health') bodyEl.innerHTML = renderHealth(rep);
        else if (kind === 'planned') bodyEl.innerHTML = renderPlanned(rep);
        else bodyEl.innerHTML = '<p class="fin-report-text">' + esc(payload.body || '') + '</p>';
    }

    function eyebrowFor(kind) {
        return {
            daily: 'Щоденний звіт', weekly: 'Тижневий звіт', debts: 'Борги',
            health: 'Фінансовий ризик', planned: 'Планові платежі'
        }[kind] || 'Звіт';
    }

    // --- Daily ---
    function renderDaily(r) {
        var html = '';
        html += '<div class="fin-rstat-grid">'
            + stat('Дохід', r.income_display, 'pos')
            + stat('Витрати', r.expense_display, 'neg')
            + stat('Заробіток', r.profit_display, (r.profit >= 0 ? 'pos' : 'neg'))
            + stat('Баланс', r.balance_display, 'neutral')
            + '</div>';

        html += '<div class="fin-rmeta">'
            + '<span>' + (r.ops_count || 0) + ' операц.</span>'
            + (r.transfers_count ? '<span>' + r.transfers_count + ' переказ.</span>' : '')
            + '</div>';

        if (r.top_expenses && r.top_expenses.length) {
            html += section('Найбільші витрати дня', listRows(r.top_expenses, 'category', 'amount_display', 'neg'));
        }
        if (r.top_income && r.top_income.length) {
            html += section('Надходження дня', listRows(r.top_income, 'category', 'amount_display', 'pos'));
        }

        // Борги, погашені сьогодні.
        var paid = r.debts_paid_today || {};
        var paidRows = '';
        if (paid.receivable && paid.receivable.count) {
            paidRows += '<div class="fin-rdebt-line is-pos"><span>Отримано від боржників (' + paid.receivable.count + ')</span><strong>' + esc(paid.receivable.sum_display) + '</strong></div>';
        }
        if (paid.payable && paid.payable.count) {
            paidRows += '<div class="fin-rdebt-line is-neg"><span>Сплачено кредиторам (' + paid.payable.count + ')</span><strong>' + esc(paid.payable.sum_display) + '</strong></div>';
        }
        if (paidRows) html += section('Борги, погашені сьогодні', paidRows);

        // Непогашені борги.
        var un = r.debts_unpaid || {};
        var unHtml = '';
        unHtml += debtSummary('Вам винні (дебіторка)', un.receivable, 'pos');
        unHtml += debtSummary('Ви винні (кредиторка)', un.payable, 'neg');
        if (unHtml) html += section('Непогашені борги', unHtml);

        html += tips(r.tips);
        return html;
    }

    function debtSummary(label, side, cls) {
        if (!side || !side.count) return '';
        var n = side.nearest;
        var nearestTxt = '';
        if (n) {
            var d = humanDays(n.days, n.overdue);
            nearestTxt = '<div class="fin-rdebt-nearest">Найближче: ' + esc(n.name)
                + ' · ' + esc(n.amount_display) + (d ? ' · <em>' + d + '</em>' : '') + '</div>';
        }
        var over = side.overdue_count
            ? '<span class="fin-rbadge fin-rbadge--alert">' + side.overdue_count + ' простроч. · ' + esc(side.overdue_sum_display) + '</span>'
            : '';
        return '<div class="fin-rdebt-block fin-rdebt-block--' + cls + '">'
            + '<div class="fin-rdebt-head"><span>' + esc(label) + '</span><strong>' + esc(side.total_display) + '</strong></div>'
            + '<div class="fin-rdebt-sub">' + side.count + ' позиц. ' + over + '</div>'
            + nearestTxt + '</div>';
    }

    // --- Weekly ---
    function renderWeekly(r) {
        var html = '';
        html += '<div class="fin-rstat-grid fin-rstat-grid--3">'
            + stat('Дохід', r.income_display, 'pos')
            + stat('Витрати', r.expense_display, 'neg')
            + stat('Прибуток', r.profit_display, (r.profit >= 0 ? 'pos' : 'neg'))
            + '</div>';

        html += weeklyChart(r.days || [], r.currency || '');

        if (r.health_score != null) {
            html += '<div class="fin-rhealth">'
                + '<div class="fin-rhealth__gauge" style="--score:' + r.health_score + '">'
                + '<span>' + r.health_score + '</span></div>'
                + '<div class="fin-rhealth__text"><strong>Фінансове здоровʼя</strong>'
                + '<span>' + esc(r.health_label || '') + ' · ' + r.health_score + '/100</span></div>'
                + '</div>';
        }

        if (r.metrics && r.metrics.length) {
            var m = '';
            r.metrics.forEach(function (it) {
                m += '<div class="fin-rmetric"><span class="fin-rmetric__label">' + esc(it.label) + '</span>'
                    + '<strong class="fin-rmetric__value">' + esc(it.value_display) + '</strong>'
                    + (it.hint ? '<small class="fin-rmetric__hint">' + esc(it.hint) + '</small>' : '')
                    + '</div>';
            });
            html += section('Ключові метрики', '<div class="fin-rmetric-grid">' + m + '</div>');
        }

        if (r.top_categories && r.top_categories.length) {
            var rows = '';
            r.top_categories.forEach(function (c) {
                rows += '<div class="fin-rcat">'
                    + '<div class="fin-rcat__top"><span>' + esc(c.name) + '</span><strong>' + esc(c.amount_display) + '</strong></div>'
                    + '<div class="fin-rcat__bar"><i style="width:' + Math.min(100, c.pct) + '%"></i></div>'
                    + '<small>' + c.pct + '% витрат</small></div>';
            });
            html += section('Куди йшли гроші', rows);
        }

        html += tips(r.tips);
        return html;
    }

    function weeklyChart(days, cur) {
        if (!days.length) return '';
        var max = 0;
        days.forEach(function (d) { max = Math.max(max, d.income, d.expense); });
        if (max <= 0) max = 1;
        var bars = '';
        days.forEach(function (d) {
            var ih = Math.round(d.income / max * 100);
            var eh = Math.round(d.expense / max * 100);
            bars += '<div class="fin-rchart__col" title="' + esc(d.label) + ': +' + fmt(d.income) + ' / -' + fmt(d.expense) + '">'
                + '<div class="fin-rchart__bars">'
                + '<i class="fin-rchart__bar fin-rchart__bar--inc" style="height:' + ih + '%"></i>'
                + '<i class="fin-rchart__bar fin-rchart__bar--exp" style="height:' + eh + '%"></i>'
                + '</div><span class="fin-rchart__label">' + esc(d.label) + '</span></div>';
        });
        return '<div class="fin-rchart">'
            + '<div class="fin-rchart__legend"><span class="is-inc">Дохід</span><span class="is-exp">Витрати</span></div>'
            + '<div class="fin-rchart__plot">' + bars + '</div></div>';
    }

    // --- Debts ---
    function renderDebts(r) {
        var html = '';
        html += '<div class="fin-rstat-grid">'
            + stat('Вам винні', (r.receivable && r.receivable.total_display) || '—', 'pos')
            + stat('Ви винні', (r.payable && r.payable.total_display) || '—', 'neg')
            + '</div>';
        html += debtTable('Дебіторка — хто винен вам', r.receivable, 'pos');
        html += debtTable('Кредиторка — кому винні ви', r.payable, 'neg');
        html += tips(r.tips);
        return html;
    }

    function debtTable(label, side, cls) {
        if (!side || !side.count) return '';
        var rows = '';
        (side.rows || []).forEach(function (row) {
            var d = humanDays(row.days, row.overdue);
            rows += '<div class="fin-rdebt-row' + (row.overdue ? ' is-overdue' : '') + '">'
                + '<span class="fin-rdebt-row__name">' + esc(row.name) + '</span>'
                + '<span class="fin-rdebt-row__meta">' + (d ? '<em>' + d + '</em>' : '') + '</span>'
                + '<strong class="fin-rdebt-row__amt">' + esc(row.amount_display) + '</strong>'
                + '</div>';
        });
        var over = side.overdue_count
            ? '<span class="fin-rbadge fin-rbadge--alert">' + side.overdue_count + ' простроч. · ' + esc(side.overdue_sum_display) + '</span>' : '';
        return section(label + ' ' + over, '<div class="fin-rdebt-table fin-rdebt-table--' + cls + '">' + rows + '</div>');
    }

    // --- Health ---
    function renderHealth(r) {
        var html = '';
        if (r.score != null) {
            html += '<div class="fin-rhealth">'
                + '<div class="fin-rhealth__gauge fin-rhealth__gauge--alert" style="--score:' + r.score + '"><span>' + r.score + '</span></div>'
                + '<div class="fin-rhealth__text"><strong>' + esc(r.label || 'Ризик') + '</strong><span>' + r.score + '/100</span></div>'
                + '</div>';
        }
        var rows = '';
        (r.alerts || []).forEach(function (a) {
            rows += '<div class="fin-ralert fin-ralert--' + esc(a.severity) + '">'
                + '<strong>' + esc(a.title) + '</strong><span>' + esc(a.message) + '</span></div>';
        });
        if (rows) html += section('Ризики', rows);
        html += tips(r.tips);
        return html;
    }

    // --- Planned ---
    function renderPlanned(r) {
        var html = '<div class="fin-rstat-grid">'
            + stat('Надходжень', r.income_display || '—', 'pos')
            + stat('До сплати', r.expense_display || '—', 'neg')
            + '</div>';
        html += '<p class="fin-report-text">' + (r.count || 0) + ' планов(их) платеж(ів) на найближчу добу. '
            + 'Перевірте календар, щоб нічого не пропустити.</p>';
        return html;
    }

    // ===== Хелпери =====
    function stat(label, value, cls) {
        return '<div class="fin-rstat fin-rstat--' + (cls || 'neutral') + '">'
            + '<span class="fin-rstat__label">' + esc(label) + '</span>'
            + '<strong class="fin-rstat__value">' + esc(value || '—') + '</strong></div>';
    }

    function section(title, inner) {
        return '<section class="fin-rsection"><h3 class="fin-rsection__title">' + title + '</h3>'
            + inner + '</section>';
    }

    function listRows(items, nameKey, amtKey, cls) {
        var rows = '';
        items.forEach(function (it) {
            rows += '<div class="fin-rline"><span>' + esc(it[nameKey]) + '</span>'
                + '<strong class="is-' + cls + '">' + esc(it[amtKey]) + '</strong></div>';
        });
        return '<div class="fin-rlist">' + rows + '</div>';
    }

    function tips(list) {
        if (!list || !list.length) return '';
        var items = '';
        list.forEach(function (t) { if (t) items += '<li>' + esc(t) + '</li>'; });
        if (!items) return '';
        return '<section class="fin-rsection fin-rtips"><h3 class="fin-rsection__title">💡 Поради дня</h3>'
            + '<ul class="fin-rtips__list">' + items + '</ul></section>';
    }

    function humanDays(days, overdue) {
        if (days == null) return '';
        if (days < 0 || overdue && days <= 0) {
            var n = Math.abs(days);
            return 'прострочено ' + n + ' дн.';
        }
        if (days === 0) return 'сьогодні';
        if (days === 1) return 'завтра';
        return 'через ' + days + ' дн.';
    }

    function fmt(n) {
        try { return Math.round(n).toLocaleString('uk-UA'); } catch (e) { return String(Math.round(n)); }
    }

    function esc(s) {
        if (s == null) return '';
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function getCookie(name) {
        var v = null;
        if (document.cookie) {
            document.cookie.split(';').forEach(function (c) {
                c = c.trim();
                if (c.substring(0, name.length + 1) === name + '=') {
                    v = decodeURIComponent(c.substring(name.length + 1));
                }
            });
        }
        return v;
    }
})();
