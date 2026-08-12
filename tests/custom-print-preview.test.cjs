const assert = require("node:assert/strict");
const test = require("node:test");

require("../twocomms/twocomms_django_theme/static/js/custom-print-preview.js");
require("../twocomms/twocomms_django_theme/static/js/custom-print-state.js");

const {
  boxForFormat,
  computeZoneBox,
  requirementsForPlacement,
  resolveGarmentRender,
  viewForPlacement,
} = globalThis.CustomPrintPreview;
const { groups, fromInternal, firstInternal, progressIndex } = globalThis.CustomPrintStateTools;

const formats = {
  A6: { width_mm: 105, height_mm: 148 },
  A5: { width_mm: 148, height_mm: 210 },
  A4: { width_mm: 210, height_mm: 297 },
  A3: { width_mm: 297, height_mm: 420 },
  A2: { width_mm: 420, height_mm: 594 },
};

test("ISO preview zones preserve physical aspect ratio within 0.5 percent", () => {
  const calibration = {
    garment_width_mm: 600,
    zones: { body: { width: 50 } },
  };

  for (const [name, dimensions] of Object.entries(formats)) {
    const box = computeZoneBox(dimensions, calibration, { width: 1200, height: 1400 });
    const renderedRatio = (box.width * 1200) / (box.height * 1400);
    const physicalRatio = dimensions.width_mm / dimensions.height_mm;
    const error = Math.abs(renderedRatio - physicalRatio) / physicalRatio;
    assert.ok(error <= 0.005, `${name} ratio error was ${(error * 100).toFixed(4)}%`);
  }
});

test("state tools expose the established eight-stage journey", () => {
  assert.deepEqual(
    groups.map((group) => group.key),
    ["format", "garment", "config", "placement", "artwork", "quantity", "gift", "contact"],
  );
  assert.equal(fromInternal("config"), "config");
  assert.equal(fromInternal("gift"), "gift");
  assert.equal(firstInternal("config"), "config");
  assert.equal(progressIndex("gift"), 6);
});

test("special placements resolve their garment side without mutating stage state", () => {
  assert.equal(viewForPlacement({ placement_key: "hem_back" }), "back");
  assert.equal(viewForPlacement({ placement_key: "hem_front" }), "front");
  assert.equal(viewForPlacement({ placement_key: "shoulder_left" }), "front");
  assert.equal(viewForPlacement({ placement_key: "shoulder_right" }), "front");
});

test("hem text mode does not require an artwork file", () => {
  assert.deepEqual(requirementsForPlacement({ zone: "hem", mode: "text" }), { requiresFile: false });
  assert.deepEqual(requirementsForPlacement({ zone: "hem", mode: "A6+" }), { requiresFile: true });
});

test("A3 plus remains larger than A3 without filling the entire garment", () => {
  assert.ok(boxForFormat("A3+").scale > boxForFormat("A3").scale);
  assert.ok(boxForFormat("A3+").scale < 0.92);
});

test("missing garment color resolves to a declared fallback without mutating selection", () => {
  const assets = {
    "tshirt:regular": {
      black: { front: { avif: "black.avif", webp: "black.webp" } },
      white: { front: { avif: "white.avif", webp: "white.webp" } },
    },
  };
  const state = { product: { color: "khaki" } };

  assert.deepEqual(resolveGarmentRender(assets, "tshirt:regular", state.product.color), {
    selectedColor: "khaki",
    previewColor: "white",
    fallbackUsed: true,
    sources: assets["tshirt:regular"].white,
  });
  assert.equal(state.product.color, "khaki");
});

test("production regular tshirt fallback reports the black base it actually renders", () => {
  const assets = {
    "tshirt:regular": {
      black: { front: { avif: "black.avif", webp: "black.webp" } },
    },
  };

  assert.deepEqual(resolveGarmentRender(assets, "tshirt:regular", "milk"), {
    selectedColor: "milk",
    previewColor: "black",
    fallbackUsed: true,
    sources: assets["tshirt:regular"].black,
  });
});

