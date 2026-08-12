const assert = require("node:assert/strict");
const test = require("node:test");

require("../twocomms/twocomms_django_theme/static/js/custom-print-render-plan.js");

const plan = globalThis.CustomPrintRenderPlan;

test("render signatures are key-order independent and dirty only affected domains", () => {
  const first = plan.signature({
    navigation: { current: "mode", done: [] },
    content: { product: { type: null }, contact: { value: "" } },
    pricing: { quantity: 0 },
    preview: { color: null, view: "front" },
  });
  const reordered = plan.signature({
    preview: { view: "front", color: null },
    pricing: { quantity: 0 },
    content: { contact: { value: "" }, product: { type: null } },
    navigation: { done: [], current: "mode" },
  });
  assert.deepEqual(reordered, first);

  const changed = plan.signature({
    navigation: { current: "product", done: ["mode"] },
    content: { product: { type: "hoodie" }, contact: { value: "" } },
    pricing: { quantity: 0 },
    preview: { color: null, view: "front" },
  });
  assert.deepEqual([...plan.dirtyDomains(first, changed)].sort(), ["content", "navigation"]);
});

test("memoized pricing reuses the exact result until its canonical key changes", () => {
  let calls = 0;
  const pricing = plan.memoize((key) => {
    calls += 1;
    return { key, final_total: calls * 100 };
  });
  const first = pricing("product|hoodie|qty=1");
  const second = pricing("product|hoodie|qty=1");
  const third = pricing("product|hoodie|qty=2");
  assert.strictEqual(second, first);
  assert.notStrictEqual(third, first);
  assert.equal(calls, 2);
});

test("refresh gate coalesces repeated refresh requests into one flush", () => {
  const flushed = [];
  const gate = plan.createRefreshGate((domains) => flushed.push([...domains].sort()));
  gate.request(["preview"]);
  gate.request(["navigation", "preview"]);
  gate.flush();
  assert.deepEqual(flushed, [["navigation", "preview"]]);
  gate.flush();
  assert.deepEqual(flushed, [["navigation", "preview"]]);
});
