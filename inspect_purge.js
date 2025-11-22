const purgecss = require('@fullhuman/postcss-purgecss');
console.log('Type:', typeof purgecss);
console.log('Value:', purgecss);
if (typeof purgecss === 'object') {
    console.log('Keys:', Object.keys(purgecss));
}
