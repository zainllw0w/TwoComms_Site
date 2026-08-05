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
