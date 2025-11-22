const purgecss = require('@fullhuman/postcss-purgecss').default;

module.exports = {
    plugins: [
        require('autoprefixer'),
        purgecss({
            content: [
                './twocomms/twocomms_django_theme/templates/**/*.html',
                './twocomms/storefront/templates/**/*.html',
                './twocomms/orders/templates/**/*.html',
                './twocomms/accounts/templates/**/*.html',
                './twocomms/twocomms_django_theme/static/js/**/*.js',
            ],
            defaultExtractor: content => content.match(/[\w-/:]+(?<!:)/g) || [],
            safelist: []
        })
    ]
}
