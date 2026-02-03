# DTF Subdomain — i18n Spec

## Languages
- Default: Ukrainian (uk)
- Secondary: Russian (ru)
- Planned: English (en) — после финализации контента.

## Implementation
- Используем Django i18n (`gettext`, `{% trans %}`) в шаблонах DTF.
- Языковой переключатель (cookie + query param) на страницах DTF.
- RU переводы оформляются в `dtf/locale/ru/LC_MESSAGES/django.po`.
- EN переводы оформляются в `dtf/locale/en/LC_MESSAGES/django.po` **после** утверждения финальных текстов.

## Acceptance Criteria
- [ ] UA по умолчанию.
- [ ] Переключение на RU сохраняется в cookie.
- [ ] Ключевые строки на RU отображаются корректно.
- [ ] EN перевод выполняется после финализации контента.
