# DTF Subdomain — Performance/SEO/Accessibility Spec

## Performance
- Ленивая загрузка изображений, skeleton loaders.
- Без тяжелых embeds (Instagram).
- Статика через WhiteNoise.

## SEO
- Title/Description/OG для каждой страницы.
- H1/H2 структура.
- Schema.org: Organization, Service/Product, FAQ.

## Accessibility
- Контраст, aria-labels, корректные label for.
- Клавиатурная навигация.
- respects `prefers-reduced-motion`.

## Acceptance Criteria
- [ ] SEO мета заполнены.
- [ ] Иконки/кнопки имеют aria-label.
- [ ] CSS учитывает prefers-reduced-motion.
