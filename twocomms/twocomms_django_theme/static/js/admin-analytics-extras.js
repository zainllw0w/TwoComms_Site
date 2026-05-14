/**
 * Side panels of the analytics dashboard:
 *   - Sessions list / detail drilldown
 *   - Analytics exclusions CRUD
 * Both panels load on demand the first time the user opens their tab so
 * the main dashboard render stays cheap.
 */

(function () {
  const root = document.querySelector("[data-admin-analytics-root]");
  if (!root) return;

  const csrfToken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

  const state = {
    sessionsLoaded: false,
    exclusionsLoaded: false,
    sessionsOffset: 0,
    sessionsLimit: 30,
  };

  /* -------- shared utils -------- */

  function fetchJson(url, options = {}) {
    const opts = Object.assign({ credentials: "same-origin", headers: {} }, options);
    if ((options.method || "GET") !== "GET") {
      opts.headers["X-CSRFToken"] = csrfToken;
    }
    if (options.body && !(options.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/x-www-form-urlencoded";
    }
    return fetch(url, opts).then((response) => response.json().catch(() => ({ success: false, error: "bad-json" })));
  }

  function escapeHtml(value) {
    if (value == null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDateTime(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString("uk-UA", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function formatDuration(seconds) {
    if (!seconds || seconds < 0) return "—";
    if (seconds < 60) return `${seconds}с`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}хв`;
    return `${(seconds / 3600).toFixed(1)}год`;
  }

  /* -------- Tab activation hook -------- */

  root.querySelectorAll("[data-analytics-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.analyticsTab;
      if (tab === "exclusions" && !state.exclusionsLoaded) {
        loadExclusions();
      }
      if (tab === "sessions" && !state.sessionsLoaded) {
        loadSessions();
      }
    });
  });

  /* -------- Exclusions panel -------- */

  const exclusionList = document.getElementById("analyticsExclusionList");
  const exclusionForm = document.getElementById("analyticsExclusionForm");
  const exclusionMsg = document.getElementById("analyticsExclusionMsg");

  function setExclusionMessage(text, kind = "info") {
    if (!exclusionMsg) return;
    exclusionMsg.textContent = text || "";
    exclusionMsg.style.color = kind === "error" ? "#fca5a5" : "rgba(148,163,184,0.92)";
  }

  function renderExclusions(items) {
    if (!exclusionList) return;
    if (!items.length) {
      exclusionList.innerHTML = '<div class="analytics-footnote">Список порожній.</div>';
      return;
    }
    exclusionList.innerHTML = items
      .map(
        (item) => `
        <div class="analytics-exclusion-row${item.is_active ? "" : " is-inactive"}" data-id="${item.id}">
          <div><strong>${escapeHtml(item.kind_label)}</strong></div>
          <code>${escapeHtml(item.value)}</code>
          <div>${escapeHtml(item.note || "")}</div>
          <button type="button" data-action="toggle">${item.is_active ? "Вимкнути" : "Увімкнути"}</button>
          <button type="button" data-action="delete" class="is-danger">Видалити</button>
        </div>`,
      )
      .join("");
  }

  function loadExclusions() {
    setExclusionMessage("Завантаження…");
    fetchJson("/admin-panel/analytics/exclusions/").then((data) => {
      if (!data.success) {
        setExclusionMessage(data.error || "Не вдалося завантажити список", "error");
        return;
      }
      state.exclusionsLoaded = true;
      renderExclusions(data.items || []);
      setExclusionMessage(`Активних: ${data.active}/${data.total}`);
    });
  }

  if (exclusionForm) {
    exclusionForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(exclusionForm);
      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) params.append(key, value);
      setExclusionMessage("Зберігаємо…");
      fetchJson("/admin-panel/analytics/exclusions/create/", {
        method: "POST",
        body: params.toString(),
      }).then((data) => {
        if (!data.success) {
          setExclusionMessage(data.error || "Помилка", "error");
          return;
        }
        exclusionForm.reset();
        setExclusionMessage("Додано. Список оновлено.");
        loadExclusions();
      });
    });
  }

  if (exclusionList) {
    exclusionList.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const row = button.closest("[data-id]");
      if (!row) return;
      const id = row.dataset.id;
      const action = button.dataset.action;

      if (action === "delete") {
        if (!window.confirm("Видалити це виключення?")) return;
        fetchJson(`/admin-panel/analytics/exclusions/${id}/`, { method: "DELETE" }).then((data) => {
          if (!data.success) {
            setExclusionMessage(data.error || "Не вдалося видалити", "error");
            return;
          }
          setExclusionMessage("Видалено.");
          loadExclusions();
        });
        return;
      }

      if (action === "toggle") {
        const params = new URLSearchParams({ action: "toggle" });
        fetchJson(`/admin-panel/analytics/exclusions/${id}/`, {
          method: "POST",
          body: params.toString(),
        }).then((data) => {
          if (!data.success) {
            setExclusionMessage(data.error || "Не вдалося змінити", "error");
            return;
          }
          loadExclusions();
        });
      }
    });
  }

  /* -------- Sessions drill-down -------- */

  const sessionsList = document.getElementById("analyticsSessionsList");
  const sessionsPager = document.getElementById("analyticsSessionsPager");
  const sessionsRefresh = document.getElementById("analyticsSessionsRefresh");
  const sessionsSearch = document.getElementById("analyticsSessionsSearch");
  const sessionsDays = document.getElementById("analyticsSessionsDays");
  const sessionsBots = document.getElementById("analyticsSessionsIncludeBots");
  const sessionDetail = document.getElementById("analyticsSessionDetail");

  function buildSessionsUrl(extra = {}) {
    const params = new URLSearchParams();
    params.set("days", sessionsDays?.value || "7");
    params.set("limit", String(state.sessionsLimit));
    params.set("offset", String(extra.offset ?? state.sessionsOffset));
    if (sessionsBots?.checked) params.set("include_bots", "1");
    const q = (sessionsSearch?.value || "").trim();
    if (q) params.set("q", q);
    return `/admin-panel/analytics/sessions/?${params.toString()}`;
  }

  function renderSessionsList(payload) {
    if (!sessionsList) return;
    if (!payload.items.length) {
      sessionsList.innerHTML = '<div class="analytics-footnote">Жодної сесії за обраний період.</div>';
      sessionsPager.textContent = "";
      return;
    }
    sessionsList.innerHTML = payload.items
      .map(
        (item) => `
        <div class="analytics-session-row${item.is_bot ? " is-bot" : ""}" data-id="${item.id}">
          <div><strong>${escapeHtml(item.username || (item.user_id ? `user#${item.user_id}` : "Анонім"))}</strong><br><small>${escapeHtml(item.ip_address || "—")}</small></div>
          <div><code>${escapeHtml(item.last_path || "/")}</code><br><small>${escapeHtml((item.user_agent || "").slice(0, 80))}</small></div>
          <div>${item.pageviews} переглядів</div>
          <div>${formatDuration(item.duration_seconds)}</div>
          <div><small>${formatDateTime(item.last_seen)}</small></div>
        </div>`,
      )
      .join("");

    const start = payload.offset + 1;
    const end = Math.min(payload.offset + payload.items.length, payload.total);
    const canPrev = payload.offset > 0;
    const canNext = end < payload.total;
    sessionsPager.innerHTML = `
      ${start}–${end} з ${payload.total}
      ${canPrev ? '<button type="button" id="analyticsSessionsPrev" class="analytics-tab-btn" style="margin-left:0.6rem;">‹</button>' : ""}
      ${canNext ? '<button type="button" id="analyticsSessionsNext" class="analytics-tab-btn" style="margin-left:0.6rem;">›</button>' : ""}`;
    if (canPrev) {
      document.getElementById("analyticsSessionsPrev").addEventListener("click", () => {
        state.sessionsOffset = Math.max(0, state.sessionsOffset - state.sessionsLimit);
        loadSessions();
      });
    }
    if (canNext) {
      document.getElementById("analyticsSessionsNext").addEventListener("click", () => {
        state.sessionsOffset = state.sessionsOffset + state.sessionsLimit;
        loadSessions();
      });
    }
  }

  function loadSessions() {
    if (!sessionsList) return;
    sessionsList.innerHTML = '<div class="analytics-footnote">Завантаження сесій…</div>';
    sessionsPager.textContent = "";
    fetchJson(buildSessionsUrl()).then((data) => {
      if (!data.success) {
        sessionsList.innerHTML = `<div class="analytics-footnote">Помилка: ${escapeHtml(data.error || "")}</div>`;
        return;
      }
      state.sessionsLoaded = true;
      renderSessionsList(data);
    });
  }

  if (sessionsRefresh) {
    sessionsRefresh.addEventListener("click", () => {
      state.sessionsOffset = 0;
      loadSessions();
    });
  }
  if (sessionsSearch) {
    sessionsSearch.addEventListener("change", () => {
      state.sessionsOffset = 0;
      loadSessions();
    });
  }
  [sessionsDays, sessionsBots].forEach((el) => {
    if (el) el.addEventListener("change", () => {
      state.sessionsOffset = 0;
      loadSessions();
    });
  });

  if (sessionsList) {
    sessionsList.addEventListener("click", (event) => {
      const row = event.target.closest("[data-id]");
      if (!row) return;
      openSessionDetail(row.dataset.id);
    });
  }

  function openSessionDetail(id) {
    if (!sessionDetail) return;
    sessionDetail.hidden = false;
    sessionDetail.innerHTML = '<div class="analytics-footnote">Завантаження…</div>';
    fetchJson(`/admin-panel/analytics/sessions/${id}/`).then((data) => {
      if (!data.success) {
        sessionDetail.innerHTML = `<div class="analytics-footnote">${escapeHtml(data.error || "Помилка")}</div>`;
        return;
      }
      renderSessionDetail(data);
      sessionDetail.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  function renderSessionDetail(payload) {
    if (!sessionDetail) return;
    const s = payload.session;
    const utm = payload.utm || {};
    const sourceLabel = [utm.utm_source, utm.utm_medium, utm.utm_campaign].filter(Boolean).join(" / ") || "—";
    const grid = `
      <div><strong>Користувач</strong>${escapeHtml(s.username || (s.user_id ? `user#${s.user_id}` : "Анонім"))}</div>
      <div><strong>IP</strong>${escapeHtml(s.ip_address || "—")}</div>
      <div><strong>Visitor ID</strong><code>${escapeHtml((s.visitor_id || "—").slice(0, 16))}</code></div>
      <div><strong>Початок</strong>${formatDateTime(s.first_seen)}</div>
      <div><strong>Останній перегляд</strong>${formatDateTime(s.last_seen)}</div>
      <div><strong>Тривалість</strong>${formatDuration(s.duration_seconds)}</div>
      <div><strong>Pageviews</strong>${s.pageviews}</div>
      <div><strong>UTM</strong>${escapeHtml(sourceLabel)}</div>
      <div><strong>Гео</strong>${escapeHtml(utm.country || "—")} / ${escapeHtml(utm.city || "—")}</div>
      <div><strong>Пристрій</strong>${escapeHtml(utm.device_type || "—")} · ${escapeHtml(utm.browser_name || "")} · ${escapeHtml(utm.os_name || "")}</div>
      <div><strong>Реферер</strong><code>${escapeHtml((utm.referrer || "—").slice(0, 60))}</code></div>
      <div><strong>Лендинг</strong><code>${escapeHtml(utm.landing_page || s.last_path || "—")}</code></div>`;
    const pageviewItems = (payload.pageviews || [])
      .map((pv) => `
        <div class="analytics-session-pageview">
          <span><code>${escapeHtml(pv.path)}</code> ${pv.is_bot ? "<small>(bot)</small>" : ""}</span>
          <small>${formatDateTime(pv.when)}${pv.seconds_since_prev != null ? ` · +${formatDuration(pv.seconds_since_prev)}` : ""}</small>
        </div>`)
      .join("");
    const actionItems = (payload.actions || [])
      .map((action) => `
        <div class="analytics-session-pageview">
          <span><strong>${escapeHtml(action.action_type)}</strong> ${action.product_name ? `· ${escapeHtml(action.product_name)}` : ""} ${action.cart_value != null ? `· ${action.cart_value} ₴` : ""}</span>
          <small>${formatDateTime(action.timestamp)}</small>
        </div>`)
      .join("");

    sessionDetail.innerHTML = `
      <h4>Деталь сесії #${s.id}</h4>
      <div class="analytics-session-detail-grid">${grid}</div>
      <h4>Послідовність переглядів (${(payload.pageviews || []).length})</h4>
      <div class="analytics-session-pageviews">${pageviewItems || '<div class="analytics-footnote">Немає переглядів.</div>'}</div>
      ${actionItems ? `<h4 style="margin-top:0.85rem;">Дії (${payload.actions.length})</h4><div class="analytics-session-pageviews">${actionItems}</div>` : ""}
      <button type="button" class="analytics-tab-btn" style="margin-top:0.85rem;" id="analyticsSessionDetailClose">Закрити</button>`;
    document.getElementById("analyticsSessionDetailClose").addEventListener("click", () => {
      sessionDetail.hidden = true;
    });
  }

  /* -------- Auto-load if landed on the tab -------- */

  const initialTab = root.querySelector("[data-analytics-tab].is-active")?.dataset.analyticsTab;
  if (initialTab === "exclusions") loadExclusions();
  if (initialTab === "sessions") loadSessions();
})();
