const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scriptPath = path.join(
  __dirname,
  '..',
  '..',
  'twocomms',
  'twocomms_django_theme',
  'static',
  'js',
  'admin-analytics-dashboard.js',
);

const scriptSource = fs.readFileSync(scriptPath, 'utf8');

function createClassList() {
  const active = new Set();
  return {
    add: (...tokens) => tokens.forEach((token) => active.add(token)),
    remove: (...tokens) => tokens.forEach((token) => active.delete(token)),
    toggle: (token, force) => {
      if (force === undefined) {
        if (active.has(token)) {
          active.delete(token);
          return false;
        }
        active.add(token);
        return true;
      }
      if (force) {
        active.add(token);
        return true;
      }
      active.delete(token);
      return false;
    },
    contains: (token) => active.has(token),
  };
}

async function renderTab(tabName, payload, options = {}) {
  const targets = {
    adminAnalyticsConfig: {
      textContent: JSON.stringify({
        apiBase: '/api/admin/analytics',
        filters: { period: 'month' },
        initialTab: tabName,
        initialData: {},
      }),
    },
    analyticsTabInput: {
      value: tabName,
    },
    analyticsPreserveLink: {
      href: '?section=stats',
      getAttribute(name) {
        return this[name];
      },
      setAttribute(name, value) {
        this[name] = value;
      },
    },
  };

  const idsByTab = {
    traffic: [
      'analyticsTrafficSources',
      'analyticsTrafficLanding',
      'analyticsTrafficBreakdowns',
      'analyticsGa4Summary',
    ],
    sales: ['analyticsSalesSummary', 'analyticsPaymentSplit', 'analyticsSalesTables'],
  };

  for (const id of idsByTab[tabName] || []) {
    targets[id] = { innerHTML: '' };
  }

  const tabButtons = [
    { dataset: { analyticsTab: 'overview' }, classList: createClassList(), addEventListener: () => {} },
    { dataset: { analyticsTab: 'traffic' }, classList: createClassList(), addEventListener: () => {} },
    { dataset: { analyticsTab: 'sales' }, classList: createClassList(), addEventListener: () => {} },
  ];
  const panels = [
    { dataset: { analyticsPanel: 'overview' }, classList: createClassList() },
    { dataset: { analyticsPanel: 'traffic' }, classList: createClassList() },
    { dataset: { analyticsPanel: 'sales' }, classList: createClassList() },
  ];

  const root = {
    querySelector: (selector) => {
      if (selector === '[data-analytics-tab-input]') return targets.analyticsTabInput;
      return null;
    },
    querySelectorAll: (selector) => {
      if (selector === '[data-analytics-tab]') return tabButtons;
      if (selector === '[data-analytics-panel]') return panels;
      if (selector === '[data-analytics-preserve-tab-link]') return [targets.analyticsPreserveLink];
      return [];
    },
  };

  const document = {
    getElementById: (id) => targets[id] || null,
    querySelector: (selector) => (selector === '[data-admin-analytics-root]' ? root : null),
  };

  const fetchImpl = options.fetchImpl || (async () => ({
    ok: true,
    json: async () => payload,
  }));

  const sandbox = {
    document,
    window: {
      document,
      setInterval,
      clearInterval,
      location: { href: 'https://twocomms.shop/admin-panel/?section=stats' },
      history: { replaceState: () => {} },
    },
    fetch: fetchImpl,
    URL,
    URLSearchParams,
    Promise,
    JSON,
    Math,
    Number,
    String,
    Array,
    Object,
    console,
    setTimeout,
    clearTimeout,
  };

  vm.runInNewContext(scriptSource, sandbox, { filename: 'admin-analytics-dashboard.js' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));

  return targets;
}

test('traffic tables include responsive class and per-cell labels for mobile rendering', async () => {
  const targets = await renderTab('traffic', {
    data: {
      top_sources: [
        {
          utm_source: 'google',
          utm_medium: 'cpc',
          source_class: 'paid',
          sessions: 42,
        },
      ],
      landing_pages: [],
      referrers: [],
      devices: [],
      browsers: [],
      geo: [],
      ga4_snapshot: { channel_groups: { rows: [] } },
      source_classes: [],
    },
  });

  assert.match(targets.analyticsTrafficSources.innerHTML, /analytics-table--responsive/);
  assert.match(targets.analyticsTrafficSources.innerHTML, /data-label="Source"/);
  assert.match(targets.analyticsTrafficSources.innerHTML, /data-label="Medium"/);
  assert.match(targets.analyticsTrafficSources.innerHTML, /data-label="Сесії"/);
});

test('composite sales tables also include per-cell labels for stacked mobile rows', async () => {
  const targets = await renderTab('sales', {
    data: {
      summary: {},
      payment_split: [],
      daily_series: { labels: [], revenue: [], orders: [] },
      source_ltv: [
        {
          label: 'Organic',
          sessions: 20,
          orders: 3,
          ltv: 900,
        },
      ],
      top_products: [
        {
          title: 'Sticker Pack',
          items_sold: 5,
          revenue: 1200,
        },
      ],
    },
  });

  assert.match(targets.analyticsSalesTables.innerHTML, /analytics-table--responsive/);
  assert.match(targets.analyticsSalesTables.innerHTML, /data-label="Канал"/);
  assert.match(targets.analyticsSalesTables.innerHTML, /data-label="LTV"/);
  assert.match(targets.analyticsSalesTables.innerHTML, /data-label="Товар"/);
});

test('failed widget fetch renders inline warning instead of silent console-only failure', async () => {
  const targets = await renderTab('traffic', null, {
    fetchImpl: async () => ({
      ok: false,
      status: 503,
      json: async () => ({}),
    }),
  });

  assert.match(targets.analyticsTrafficSources.innerHTML, /HTTP 503 while loading acquisition/);
});

test('tab activation keeps current analytics tab in hidden form input and reset links', async () => {
  const targets = await renderTab('sales', {
    data: {
      summary: {},
      payment_split: [],
      daily_series: { labels: [], revenue: [], orders: [] },
      source_ltv: [],
      top_products: [],
    },
  });

  assert.equal(targets.analyticsTabInput.value, 'sales');
  assert.match(targets.analyticsPreserveLink.href, /analytics_tab=sales/);
});
