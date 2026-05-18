const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildFinalActionPolicy,
} = require("../twocomms/twocomms_django_theme/static/js/custom-print-submission-policy.js");

test("manager remains available when only artwork files are missing", () => {
  const policy = buildFinalActionPolicy({
    baseIssues: [],
    artworkIssues: ["Додайте готові макети для: На спині, Лівий рукав."],
    estimateRequired: false,
    isCustomerGarment: false,
  });

  assert.equal(policy.leadReady, true);
  assert.equal(policy.cartReady, false);
  assert.match(policy.leadHint, /можна додати пізніше/i);
});

test("manager stays blocked when a shared prerequisite is missing", () => {
  const policy = buildFinalActionPolicy({
    baseIssues: ["Заповніть імʼя, канал звʼязку і контакт."],
    artworkIssues: [],
    estimateRequired: false,
    isCustomerGarment: false,
  });

  assert.equal(policy.leadReady, false);
  assert.equal(policy.cartReady, false);
  assert.match(policy.leadHint, /Заповніть ім/i);
});

test("cart stays unavailable for manager-estimate products even if lead is allowed", () => {
  const policy = buildFinalActionPolicy({
    baseIssues: [],
    artworkIssues: [],
    estimateRequired: true,
    isCustomerGarment: false,
  });

  assert.equal(policy.leadReady, true);
  assert.equal(policy.cartReady, false);
  assert.match(policy.cartHint, /менеджерського прорахунку/i);
});

test("manager IS blocked when ready service has missing artwork files", () => {
  // CP-UX-2026-05-18: для service_kind=ready клієнт не повинен мати
  // можливість надіслати заявку без файлів — навіть менеджеру.
  const policy = buildFinalActionPolicy({
    baseIssues: [],
    artworkIssues: ["Додайте готові макети для: На спині."],
    estimateRequired: false,
    isCustomerGarment: false,
    serviceKind: "ready",
  });

  assert.equal(policy.leadReady, false);
  assert.equal(policy.cartReady, false);
  assert.match(policy.leadHint, /Додайте готові макети/);
});

test("manager IS blocked when adjust service has missing artwork files", () => {
  const policy = buildFinalActionPolicy({
    baseIssues: [],
    artworkIssues: ["Додайте макети для: На спині."],
    estimateRequired: false,
    isCustomerGarment: false,
    serviceKind: "adjust",
  });

  assert.equal(policy.leadReady, false);
  assert.match(policy.leadHint, /Додайте макети/);
});

test("manager remains available for design service even without files", () => {
  // service_kind=design — файли не потрібні, тільки brief.
  const policy = buildFinalActionPolicy({
    baseIssues: [],
    artworkIssues: [],
    estimateRequired: false,
    isCustomerGarment: false,
    serviceKind: "design",
  });

  assert.equal(policy.leadReady, true);
});
