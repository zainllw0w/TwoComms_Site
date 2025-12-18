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

  const getCookie = (name) => {
    const parts = (`; ${document.cookie || ''}`).split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  };

  const csrfToken = () => getCookie('csrftoken');

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

  const dismissAdvice = async (key, expiresAt) => {
    if (!dismissUrl) return;
    try {
      await fetch(dismissUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
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

    const actionBtn = e.target.closest?.('[data-action]');
    if (actionBtn) {
      const action = actionBtn.dataset.action;
      if (action === 'open_profile_bot') openProfileBot();
    }
  });

  // Kickoff
  renderSpiral();
  renderGauge();
  renderSparkline('chart-points', 'points', '#ff7e29');
  renderSparkline('chart-kpd', 'kpd', '#6f95ff');
  renderSparkline('chart-active', 'active_seconds', '#10b981');
  renderSources();
  renderReportTimeline();
})();
