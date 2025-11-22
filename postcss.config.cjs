const { purgeCSSPlugin } = require('@fullhuman/postcss-purgecss');

module.exports = {
  plugins: [
    require('autoprefixer'),
    purgeCSSPlugin({
      content: [
        './twocomms/twocomms_django_theme/templates/**/*.html',
        './twocomms/twocomms_django_theme/static/js/**/*.js'
      ],
      safelist: [
        /^btn/, /^modal/, /^offcanvas/, /^nav/, /^navbar/, /^dropdown/, /^show$/,
        /^fade/, /^collapse/, /^alert/, /^badge/, /^toast/, /^carousel/, /^row/,
        /^col-/, /^g-/,
        /^fa/, /^fas/, /^far/, /^fab/,
        /^reveal/, /^stagger/, /^perf-lite/, /^effects-lite/, /^bg-/,
        /^text-/, /^border-/, /^d-/, /^align-/, /^justify-/, /^flex/,
        /^position-/, /^top-/, /^bottom-/, /^start-/, /^end-/, /^z-/,
        /^ratio/, /^object-fit/, /^w-/, /^h-/, /^min-vh/, /^max-vh/
      ],
      defaultExtractor: (content) => content.match(/[\w-/:()]+(?<!:)/g) || []
    })
  ]
};
