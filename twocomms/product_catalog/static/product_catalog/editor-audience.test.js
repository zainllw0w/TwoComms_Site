const test = require('node:test');
const assert = require('node:assert/strict');

let audience = {};
try {
  audience = require('./editor-audience.js');
} catch (_) {
  // RED until the shared browser/Node audience contract exists.
}

test('unisex remains canonical while men and women are derived for the editor', () => {
  assert.equal(typeof audience.canonicalAudienceCodes, 'function');
  assert.equal(typeof audience.effectiveAudienceCodes, 'function');

  assert.deepEqual(audience.canonicalAudienceCodes(['unisex', 'men', 'women']), ['unisex']);
  assert.deepEqual(audience.effectiveAudienceCodes(['unisex']), ['unisex', 'men', 'women']);
});

test('audience toggles update canonical state without persisting derived controls', () => {
  assert.equal(typeof audience.toggleAudienceCode, 'function');

  const unisex = audience.toggleAudienceCode([], 'unisex', true);
  assert.deepEqual(unisex, ['unisex']);
  assert.deepEqual(audience.effectiveAudienceCodes(unisex), ['unisex', 'men', 'women']);

  const cleared = audience.toggleAudienceCode(unisex, 'unisex', false);
  assert.deepEqual(cleared, []);

  assert.deepEqual(audience.toggleAudienceCode(cleared, 'men', true), ['men']);
});

test('audience helpers accept the Set state used by the editor', () => {
  assert.deepEqual(
    audience.effectiveAudienceCodes(new Set(['unisex'])),
    ['unisex', 'men', 'women']
  );
});
