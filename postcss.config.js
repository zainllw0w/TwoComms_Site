const purgecss = require('@fullhuman/postcss-purgecss').default;
const cssnano = require('cssnano');

module.exports = {
  plugins: [
    purgecss({
      content: [
        './twocomms/twocomms_django_theme/templates/**/*.html',
        './twocomms/storefront/templates/**/*.html',
        './twocomms/orders/templates/**/*.html',
        './twocomms/accounts/templates/**/*.html',
        './twocomms/twocomms_django_theme/static/js/**/*.js',
      ],
      defaultExtractor: (content) => content.match(/[\w-/:]+(?<!:)/g) || [],
      safelist: {
        standard: [
          // Состояния, которые навешиваются динамически и могут не встретиться в шаблоне
          'show',
          'fade',
          'collapsing',
          'collapsed',
          'modal-open',
          'modal-backdrop',
          'offcanvas',
          'offcanvas-backdrop',
          'open',
          'active',
          'is-active',
          'is-open',
          'is-visible',
          'reveal-ready',
          'perf-lite',
          'effects-lite',
          'effects-high',
          'script-loaded',
          'script-error',
          'loading',
          'loaded',
          'error',
          'success',
          // Критичные классы для анимаций reveal (добавлены 2025-12-08)
          'visible',
          'stagger-item',
          'reveal',
          'reveal-fast',
          'reveal-stagger',
          // Hero секция - логотип и частицы (добавлены 2025-12-08)
          'hero-logo-bg',
          'hero-logo-image',
          'hero-particles',
          'hero-glow',
          'particle',
          // Цены и анимации (добавлены 2025-12-08)
          'price-text',
          'price-row',
          'fw-semibold',
          // Декоративные элементы
          'floating-logo',
          'featured-particles',
          'dark-particles',
          'featured-glow',
          'dark-glow',
        ],
        greedy: [
          /^toast/,
          /^tooltip/,
          /^popover/,
          /^dropdown/,
          /^modal/,
          // Сохраняем все hero-* и logo-* классы
          /^hero-/,
          /^logo-/,
          // Сохраняем все price-* классы
          /^price-/,
          // Сохраняем все particle и glow классы
          /^particle/,
          /^glow/,
          /^floating-/,
          /^featured-/,
          /^dark-/,
        ],
        // Сохраняем keyframes анимации
        keyframes: true,
      },
    }),
    require('autoprefixer'),
    cssnano({
      preset: ['default', { discardComments: { removeAll: true } }],
    }),
  ],
};
