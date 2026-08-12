const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

test("RUM reports INP timing attribution once without serializing target text", async () => {
  const observers = [];
  const listeners = {};
  const beacons = [];
  class BlobStub {
    constructor(parts) { this.body = parts.join(""); }
    async text() { return this.body; }
  }
  class PerformanceObserverStub {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe(options) { this.type = options.type; }
  }
  const context = {
    Blob: BlobStub,
    PerformanceObserver: PerformanceObserverStub,
    document: {
      prerendering: false,
      visibilityState: "visible",
      documentElement: { dataset: {} },
      addEventListener(name, callback) { listeners[name] = callback; },
    },
    location: { href: "https://twocomms.shop/custom-print/" },
    navigator: {
      userAgentData: { mobile: true },
      sendBeacon(url, blob) { beacons.push({ url, blob }); return true; },
    },
    performance: {
      getEntriesByType(type) { return type === "navigation" ? [{ type: "navigate", responseStart: 120 }] : []; },
    },
    addEventListener() {},
    setTimeout,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../twocomms/twocomms_django_theme/static/js/rum.js"), "utf8"), context);

  const eventObserver = observers.find((observer) => observer.type === "event");
  assert.ok(eventObserver);
  eventObserver.callback({ getEntries: () => [{
    entryType: "event",
    name: "click",
    startTime: 100,
    processingStart: 112,
    processingEnd: 170,
    duration: 180,
    interactionId: 7,
    target: { tagName: "BUTTON", id: "buy", textContent: "secret customer data" },
  }] });
  context.document.visibilityState = "hidden";
  listeners.visibilitychange();
  listeners.pagehide?.();
  assert.equal(beacons.length, 1);
  const payload = JSON.parse(await beacons[0].blob.text());
  assert.equal(payload.metrics.INP, 180);
  assert.equal(payload.metrics.INP_inputDelay, 12);
  assert.equal(payload.metrics.INP_processingDuration, 58);
  assert.equal(payload.metrics.INP_presentationDelay, 110);
  assert.equal(payload.metrics.INP_interactionTarget, "button#buy");
  assert.equal(Object.values(payload.metrics).some((value) => String(value).includes("secret customer")), false);
});
