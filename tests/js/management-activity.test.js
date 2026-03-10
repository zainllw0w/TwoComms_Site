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
  'management-activity.js',
);

const scriptSource = fs.readFileSync(scriptPath, 'utf8');

async function runManagementActivity({
  cookie = '',
  hiddenCsrfToken = '',
  metaCsrfToken = '',
  url = '/activity/pulse/',
} = {}) {
  const fetchCalls = [];
  const dateValues = [0, 0, 15_000];

  const document = {
    body: { dataset: { activityPulseUrl: url } },
    cookie,
    visibilityState: 'visible',
    hasFocus: () => true,
    addEventListener: () => {},
    querySelector: (selector) => {
      if (selector === 'meta[name="csrf-token"]' && metaCsrfToken) {
        return {
          getAttribute: (name) => (name === 'content' ? metaCsrfToken : null),
        };
      }
      if (selector === '[name="csrfmiddlewaretoken"]' && hiddenCsrfToken) {
        return { value: hiddenCsrfToken };
      }
      return null;
    },
  };

  const window = {
    addEventListener: () => {},
  };

  const sandbox = {
    document,
    window,
    fetch: async (requestUrl, options = {}) => {
      fetchCalls.push({ requestUrl, options });
      return { ok: true, status: 200 };
    },
    setTimeout: (fn) => {
      fn();
      return 1;
    },
    setInterval: () => 1,
    clearInterval: () => {},
    Math,
    JSON,
    Promise,
    Date: {
      now: () => (dateValues.length ? dateValues.shift() : 15_000),
    },
    console,
  };

  window.fetch = sandbox.fetch;
  window.setTimeout = sandbox.setTimeout;
  window.setInterval = sandbox.setInterval;
  window.clearInterval = sandbox.clearInterval;
  window.document = document;

  vm.runInNewContext(scriptSource, sandbox, { filename: 'management-activity.js' });
  await Promise.resolve();

  return fetchCalls;
}

test('activity pulse uses DOM csrf token when duplicate csrf cookies exist', async () => {
  const domToken = 'A'.repeat(64);
  const cookie = `foo=1; csrftoken=${'b'.repeat(32)}; theme=dark; csrftoken=${'c'.repeat(32)}`;

  const fetchCalls = await runManagementActivity({
    cookie,
    hiddenCsrfToken: domToken,
  });

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].requestUrl, '/activity/pulse/');
  assert.equal(fetchCalls[0].options.headers['X-CSRFToken'], domToken);
});

test('activity pulse keeps using a valid csrf cookie even when csrftoken appears twice', async () => {
  const firstToken = 'd'.repeat(32);
  const secondToken = 'e'.repeat(32);
  const cookie = `foo=1; csrftoken=${firstToken}; theme=dark; csrftoken=${secondToken}`;

  const fetchCalls = await runManagementActivity({ cookie });

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].options.headers['X-CSRFToken'], firstToken);
});
