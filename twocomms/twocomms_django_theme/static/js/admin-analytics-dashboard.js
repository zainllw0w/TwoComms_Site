(function () {
  const configNode = document.getElementById("adminAnalyticsConfig");
  const root = document.querySelector("[data-admin-analytics-root]");
  if (!configNode || !root) return;

  let config;
  try {
    config = JSON.parse(configNode.textContent || "{}");
  } catch (error) {
    console.error("[admin analytics] config parse failed", error);
    return;
  }

  const state = {
    cache: {
      overview: config.initialData?.overview || null,
      timeseries: config.initialData?.timeseries || null,
      "integration-status": config.initialData?.integrationStatus || null,
    },
    charts: {},
    loading: new Set(),
  };

  const tabToEndpoint = {
    traffic: "acquisition",
    sales: "sales",
    cart: "cart",
    products: "products",
    "custom-print": "custom-print",
    survey: "survey",
    ux: "ux-health",
  };

  initTabs();
  renderOverview();
  activateTab(config.initialTab || "overview");

  function initTabs() {
    root.querySelectorAll("[data-analytics-tab]").forEach((button) => {
      button.addEventListener("click", () => activateTab(button.dataset.analyticsTab));
    });
  }

  function activateTab(tabName) {
    root.querySelectorAll("[data-analytics-tab]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.analyticsTab === tabName);
    });
    root.querySelectorAll("[data-analytics-panel]").forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.analyticsPanel === tabName);
    });

    if (tabName === "overview") {
      renderOverview();
      return;
    }

    const endpoint = tabToEndpoint[tabName];
    if (!endpoint) return;
    ensureWidget(endpoint)
      .then((widget) => {
        if (tabName === "traffic") renderTraffic(widget);
        if (tabName === "sales") renderSales(widget);
        if (tabName === "cart") renderCart(widget);
        if (tabName === "products") renderProducts(widget);
        if (tabName === "custom-print") renderCustomPrint(widget);
        if (tabName === "survey") renderSurvey(widget);
        if (tabName === "ux") renderUx(widget);
      })
      .catch((error) => {
        console.error(`[admin analytics] ${endpoint} failed`, error);
      });
  }

  function buildWidgetUrl(endpoint) {
    const params = new URLSearchParams(config.filters || {});
    const query = params.toString();
    return `${config.apiBase}/${endpoint}/${query ? `?${query}` : ""}`;
  }

  async function ensureWidget(endpoint) {
    if (state.cache[endpoint]) return state.cache[endpoint];
    if (state.loading.has(endpoint)) {
      return new Promise((resolve) => {
        const interval = window.setInterval(() => {
          if (!state.loading.has(endpoint)) {
            window.clearInterval(interval);
            resolve(state.cache[endpoint]);
          }
        }, 100);
      });
    }
    state.loading.add(endpoint);
    try {
      const response = await fetch(buildWidgetUrl(endpoint), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      const payload = await response.json();
      state.cache[endpoint] = payload;
      return payload;
    } finally {
      state.loading.delete(endpoint);
    }
  }

  function renderOverview() {
    const overview = state.cache.overview;
    const timeseries = state.cache.timeseries;
    const integration = state.cache["integration-status"];

    renderTrackedFrom(
      document.getElementById("analyticsTrackedFromList"),
      overview?.data?.tracked_from || {}
    );
    renderCompareSummary(
      document.getElementById("analyticsCompareSummary"),
      overview?.data?.comparison || {}
    );
    renderIntegrationFreshness(
      document.getElementById("analyticsOverviewFreshness"),
      integration?.data?.integrations || []
    );

    const labels = timeseries?.data?.labels || [];
    const series = timeseries?.data?.series || {};
    drawChart("analyticsOverviewChart", {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Сесії",
            data: series.sessions || [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.18)",
            tension: 0.28,
            fill: true,
          },
          {
            label: "Замовлення",
            data: series.orders || [],
            borderColor: "#f97316",
            backgroundColor: "rgba(249, 115, 22, 0.18)",
            tension: 0.28,
            fill: true,
          },
          {
            label: "Дохід",
            data: series.revenue || [],
            borderColor: "#22c55e",
            backgroundColor: "rgba(34, 197, 94, 0.1)",
            tension: 0.28,
            yAxisID: "y1",
          },
        ],
      },
      options: lineOptions(),
    });
  }

  function renderTraffic(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsTrafficSources", "analyticsTrafficLanding", "analyticsTrafficBreakdowns", "analyticsGa4Summary"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsTrafficChart", {
      type: "bar",
      data: {
        labels: (data.source_classes || []).map((item) => item.label),
        datasets: [
          {
            label: "Сесії",
            data: (data.source_classes || []).map((item) => item.sessions),
            backgroundColor: ["#38bdf8", "#f97316", "#22c55e", "#e879f9", "#facc15", "#94a3b8"],
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderTable(
      document.getElementById("analyticsTrafficSources"),
      [
        { key: "utm_source", label: "Source" },
        { key: "utm_medium", label: "Medium" },
        { key: "source_class", label: "Клас" },
        { key: "sessions", label: "Сесії", formatter: formatInt },
      ],
      data.top_sources || []
    );

    renderList(
      document.getElementById("analyticsTrafficLanding"),
      [
        ...(data.landing_pages || []).slice(0, 6).map((item) => ({
          title: item.label,
          value: `${formatInt(item.sessions)} сесій`,
        })),
        ...(data.referrers || []).slice(0, 6).map((item) => ({
          title: item.label,
          value: `${formatInt(item.sessions)} переходів`,
        })),
      ]
    );

    const breakdownItems = [];
    (data.devices || []).slice(0, 4).forEach((item) => breakdownItems.push({
      title: `Device: ${item.label}`,
      value: `${formatInt(item.sessions)} сесій`,
    }));
    (data.browsers || []).slice(0, 4).forEach((item) => breakdownItems.push({
      title: `Browser: ${item.label}`,
      value: `${formatInt(item.sessions)} сесій`,
    }));
    (data.geo || []).slice(0, 4).forEach((item) => breakdownItems.push({
      title: item.label,
      value: `${formatInt(item.sessions)} сесій`,
    }));
    renderList(document.getElementById("analyticsTrafficBreakdowns"), breakdownItems);

    const ga4Summary = document.getElementById("analyticsGa4Summary");
    if (data.ga4_snapshot?.error) {
      renderList(ga4Summary, [{ title: "GA4", value: data.ga4_snapshot.error }]);
      return;
    }
    const ga4Items = [];
    ((data.ga4_snapshot?.channel_groups?.rows) || []).slice(0, 6).forEach((item) => {
      ga4Items.push({
        title: item.sessionDefaultChannelGroup || "—",
        value: `${formatInt(item.sessions)} sessions · ER ${formatPercent(item.engagementRate)}`,
      });
    });
    renderList(ga4Summary, ga4Items);
  }

  function renderSales(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsSalesSummary", "analyticsPaymentSplit", "analyticsSalesTables"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsSalesChart", {
      type: "line",
      data: {
        labels: data.daily_series?.labels || [],
        datasets: [
          {
            label: "Дохід",
            data: data.daily_series?.revenue || [],
            borderColor: "#22c55e",
            backgroundColor: "rgba(34, 197, 94, 0.12)",
            fill: true,
            tension: 0.28,
          },
          {
            label: "Замовлення",
            data: data.daily_series?.orders || [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.12)",
            fill: true,
            tension: 0.28,
            yAxisID: "y1",
          },
        ],
      },
      options: lineOptions(),
    });

    renderList(document.getElementById("analyticsSalesSummary"), [
      { title: "Оплачені замовлення", value: formatInt(data.summary?.paid_orders) },
      { title: "Revenue", value: formatMoney(data.summary?.revenue) },
      { title: "AOV", value: formatMoney(data.summary?.aov) },
      { title: "Items sold", value: formatInt(data.summary?.items_sold) },
      { title: "Repeat purchase rate", value: formatPercent(data.summary?.repeat_purchase_rate, true) },
    ]);

    renderList(
      document.getElementById("analyticsPaymentSplit"),
      (data.payment_split || []).map((item) => ({
        title: item.payment_status,
        value: formatInt(item.count),
      }))
    );

    renderCompositeTables(document.getElementById("analyticsSalesTables"), [
      {
        title: "Source LTV",
        columns: [
          { key: "label", label: "Канал" },
          { key: "sessions", label: "Сесії", formatter: formatInt },
          { key: "orders", label: "Замовлення", formatter: formatInt },
          { key: "ltv", label: "LTV", formatter: formatMoney },
        ],
        rows: (data.source_ltv || []).slice(0, 8),
      },
      {
        title: "Top products",
        columns: [
          { key: "title", label: "Товар" },
          { key: "items_sold", label: "Шт", formatter: formatInt },
          { key: "revenue", label: "Revenue", formatter: formatMoney },
        ],
        rows: (data.top_products || []).slice(0, 8),
      },
    ]);
  }

  function renderCart(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsCartSummary", "analyticsCartPayments", "analyticsCartRemovals"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsCartChart", {
      type: "bar",
      data: {
        labels: (data.funnel || []).map((item) => item.label),
        datasets: [
          {
            label: "Користувачі",
            data: (data.funnel || []).map((item) => item.count),
            backgroundColor: ["#38bdf8", "#f97316", "#e879f9", "#22c55e"],
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderList(document.getElementById("analyticsCartSummary"), [
      { title: "Adds", value: formatInt(data.summary?.adds) },
      { title: "Removes", value: formatInt(data.summary?.removes) },
      { title: "Abandonment", value: formatPercent(data.summary?.abandonment_rate, true) },
      { title: "Add → checkout", value: formatPercent(data.summary?.add_to_checkout_rate, true) },
      { title: "Add → purchase", value: formatPercent(data.summary?.add_to_purchase_rate, true) },
      { title: "Added then purchased", value: formatInt(data.summary?.added_then_purchased) },
    ]);

    renderList(
      document.getElementById("analyticsCartPayments"),
      (data.payment_methods || []).map((item) => ({
        title: item.pay_type,
        value: formatInt(item.count),
      }))
    );

    renderTable(
      document.getElementById("analyticsCartRemovals"),
      [
        { key: "product_name", label: "Товар" },
        { key: "count", label: "Видалень", formatter: formatInt },
      ],
      data.top_removed_products || []
    );
  }

  function renderProducts(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsProductsSidebar", "analyticsProductsTable"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsProductsChart", {
      type: "bar",
      data: {
        labels: (data.top_viewed || []).slice(0, 8).map((item) => item.title),
        datasets: [
          {
            label: "Total views",
            data: (data.top_viewed || []).slice(0, 8).map((item) => item.total_views),
            backgroundColor: "#38bdf8",
            borderRadius: 12,
          },
          {
            label: "Unique IP",
            data: (data.top_viewed || []).slice(0, 8).map((item) => item.unique_ip_views),
            backgroundColor: "#f97316",
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderList(document.getElementById("analyticsProductsSidebar"), [
      ...(data.categories || []).slice(0, 6).map((item) => ({
        title: item.category,
        value: `${formatInt(item.views)} переглядів`,
      })),
      ...(data.low_viewed || []).slice(0, 6).map((item) => ({
        title: `Low view: ${item.title}`,
        value: `${formatInt(item.total_views)} views`,
      })),
    ]);

    renderTable(
      document.getElementById("analyticsProductsTable"),
      [
        { key: "title", label: "Товар" },
        { key: "category", label: "Категорія" },
        { key: "total_views", label: "Total", formatter: formatInt },
        { key: "unique_ip_views", label: "Unique IP", formatter: formatInt },
        { key: "adds_to_cart", label: "Cart", formatter: formatInt },
        { key: "purchases", label: "Purchase", formatter: formatInt },
        { key: "view_to_cart_rate", label: "View→cart", formatter: (value) => formatPercent(value, true) },
        { key: "view_to_purchase_rate", label: "View→purchase", formatter: (value) => formatPercent(value, true) },
      ],
      data.top_viewed || []
    );
  }

  function renderCustomPrint(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsCustomPrintSummary", "analyticsCustomPrintExits", "analyticsCustomPrintTables"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsCustomPrintChart", {
      type: "bar",
      data: {
        labels: (data.step_funnel || []).map((item) => item.step),
        datasets: [
          {
            label: "Enter",
            data: (data.step_funnel || []).map((item) => item.enters),
            backgroundColor: "#38bdf8",
            borderRadius: 12,
          },
          {
            label: "Complete",
            data: (data.step_funnel || []).map((item) => item.completes),
            backgroundColor: "#22c55e",
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderList(document.getElementById("analyticsCustomPrintSummary"), [
      { title: "Unique starters", value: formatInt(data.summary?.unique_starters) },
      { title: "Leads", value: formatInt(data.summary?.leads) },
      { title: "Add to cart", value: formatInt(data.summary?.add_to_cart) },
      { title: "Send to manager", value: formatInt(data.summary?.send_to_manager) },
      { title: "Linked to order", value: formatPercent(data.summary?.linked_to_order_rate, true) },
      { title: "Average final value", value: formatMoney(data.summary?.avg_final_value) },
    ]);

    renderList(
      document.getElementById("analyticsCustomPrintExits"),
      (data.safe_exits || []).map((item) => ({
        title: item.step,
        value: formatInt(item.count),
      }))
    );

    renderCompositeTables(document.getElementById("analyticsCustomPrintTables"), [
      {
        title: "Moderation",
        columns: [
          { key: "status", label: "Статус" },
          { key: "count", label: "Кількість", formatter: formatInt },
        ],
        rows: data.moderation || [],
      },
      {
        title: "Client mix",
        columns: [
          { key: "client_kind", label: "Тип" },
          { key: "count", label: "Кількість", formatter: formatInt },
        ],
        rows: data.client_mix || [],
      },
    ]);
  }

  function renderSurvey(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsSurveySummary", "analyticsSurveyDropoff", "analyticsSurveyAnswers"])) {
      return;
    }
    const data = widget.data || {};
    drawChart("analyticsSurveyChart", {
      type: "bar",
      data: {
        labels: ["Starts", "Completed", "Back", "Skip", "Promo issued"],
        datasets: [
          {
            label: "Кількість",
            data: [
              data.summary?.starts || 0,
              data.summary?.completed || 0,
              data.summary?.back_used || 0,
              data.summary?.skip_used || 0,
              data.summary?.promo_issued || 0,
            ],
            backgroundColor: ["#38bdf8", "#22c55e", "#f97316", "#e879f9", "#facc15"],
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderList(document.getElementById("analyticsSurveySummary"), [
      { title: "Starts", value: formatInt(data.summary?.starts) },
      { title: "Completed", value: formatInt(data.summary?.completed) },
      { title: "Completion rate", value: formatPercent(data.summary?.completion_rate, true) },
      { title: "Promo issued", value: formatInt(data.summary?.promo_issued) },
      { title: "Downstream purchase", value: formatPercent(data.summary?.downstream_purchase_rate, true) },
    ]);

    renderTable(
      document.getElementById("analyticsSurveyDropoff"),
      [
        { key: "question_id", label: "Question" },
        { key: "count", label: "Drop-off", formatter: formatInt },
      ],
      data.question_dropoff || []
    );

    renderTable(
      document.getElementById("analyticsSurveyAnswers"),
      [
        { key: "question_id", label: "Question" },
        { key: "count", label: "Answers", formatter: formatInt },
      ],
      data.question_answers || []
    );
  }

  function renderUx(widget) {
    if (renderErrorIfNeeded(widget, ["analyticsUxFreshness", "analyticsUxUrls", "analyticsUxWarnings"])) {
      return;
    }
    const data = widget.data || {};
    const clarityOverview = data.clarity_overview || {};
    const metrics = [
      { label: "Traffic", value: totalFromClarityMetric(clarityOverview.Traffic, "totalSessionCount") },
      { label: "Rage clicks", value: totalFromClarityMetric(clarityOverview["Rage Click Count"], "Rage Click Count") },
      { label: "Dead clicks", value: totalFromClarityMetric(clarityOverview["Dead Click Count"], "Dead Click Count") },
      { label: "Quickbacks", value: totalFromClarityMetric(clarityOverview["Quickback Click"], "Quickback Click") },
      { label: "Script errors", value: totalFromClarityMetric(clarityOverview["Script Error Count"], "Script Error Count") },
    ];

    drawChart("analyticsUxChart", {
      type: "bar",
      data: {
        labels: metrics.map((item) => item.label),
        datasets: [
          {
            label: "Clarity live",
            data: metrics.map((item) => item.value),
            backgroundColor: ["#38bdf8", "#ef4444", "#f97316", "#e879f9", "#facc15"],
            borderRadius: 12,
          },
        ],
      },
      options: barOptions(),
    });

    renderList(
      document.getElementById("analyticsUxFreshness"),
      (data.tracking_freshness || []).map((item) => ({
        title: item.label,
        value: item.timestamp ? new Date(item.timestamp).toLocaleString("uk-UA") : "Немає даних",
      }))
    );

    renderTable(
      document.getElementById("analyticsUxUrls"),
      [
        { key: "url", label: "URL" },
        { key: "sessions", label: "Сесії", formatter: formatInt },
        { key: "rage_clicks", label: "Rage", formatter: formatInt },
        { key: "dead_clicks", label: "Dead", formatter: formatInt },
        { key: "quickbacks", label: "Quickback", formatter: formatInt },
        { key: "script_errors", label: "Script", formatter: formatInt },
      ],
      data.problem_urls || []
    );

    renderList(
      document.getElementById("analyticsUxWarnings"),
      [
        {
          title: "IP capture",
          value: `${formatPercent(data.capture_health?.ip_capture_ratio, true)}`,
        },
        {
          title: "Visitor cookie coverage",
          value: `${formatPercent(data.capture_health?.visitor_cookie_ratio, true)}`,
        },
        ...((data.warnings || []).map((warning) => ({ title: "Warning", value: warning }))),
      ]
    );
  }

  function renderTrackedFrom(target, trackedFrom) {
    renderList(target, Object.entries(trackedFrom || {}).map(([key, value]) => ({
      title: key,
      value: value ? new Date(value).toLocaleDateString("uk-UA") : "tracked from pending",
    })));
  }

  function renderCompareSummary(target, comparison) {
    const rows = Object.entries(comparison || {}).map(([key, meta]) => ({
      title: key,
      value: meta && meta.delta_percent !== null && meta.delta_percent !== undefined
        ? `${meta.delta_percent}%`
        : "—",
    }));
    renderList(target, rows);
  }

  function renderIntegrationFreshness(target, integrations) {
    renderList(target, (integrations || []).map((item) => ({
      title: item.label,
      value: item.message,
    })));
  }

  function renderErrorIfNeeded(widget, ids) {
    if (!widget || !widget.error_state) return false;
    ids.forEach((id) => {
      const target = document.getElementById(id);
      if (target) {
        target.innerHTML = `<div class="analytics-warning-item">${escapeHtml(widget.error_state)}</div>`;
      }
    });
    return true;
  }

  function renderList(target, items) {
    if (!target) return;
    if (!items || !items.length) {
      target.innerHTML = '<div class="analytics-list-item"><strong>Немає даних</strong><span>Виберіть інший період або дочекайтесь збору подій.</span></div>';
      return;
    }
    target.innerHTML = items.map((item) => `
      <div class="analytics-list-item">
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.value)}</span>
      </div>
    `).join("");
  }

  function renderTable(target, columns, rows) {
    if (!target) return;
    if (!rows || !rows.length) {
      target.innerHTML = '<div class="analytics-warning-item">Немає даних для вибраних фільтрів.</div>';
      return;
    }
    target.innerHTML = `
      <table class="analytics-table">
        <thead>
          <tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              ${columns.map((column) => {
                const value = row[column.key];
                const rendered = column.formatter ? column.formatter(value) : value;
                return `<td>${escapeHtml(String(rendered ?? "—"))}</td>`;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function renderCompositeTables(target, tables) {
    if (!target) return;
    target.innerHTML = tables.map((table) => `
      <div style="margin-bottom: 1rem;">
        <div class="analytics-meta-pill" style="margin-bottom: 0.65rem;">${escapeHtml(table.title)}</div>
        ${buildTableMarkup(table.columns, table.rows)}
      </div>
    `).join("");
  }

  function buildTableMarkup(columns, rows) {
    if (!rows || !rows.length) {
      return '<div class="analytics-warning-item">Немає даних.</div>';
    }
    return `
      <table class="analytics-table">
        <thead>
          <tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              ${columns.map((column) => {
                const value = row[column.key];
                const rendered = column.formatter ? column.formatter(value) : value;
                return `<td>${escapeHtml(String(rendered ?? "—"))}</td>`;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function drawChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return;
    const existing = state.charts[canvasId];
    if (existing) existing.destroy();
    state.charts[canvasId] = new Chart(canvas.getContext("2d"), {
      ...config,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "rgba(226,232,240,0.78)" },
          },
        },
        scales: {
          x: {
            ticks: { color: "rgba(148,163,184,0.88)" },
            grid: { color: "rgba(148,163,184,0.12)" },
          },
          y: {
            ticks: { color: "rgba(148,163,184,0.88)" },
            grid: { color: "rgba(148,163,184,0.12)" },
          },
          y1: {
            position: "right",
            ticks: { color: "rgba(148,163,184,0.88)" },
            grid: { drawOnChartArea: false },
          },
        },
        ...config.options,
      },
    });
  }

  function lineOptions() {
    return {
      interaction: { mode: "index", intersect: false },
    };
  }

  function barOptions() {
    return {
      indexAxis: "x",
    };
  }

  function totalFromClarityMetric(rows, fieldName) {
    if (!rows || !rows.length) return 0;
    return rows.reduce((sum, row) => {
      const raw = row[fieldName] || row.value || row.totalSessionCount || 0;
      return sum + (Number(raw) || 0);
    }, 0);
  }

  function formatInt(value) {
    return Number(value || 0).toLocaleString("uk-UA");
  }

  function formatMoney(value) {
    return `${formatInt(Math.round(Number(value || 0)))} ₴`;
  }

  function formatPercent(value, suffix) {
    const numeric = Number(value || 0);
    const formatted = Number.isInteger(numeric) ? numeric.toLocaleString("uk-UA") : numeric.toLocaleString("uk-UA", { maximumFractionDigits: 2 });
    return suffix ? `${formatted}%` : formatted;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
