const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..', '..', '..');
const mainSource = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
const pdpTemplate = fs.readFileSync(
  path.join(root, 'twocomms', 'twocomms_django_theme', 'templates', 'pages', 'product_detail.html'),
  'utf8'
);
const headerTemplate = fs.readFileSync(
  path.join(root, 'twocomms', 'twocomms_django_theme', 'templates', 'partials', 'header.html'),
  'utf8'
);
const cargoPartial = fs.readFileSync(
  path.join(root, 'twocomms', 'twocomms_django_theme', 'templates', 'partials', 'add_to_cart_cargo_scene.html'),
  'utf8'
);

test('live product triggers expose cargo scenes without replacing their existing labels', () => {
  assert.match(pdpTemplate, /class="tc-add-btn"[\s\S]*data-add-to-cart=/);
  assert.match(pdpTemplate, /class="tc-sticky-add-btn"[\s\S]*data-pdp-sticky-add/);
  assert.match(pdpTemplate, /data-cargo-idle/);
  assert.match(pdpTemplate, /partials\/add_to_cart_cargo_scene\.html/g);
  assert.match(cargoPartial, /data-cargo-scene/);
  assert.match(cargoPartial, /data-cargo-done/);
});

test('cargo success opens mini-cart only after the scene completion gate', () => {
  const handlerStart = mainSource.indexOf("document.addEventListener('click', (e) => {", mainSource.indexOf('window.__twcRunCargoDropAnimation'));
  assert.ok(handlerStart >= 0);
  const handlerEnd = mainSource.indexOf('// ====== PRODUCT DETAIL:', handlerStart);
  const handler = mainSource.slice(handlerStart, handlerEnd >= 0 ? handlerEnd : handlerStart + 20000);
  const animationStart = handler.indexOf('runCargoDropAnimation(btn)');
  const requestStart = handler.indexOf('addToCartRequest(false)');
  const animationFinish = handler.indexOf('await cargoAnimation.finish(');
  const miniRefresh = handler.indexOf('refreshMiniCart()');
  const miniOpen = handler.indexOf('openMiniCart({ skipRefresh: true })');
  assert.ok(animationStart >= 0 && requestStart >= 0 && animationStart < requestStart);
  assert.ok(miniRefresh >= 0 && animationFinish >= 0 && miniOpen > animationFinish);
  assert.doesNotMatch(handler.slice(0, requestStart), /openMiniCart/);
});

test('cargo phases keep the reference timing and delay cart entry until packing', () => {
  assert.match(mainSource, /is-cargo-scan'\), 1280\)/);
  assert.match(mainSource, /is-cargo-fold'\), 2000\)/);
  assert.match(mainSource, /Math\.max\(0, 3080 - elapsed\)/);
  assert.match(mainSource, /cargoWait\(button, 660\)/);
  assert.match(
    fs.readFileSync(path.join(root, 'twocomms', 'twocomms_django_theme', 'static', 'css', 'product-detail.css'), 'utf8'),
    /transition: transform 500ms cubic-bezier\(0\.22, 1\.3, 0\.36, 1\) 300ms/
  );
});

test('desktop and mobile cart triggers share the attention pulse hook', () => {
  assert.match(headerTemplate, /id="cart-toggle"[\s\S]*data-cart-attention/);
  assert.match(headerTemplate, /id="cart-toggle-mobile"[\s\S]*data-cart-attention/);
  assert.match(mainSource, /pulseHeaderCartAttention/);
  assert.match(mainSource, /document\.querySelectorAll\(\x27\[data-cart-attention\]\x27\)/);
});

test('reduced motion uses the same success gate without forcing a long animation', () => {
  assert.match(mainSource, /prefers-reduced-motion/);
  assert.match(mainSource, /isCargoReducedMotion/);
  assert.match(mainSource, /cargoReducedMotion/);
});
