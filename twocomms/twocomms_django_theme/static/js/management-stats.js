(() => {
  const dataEl = document.getElementById('mgmt-stats-data');
  if (!dataEl) return;

  let data;
  try {
    data = JSON.parse(dataEl.textContent || '{}');
  } catch (e) {
    data = {};
  }

  const page = document.getElementById('stats-page');
  const dismissUrl = page?.dataset?.dismissUrl || '';
  const shadowUrl = page?.dataset?.shadowUrl || '';
  let lastShadowOpener = null;

  const getCookie = (name) => {
    if (!document.cookie) return '';
    const cookies = document.cookie.split(';');
    for (const rawCookie of cookies) {
      const cookie = rawCookie.trim();
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return '';
  };

  const isValidCsrfToken = (token) => /^[A-Za-z0-9]{32}$|^[A-Za-z0-9]{64}$/.test(token || '');
  const readDomCsrfToken = () => {
    const meta = document.querySelector?.('meta[name="csrf-token"]');
    if (meta?.getAttribute) {
      const token = meta.getAttribute('content') || '';
      if (isValidCsrfToken(token)) return token;
    }

    const input = document.querySelector?.('[name="csrfmiddlewaretoken"]');
    if (input && 'value' in input && isValidCsrfToken(input.value)) {
      return input.value;
    }

    return '';
  };

  const csrfToken = () => {
    const domToken = readDomCsrfToken();
    if (domToken) return domToken;

    const cookieToken = getCookie('csrftoken');
    if (isValidCsrfToken(cookieToken)) return cookieToken;

    return '';
  };

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  const hashCode = (s) => {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  };

  const palette = [
    '#ff7e29',
    '#ffb347',
    '#6f95ff',
    '#785aff',
    '#10b981',
    '#f97316',
    '#38bdf8',
    '#a855f7',
    '#f59e0b',
    '#fb7185',
  ];

  const colorFor = (code, idx) => {
    const key = String(code || idx || '');
    const i = hashCode(key) % palette.length;
    return palette[i];
  };

  const polarToCartesian = (cx, cy, r, angleDeg) => {
    const rad = ((angleDeg - 90) * Math.PI) / 180.0;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const describeDonutArc = (cx, cy, rOuter, rInner, startAngle, endAngle) => {
    const s = polarToCartesian(cx, cy, rOuter, endAngle);
    const e = polarToCartesian(cx, cy, rOuter, startAngle);
    const si = polarToCartesian(cx, cy, rInner, startAngle);
    const ei = polarToCartesian(cx, cy, rInner, endAngle);
    const large = endAngle - startAngle <= 180 ? 0 : 1;
    return [
      `M ${s.x} ${s.y}`,
      `A ${rOuter} ${rOuter} 0 ${large} 0 ${e.x} ${e.y}`,
      `L ${si.x} ${si.y}`,
      `A ${rInner} ${rInner} 0 ${large} 1 ${ei.x} ${ei.y}`,
      'Z',
    ].join(' ');
  };

  const renderSpiral = () => {
    const svg = document.getElementById('spiral-svg');
    const group = document.getElementById('spiral-segments');
    const legend = document.getElementById('spiral-legend');
    const tip = document.getElementById('spiral-tooltip');
    if (!svg || !group || !legend || !tip) return;

    const segments = Array.isArray(data.segments) ? data.segments : [];
    const segByCode = new Map(segments.map((s) => [String(s.code || ''), s]));
    group.innerHTML = '';
    legend.innerHTML = '';

    if (!segments.length) {
      legend.innerHTML = `<div class="legend-row"><div class="legend-left"><span class="muted">Немає даних за період.</span></div></div>`;
      return;
    }

    const cx = 120;
    const cy = 120;
    const rOuter = 108;
    const rInner = 78;
    const gap = 0.8; // degrees

    let angle = 0;
    segments.forEach((seg, idx) => {
      const pct = clamp(Number(seg.pct || 0), 0, 100);
      const slice = (pct / 100) * 360;
      const start = angle + gap;
      const end = angle + slice - gap;
      angle += slice;

      if (end <= start) return;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', describeDonutArc(cx, cy, rOuter, rInner, start, end));
      const color = colorFor(seg.code, idx);
      path.setAttribute('fill', color);
      path.setAttribute('stroke', 'rgba(255,255,255,0.10)');
      path.setAttribute('stroke-width', '1');
      path.classList.add('seg');
      path.dataset.code = seg.code || '';
      path.dataset.label = seg.label || seg.code || '';
      path.dataset.count = String(seg.count || 0);
      path.dataset.pct = `${pct.toFixed(1)}%`;
      group.appendChild(path);

      const row = document.createElement('div');
      row.className = 'legend-row';
      row.innerHTML = `
        <div class="legend-left">
          <span class="legend-dot" style="background:${color}"></span>
          <span class="legend-label">${seg.label || seg.code || ''}</span>
        </div>
        <div class="legend-right">
          <span class="legend-count">${seg.count || 0}</span>
          <span class="muted">${pct.toFixed(1)}%</span>
        </div>
      `;
      legend.appendChild(row);
    });

    const setTip = (x, y, title, count, pct, code) => {
      const titleEl = document.getElementById('tip-title');
      const countEl = document.getElementById('tip-count');
      const pctEl = document.getElementById('tip-pct');
      const noteEl = document.getElementById('tip-note');
      if (titleEl) titleEl.textContent = title;
      if (countEl) countEl.textContent = count;
      if (pctEl) pctEl.textContent = pct;
      if (noteEl) {
        const seg = segByCode.get(String(code || ''));
        const sub = Array.isArray(seg?.subtypes) ? seg.subtypes : [];
        if (sub.length) {
          noteEl.textContent = sub
            .map((x) => `${x.label} — ${x.count}`)
            .slice(0, 4)
            .join(' • ');
        } else {
          noteEl.textContent = 'Показник за обраний період (деталі — за наведенням).';
        }
      }

      tip.hidden = false;
      tip.style.left = `${x}px`;
      tip.style.top = `${y}px`;
    };

    const hideTip = () => {
      tip.hidden = true;
    };

    const shell = document.getElementById('spiral-shell');
    const shellRect = () => shell?.getBoundingClientRect();

    group.addEventListener('mousemove', (e) => {
      const target = e.target.closest?.('path.seg');
      if (!target) return;
      const rect = shellRect();
      if (!rect) return;
      const x = clamp(e.clientX - rect.left + 14, 10, rect.width - 10);
      const y = clamp(e.clientY - rect.top + 14, 10, rect.height - 10);
      setTip(x, y, target.dataset.label || '', target.dataset.count || '0', target.dataset.pct || '0%', target.dataset.code || '');
    });

    group.addEventListener('mouseleave', hideTip);
  };

  const renderGauge = () => {
    const el = document.getElementById('followup-gauge');
    const arc = document.getElementById('fu-arc');
    if (!el || !arc) return;
    const pct = clamp(Number(el.dataset.missedRate || 0), 0, 100);
    const len = 283;
    arc.style.strokeDashoffset = String(len * (1 - pct / 100));
    if (pct > 8) arc.style.stroke = 'rgba(255, 126, 41, 0.95)';
    if (pct > 20) arc.style.stroke = 'rgba(239, 68, 68, 0.95)';
  };

  const renderSparkline = (mountId, valueKey, color) => {
    const el = document.getElementById(mountId);
    if (!el) return;
    const series = Array.isArray(data.series) ? data.series : [];
    const vals = series.map((d) => Number(d?.[valueKey] || 0));
    const max = Math.max(1, ...vals);
    const w = 320;
    const h = 88;
    const pad = 6;
    const n = Math.max(1, vals.length);
    const pts = vals.map((v, i) => {
      const x = pad + (i * (w - pad * 2)) / Math.max(1, n - 1);
      const y = h - pad - (clamp(v, 0, max) * (h - pad * 2)) / max;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    el.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="${mountId}-g" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stop-color="${color}" stop-opacity="0.75"></stop>
            <stop offset="1" stop-color="${color}" stop-opacity="0.25"></stop>
          </linearGradient>
        </defs>
        <polyline points="${pts.join(' ')}" fill="none" stroke="url(#${mountId}-g)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
      </svg>
    `;
  };

  const renderSources = () => {
    const el = document.getElementById('sources-list');
    if (!el) return;
    const sources = Array.isArray(data.sources) ? data.sources : [];
    if (!sources.length) {
      el.innerHTML = `<div class="muted">Немає даних по джерелах.</div>`;
      return;
    }
    const max = Math.max(1, ...sources.map((s) => Number(s.count || 0)));
    el.innerHTML = '';
    sources.slice(0, 10).forEach((s) => {
      const cnt = Number(s.count || 0);
      const pct = clamp((cnt / max) * 100, 0, 100);
      const idx = clamp(Number(s.success_rate || 0) * 100, 0, 100);
      const idxLabel = `≈${Math.round(idx)}%`;
      const row = document.createElement('div');
      row.className = 'source-row';
      const raw = Array.isArray(s.raw) ? s.raw.filter(Boolean) : [];
      row.title = [`${cnt} лідів`, `індекс успішності ${idxLabel}`, raw.length ? `raw: ${raw.slice(0, 4).join(', ')}` : '']
        .filter(Boolean)
        .join(' • ');
      row.innerHTML = `
        <div class="source-label">${s.label || s.code || ''}</div>
        <div class="source-bar"><div class="source-fill" style="width:${pct.toFixed(1)}%"></div></div>
        <div class="source-count">${cnt}</div>
        <div class="source-idx">${idxLabel}</div>
      `;
      el.appendChild(row);
    });
  };

  const renderReportTimeline = () => {
    const el = document.getElementById('report-timeline');
    if (!el) return;
    const series = Array.isArray(data.series) ? data.series : [];
    el.innerHTML = '';
    series.forEach((d) => {
      const st = String(d.report_status || 'none');
      const dot = document.createElement('div');
      dot.className = `day-dot ${st}`;
      const title = `${d.date || ''}: ${st === 'on_time' ? 'вчасно' : st === 'late' ? 'із запізненням' : st === 'missing' ? 'не відправлено' : '—'}`;
      dot.title = title;
      el.appendChild(dot);
    });
  };

  const prettyAxisLabel = (key) =>
    String(key || '')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (m) => m.toUpperCase());

  const getVisibleShadowDrawer = () =>
    Array.from(document.querySelectorAll('.shadow-drawer')).find((node) => !node.hidden) || null;

  const getFocusableWithin = (root) =>
    Array.from(
      root?.querySelectorAll?.(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
      ) || []
    ).filter((node) => !node.hidden && node.offsetParent !== null);

  const updateAppealSummary = (appeals) => {
    const openEl = document.getElementById('shadow-appeals-open');
    const totalEl = document.getElementById('shadow-appeals-total');
    const latestEl = document.getElementById('shadow-appeals-latest');
    const dueEl = document.getElementById('shadow-appeals-due');
    if (openEl) openEl.textContent = String(appeals?.open ?? 0);
    if (totalEl) totalEl.textContent = String(appeals?.total ?? 0);
    if (latestEl) latestEl.textContent = appeals?.latest_status || '—';
    if (dueEl) dueEl.textContent = appeals?.nearest_due_at || '—';
  };

  const refreshShadowSummary = async () => {
    if (!shadowUrl) return;
    const url = new URL(shadowUrl, window.location.origin);
    const currentParams = new URLSearchParams(window.location.search || '');
    currentParams.forEach((value, key) => {
      if (!url.searchParams.has(key)) url.searchParams.set(key, value);
    });
    const res = await fetch(url.toString(), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(payload?.error || 'Не вдалося оновити стан апеляцій.');
    }
    updateAppealSummary(payload?.appeals || {});
  };

  const renderShadowRadar = () => {
    const mount = document.getElementById('shadow-radar');
    if (!mount) return;
    const currentAxes = Object.entries(data?.shadow_score?.explain?.axes || {});
    const previousAxes = data?.shadow_score?.previous_period?.explain?.axes || {};
    if (!currentAxes.length) {
      mount.innerHTML = `<div class="muted">Radar data is not ready yet.</div>`;
      return;
    }

    const w = 360;
    const h = 260;
    const cx = 180;
    const cy = 130;
    const radius = 92;
    const levels = [0.25, 0.5, 0.75, 1];
    const total = currentAxes.length;

    const pointFor = (idx, ratio, multiplier = 1) => {
      const angle = -Math.PI / 2 + (idx / total) * Math.PI * 2;
      const r = radius * clamp(Number(ratio || 0), 0, 1) * multiplier;
      return {
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
      };
    };

    const polygonForLevel = (ratio) =>
      currentAxes
        .map((_, idx) => {
          const pt = pointFor(idx, ratio);
          return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
        })
        .join(' ');

    const currentPoints = currentAxes
      .map(([key, axis], idx) => {
        const pt = pointFor(idx, axis?.value || 0);
        return { ...pt, key, value: Number(axis?.value || 0) };
      });

    const previousPoints = currentAxes
      .map(([key], idx) => {
        const prevAxis = previousAxes?.[key] || {};
        const pt = pointFor(idx, prevAxis?.value || 0);
        return { ...pt, key, value: Number(prevAxis?.value || 0) };
      })
      .filter((pt) => pt.value > 0);

    const labels = currentAxes
      .map(([key], idx) => {
        const pt = pointFor(idx, 1, 1.18);
        const anchor = pt.x < cx - 10 ? 'end' : pt.x > cx + 10 ? 'start' : 'middle';
        return `<text x="${pt.x.toFixed(1)}" y="${pt.y.toFixed(1)}" fill="rgba(255,255,255,0.72)" font-size="11" text-anchor="${anchor}">${prettyAxisLabel(key)}</text>`;
      })
      .join('');

    const axesLines = currentAxes
      .map((_, idx) => {
        const pt = pointFor(idx, 1);
        return `<line class="shadow-radar-axis" x1="${cx}" y1="${cy}" x2="${pt.x.toFixed(1)}" y2="${pt.y.toFixed(1)}"></line>`;
      })
      .join('');

    mount.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" class="shadow-radar-svg" aria-label="Shadow radar preview" role="img">
        ${levels.map((level) => `<polygon class="shadow-radar-grid" points="${polygonForLevel(level)}"></polygon>`).join('')}
        ${axesLines}
        ${
          previousPoints.length
            ? `<polygon class="shadow-radar-shape is-previous" points="${previousPoints
                .map((pt) => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`)
                .join(' ')}"></polygon>`
            : ''
        }
        <polygon class="shadow-radar-shape" points="${currentPoints
          .map((pt) => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`)
          .join(' ')}"></polygon>
        ${currentPoints
          .map((pt) => `<circle class="shadow-radar-point" cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="4.5"></circle>`)
          .join('')}
        ${previousPoints
          .map((pt) => `<circle class="shadow-radar-point is-previous" cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="3.5"></circle>`)
          .join('')}
        ${labels}
      </svg>
    `;
  };

  const setShadowDrawerState = (open) => {
    document.body.classList.toggle('shadow-drawer-open', Boolean(open));
  };

  const closeShadowDrawers = () => {
    document.querySelectorAll('.shadow-drawer').forEach((node) => {
      node.hidden = true;
      node.setAttribute('aria-hidden', 'true');
    });
    setShadowDrawerState(false);
    if (lastShadowOpener && typeof lastShadowOpener.focus === 'function') {
      lastShadowOpener.focus();
    }
  };

  const openShadowDrawer = (kind, triggerEl = null) => {
    const map = {
      decomposition: document.getElementById('shadow-decomposition-drawer'),
      appeal: document.getElementById('shadow-appeal-drawer'),
    };
    closeShadowDrawers();
    if (map[kind]) {
      lastShadowOpener = triggerEl || document.activeElement;
      map[kind].hidden = false;
      map[kind].setAttribute('aria-hidden', 'false');
      setShadowDrawerState(true);
      const panel = map[kind].querySelector('.shadow-drawer__panel');
      if (panel) {
        const focusable = getFocusableWithin(panel);
        (focusable[0] || panel).focus();
      }
    }
  };

  const submitShadowAppeal = async (form) => {
    const statusEl = document.getElementById('shadow-appeal-status');
    const token = csrfToken();
    if (!token) {
      if (statusEl) statusEl.textContent = 'CSRF token недоступний.';
      return;
    }
    const payload = new URLSearchParams(new FormData(form));
    if (statusEl) statusEl.textContent = 'Надсилання апеляції...';
    try {
      const res = await fetch(form.dataset.url || '', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          'X-CSRFToken': token,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: payload.toString(),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok || !result?.success) {
        throw new Error(result?.error || 'Не вдалося надіслати апеляцію.');
      }
      await refreshShadowSummary();
      if (statusEl) statusEl.textContent = `Апеляцію #${result.appeal?.id || ''} створено. Стан оновлено.`;
      form.reset();
      setTimeout(() => {
        closeShadowDrawers();
      }, 900);
    } catch (err) {
      if (statusEl) statusEl.textContent = err?.message || 'Не вдалося надіслати апеляцію.';
    }
  };

  const dismissAdvice = async (key, expiresAt) => {
    if (!dismissUrl) return;
    const token = csrfToken();
    if (!token) return;
    try {
      await fetch(dismissUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': token,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ key, expires_at: expiresAt || null }),
      });
    } catch (e) {
      // ignore
    }
  };

  const openProfileBot = () => {
    const btn = document.querySelector('.open-profile-modal');
    if (btn) btn.click();
    setTimeout(() => {
      const block = document.querySelector('#profile-modal .bot-block');
      if (block) block.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 250);
  };

  document.addEventListener('click', (e) => {
    const dismissBtn = e.target.closest?.('.dismiss-advice');
    if (dismissBtn) {
      const item = dismissBtn.closest('.advice-item');
      if (!item) return;
      const key = item.dataset.adviceKey || '';
      const expiresAt = item.dataset.expiresAt || '';
      item.remove();
      dismissAdvice(key, expiresAt);
      return;
    }

    const shadowOpenBtn = e.target.closest?.('[data-shadow-open]');
    if (shadowOpenBtn) {
      openShadowDrawer(shadowOpenBtn.dataset.shadowOpen || '', shadowOpenBtn);
      return;
    }

    if (e.target.closest?.('[data-shadow-close]')) {
      closeShadowDrawers();
      return;
    }

    const actionBtn = e.target.closest?.('[data-action]');
    if (actionBtn) {
      const action = actionBtn.dataset.action;
      if (action === 'open_profile_bot') openProfileBot();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeShadowDrawers();
      return;
    }
    if (e.key !== 'Tab') return;
    const activeDrawer = getVisibleShadowDrawer();
    if (!activeDrawer) return;
    const panel = activeDrawer.querySelector('.shadow-drawer__panel');
    const focusable = getFocusableWithin(panel);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  // Kickoff
  renderSpiral();
  renderGauge();
  renderShadowRadar();
  renderSparkline('chart-points', 'points', '#ff7e29');
  renderSparkline('chart-kpd', 'kpd', '#6f95ff');
  renderSparkline('chart-active', 'active_seconds', '#10b981');
  renderSources();
  renderReportTimeline();

  const appealForm = document.getElementById('shadow-appeal-form');
  if (appealForm) {
    appealForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitShadowAppeal(appealForm);
    });
  }
})();
