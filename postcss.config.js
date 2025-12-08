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
        ],
        greedy: [
          /^toast/,
          /^tooltip/,
          /^popover/,
          /^dropdown/,
          /^modal/,
        ],
      },
    }),
    require('autoprefixer'),
    cssnano({
      preset: ['default', { discardComments: { removeAll: true } }],
    }),
  ],
};
