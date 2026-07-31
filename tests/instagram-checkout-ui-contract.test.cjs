const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'twocomms/twocomms_django_theme/templates/pages/ig_checkout.html'), 'utf8');
const cssPath = path.join(root, 'twocomms/twocomms_django_theme/static/css/instagram-checkout.css');
const jsPath = path.join(root, 'twocomms/twocomms_django_theme/static/js/instagram-checkout.js');

test('checkout template uses isolated assets and semantic delivery controls', () => {
  assert.match(template, /instagram-checkout\.css/);
  assert.match(template, /instagram-checkout\.js/);
  assert.match(template, /data-np-form/);
  assert.match(template, /data-np-form="instagram"/);
  assert.match(template, /data-payment-submit/);
  assert.match(template, /id="ig-city"[^>]*role="combobox"[^>]*aria-haspopup="listbox"/);
  assert.match(template, /id="ig-warehouse"[^>]*role="combobox"[^>]*aria-haspopup="listbox"/);
  assert.match(template, /data-np-kind-toggle role="group"/);
  assert.match(template, /data-kind="all" aria-pressed="true"/);
  assert.match(template, /name="email"[^>]*aria-describedby/);
  assert.doesNotMatch(template, /name="email"[^>]*required/);
  assert.doesNotMatch(template, /<style[\s>]/i);
  assert.doesNotMatch(template, /<script>(?!\s*\{\{)/i);
});

test('checkout CSS is mobile safe and deliberately restrained', () => {
  assert.equal(fs.existsSync(cssPath), true);
  const css = fs.readFileSync(cssPath, 'utf8');
  const panelRule = [...css.matchAll(/\.ig-checkout-panel\s*\{([\s\S]*?)\}/g)]
    .find((match) => /animation:/.test(match[1]));
  assert.ok(panelRule, 'checkout panel rule must exist');
  assert.match(css, /aspect-ratio:\s*4\s*\/\s*5/);
  assert.match(css, /env\(safe-area-inset-bottom\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /min-height:\s*48px/);
  assert.match(css, /\.ig-kind button\s*\{[^}]*min-width:\s*44px/s);
  assert.match(css, /scroll-padding-bottom/);
  assert.match(panelRule[1], /animation:\s*ig-panel-fade/);
  assert.doesNotMatch(panelRule[1], /ig-settle/);
  assert.match(css, /\.is-field-focused\s+\.ig-payment-rail\s*\{[^}]*visibility:\s*hidden[^}]*opacity:\s*0/s);
  assert.match(css, /--ig-action:\s*#c64018/);
  assert.doesNotMatch(css, /max-height:\s*650px/);
  assert.doesNotMatch(css, /\.is-field-focused\s+\.ig-payment-rail\s*\{[^}]*transform:/s);
  assert.doesNotMatch(css, /(linear|radial|conic)-gradient\(/i);
  assert.doesNotMatch(css, /animation[^;]*infinite/i);
});

test('checkout JS copies fresh share URL and refreshes stale revisions', () => {
  assert.equal(fs.existsSync(jsPath), true);
  const source = fs.readFileSync(jsPath, 'utf8');
  assert.match(source, /data-share-url/);
  assert.match(source, /navigator\.clipboard/);
  assert.match(source, /visibilitychange/);
  assert.match(source, /TwoCommsNovaPoshta/);
  assert.match(source, /stopImmediatePropagation\(\)/);
  assert.match(source, /image\.complete && image\.naturalWidth === 0/);
  assert.doesNotMatch(source, /offer\/a\/\$\{/);
  assert.doesNotMatch(source, /console\.(log|debug|info)/);
});

test('Nova Poshta settlement metadata follows the checkout locale', () => {
  const selectorPath = path.join(root, 'twocomms/twocomms_django_theme/static/js/modules/nova-poshta-selector.js');
  const selector = fs.readFileSync(selectorPath, 'utf8');
  assert.match(selector, /function localizeSettlementType\(value, locale\)/);
  assert.match(selector, /localizeSettlementType\(current\.settlement_type, this\.locale\)/);
  assert.match(selector, /input\.removeAttribute\('aria-activedescendant'\)/);
  assert.match(selector, /item\.setAttribute\('aria-pressed', isActive \? 'true' : 'false'\)/);
  assert.match(selector, /params\.set\('locale', this\.locale\)/);
  assert.doesNotMatch(selector, /payload\.error \|\| this\.copy\.searchDisabled/);
  assert.match(selector, /ru:\s*\{[\s\S]*?city:\s*'Город'/);
  assert.match(selector, /en:\s*\{[\s\S]*?city:\s*'City'/);
});