test("preview render is a no-op when sources and overlays are unchanged", () => {
  const previousDocument = globalThis.document;
  const previousNavigator = globalThis.navigator;
  const previousSetTimeout = globalThis.setTimeout;
  const previousRaf = globalThis.requestAnimationFrame;
  const preloads = [];
  const rafs = [];

  function makeNode(attributes = {}) {
    return {
      attributes: { ...attributes },
      children: [],
      classList: {
        remove() {},
        add() {},
      },
      hidden: true,
      style: { setProperty() {}, removeProperty() {} },
      querySelector(selector) {
        const key = selector.match(/\[([^\]]+)\]/)?.[1];
        return this.children.find((child) => child.attributes?.[key] !== undefined) || null;
      },
      replaceChildren(...children) {
        this.children = children;
      },
      getAttribute(key) {
        return this.attributes[key] ?? null;
      },
      setAttribute(key, value) {
        this.attributes[key] = String(value);
      },
      addEventListener() {},
    };
  }

  const preview = makeNode({ "data-png-preview": "" });
  const garment = makeNode({ "data-preview-garment": "" });
  const avif = makeNode({ "data-preview-avif": "" });
  const webp = makeNode({ "data-preview-webp": "" });
  const lacing = makeNode({ "data-preview-lacing": "" });
  const zones = makeNode({ "data-preview-zones": "" });
  lacing.hidden = true;
  preview.children = [garment, avif, webp, lacing, zones];

  globalThis.document = {
    documentElement: { lang: "uk-UA" },
    createElement: () => makeNode(),
    head: { appendChild: (node) => preloads.push(node.href) },
  };
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { connection: { effectiveType: "2g", saveData: false } },
  });
  globalThis.requestAnimationFrame = (callback) => rafs.push(callback);
  globalThis.setTimeout = () => 0;

  const state = {
    product: { type: "tshirt", fit: "regular", color: "black" },
    ui: { stage_view: "front" },
    print: { zones: [], zone_options: {} },
  };
  const config = {
    custom_ref_preview_assets: {
      "tshirt:regular": {
        black: {
          front: { avif: "front.avif", webp: "front.webp" },
          back: { avif: "back.avif", webp: "back.webp" },
        },
      },
    },
    preview_assets: { "tshirt:regular": {} },
    preview_calibration: {
      "tshirt:regular": {
        garment_width_mm: 600,
        canvas: { width: 1200, height: 1400 },
        zones: { body: { width: 50 }, front: { x: 50, y: 30 }, back: { x: 50, y: 30 } },
      },
    },
    format_dimensions: { A4: { width_mm: 210, height_mm: 297 } },
    products: { tshirt: { label: "T-shirt", colors: [] } },
  };

  try {
    const controller = globalThis.CustomPrintPreview.create({
      root: { querySelectorAll: () => [preview] },
      config,
      getState: () => state,
    });
    controller.render();
    controller.render();
    assert.equal(preloads.length, 1, "front is warmed immediately; hidden back stays lazy");
    assert.equal(preloads[0], "front.avif");
    assert.equal(rafs.length, 1, "asset transition is scheduled only on the first render");
    assert.equal(zones.children.length, 0);
  } finally {
    globalThis.document = previousDocument;
    Object.defineProperty(globalThis, "navigator", { configurable: true, value: previousNavigator });
    globalThis.requestAnimationFrame = previousRaf;
    globalThis.setTimeout = previousSetTimeout;
  }
});

test("explicit back view warms the back source immediately", () => {
  const previousDocument = globalThis.document;
  const previousNavigator = globalThis.navigator;
  const previousRaf = globalThis.requestAnimationFrame;
  const preloads = [];

  function makeNode(attributes = {}) {
    return {
      attributes: { ...attributes },
      children: [],
      classList: { remove() {}, add() {} },
      hidden: true,
      style: { setProperty() {}, removeProperty() {} },
      querySelector() { return null; },
      replaceChildren() {},
      getAttribute(key) { return this.attributes[key] ?? null; },
      addEventListener() {},
    };
  }

  globalThis.document = {
    documentElement: { lang: "uk-UA" },
    createElement: () => makeNode(),
    head: { appendChild: (node) => preloads.push(node.href) },
  };
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { connection: { effectiveType: "2g", saveData: false } },
  });
  globalThis.requestAnimationFrame = () => {};
  const state = {
    product: { type: "tshirt", fit: "regular", color: "black" },
    ui: { stage_view: "back" },
    print: { zones: [], zone_options: {} },
  };
  const config = {
    custom_ref_preview_assets: {
      "tshirt:regular": {
        black: {
          front: { avif: "front.avif", webp: "front.webp" },
          back: { avif: "back.avif", webp: "back.webp" },
        },
      },
    },
    preview_assets: { "tshirt:regular": {} },
    preview_calibration: {
      "tshirt:regular": {
        garment_width_mm: 600,
        canvas: { width: 1200, height: 1400 },
        zones: { body: { width: 50 }, front: { x: 50, y: 30 }, back: { x: 50, y: 30 } },
      },
    },
    format_dimensions: {},
    products: { tshirt: { label: "T-shirt", colors: [] } },
  };

  try {
    const controller = globalThis.CustomPrintPreview.create({
      root: { querySelectorAll: () => [makeNode({ "data-png-preview": "" })] },
      config,
      getState: () => state,
    });
    controller.render();
    assert.deepEqual(preloads, ["back.avif"]);
  } finally {
    globalThis.document = previousDocument;
    Object.defineProperty(globalThis, "navigator", { configurable: true, value: previousNavigator });
    globalThis.requestAnimationFrame = previousRaf;
  }
});
