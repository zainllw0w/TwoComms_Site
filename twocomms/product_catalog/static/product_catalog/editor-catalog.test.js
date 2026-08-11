const test = require("node:test");
const assert = require("node:assert/strict");
const catalog = require("./editor-catalog.js");

test("selected prints are grouped first without mutating storage order", () => {
  const input = [
    { id: 2, name: "Z", category: "B" },
    { id: 1, name: "A", category: "A" },
    { id: 3, name: "C", category: "A", is_active: false },
  ];
  const output = catalog.sortPrints(input, new Set([2]));
  assert.deepEqual(output.map((item) => item.id), [2, 1, 3]);
  assert.deepEqual(input.map((item) => item.id), [2, 1, 3]);
});

test("print labels expose only canonical artwork sources", () => {
  assert.equal(catalog.printSourceLabel({ image_source: "print" }), "Арт принта");
  assert.equal(catalog.printSourceLabel({ image_source: "variant" }), "Арт варіанту");
  assert.equal(catalog.printSourceLabel({ image_source: "product" }), "Artwork відсутній");
  assert.equal(catalog.printStateLabel({ is_active: false }, false), "Архів");
  assert.equal(catalog.printStateLabel({ is_active: false }, true), "Вибрано");
});

test("print search exposes a zero-results state only for a non-empty query", () => {
  assert.equal(catalog.shouldShowPrintEmpty(0, "225"), true);
  assert.equal(catalog.shouldShowPrintEmpty(0, ""), false);
  assert.equal(catalog.shouldShowPrintEmpty(2, "225"), false);
});

test("keyboard reorder moves one product without mutating the source list", () => {
  const input = ["225", "127", "streetwear"];
  assert.deepEqual(catalog.reorderIds(input, "streetwear", "up"), ["225", "streetwear", "127"]);
  assert.deepEqual(catalog.reorderIds(input, "225", "up"), input);
  assert.deepEqual(input, ["225", "127", "streetwear"]);
});

test("brigade children derive only brigades while military stays manual", () => {
  const rows = [
    { slug: "military", parent_slug: "", order: 10 },
    { slug: "brigades", parent_slug: "", order: 20 },
    { slug: "225", parent_slug: "brigades", order: 30 },
    { slug: "127", parent_slug: "brigades", order: 31 },
    { slug: "streetwear", parent_slug: "", order: 40 },
  ];

  const groups = catalog.groupCollections(rows);
  const effective = catalog.derivedCollectionSlugs(rows, new Set(["225"]));

  assert.deepEqual(groups.map((group) => group.slug), ["military", "brigades", "streetwear"]);
  assert.deepEqual(groups[1].children.map((item) => item.slug), ["225", "127"]);
  assert.deepEqual(Array.from(effective), ["brigades"]);
  assert.equal(effective.has("military"), false);
});

test("selected brigade leaf removes only its redundant parent", () => {
  const rows = [
    { slug: "military", parent_slug: "", order: 10 },
    { slug: "brigades", parent_slug: "", order: 20 },
    { slug: "225", parent_slug: "brigades", order: 30 },
  ];

  const selected = catalog.canonicalCollectionSlugs(
    rows,
    new Set(["military", "brigades", "225"]),
  );

  assert.deepEqual(Array.from(selected), ["military", "225"]);
});
