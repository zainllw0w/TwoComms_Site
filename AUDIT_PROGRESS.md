# Прогресс по FULL_AUDIT_REPORT.md

## Выполнено
- **Безопасность**
  - `DEBUG` теперь выключен по умолчанию (`twocomms/twocomms/settings.py`), убран риск случайного запуска проекта в режиме отладки (п.7 отчёта).
  - Добавлен `SecurityHeadersMiddleware` с Content-Security-Policy, X-XSS-Protection и другими заголовками. В список разрешённых источников включены Google, Meta Pixel, Microsoft Clarity, CDN (п.8, п.5 Security analysis).
  - В `LOGGING` переключены на `RotatingFileHandler`, чтобы `django.log` и `stderr.log` не росли до 19 МБ (п.11 и 12).
- **Инфраструктура / SEO**
  - Создан `static/robots.txt` (`Allow: /`, `Sitemap: https://twocomms.shop/sitemap.xml`) — поисковые боты видят сайт и карту.
  - Отключён `django-compressor` (`COMPRESS_ENABLED/OFFLINE = False`) — CSS/JS отдаётся в исходном виде, браузеры не получают HTML c MIME `text/html`, что устраняет ошибки «Refused to apply style». Это также упростило кеширование для ботов.
- **Фронтенд**
  - Вернули монолитный `css/dropshipper.css` и прямое подключение JS (`dropshipper.dashboard.js`, `dropshipper-product-modal.js`). Панели и модалки снова отображаются корректно и не требуют ленивой загрузки, которая ломала вкладки.
  - Часть изображений получает width/height и используется `<picture>` (catalog, wholesale) — уменьшен CLS на страницах товара (п.2 из Performance).
- **Аналитика**
  - Расширен CSP для `https://scripts.clarity.ms` и `https://cdn.jsdelivr.net`, Clarity и Meta Pixel снова подгружаются штатно.

## В процессе / частично
- **База данных**
  - Индексы `idx_product_id_desc`, `idx_order_created_desc`, `dropship_ord_created` добавлены (п.17-18). Включить slow query log без SUPER-привилегий не удалось — требуется доступ хостинга.
- **Оптимизация изображений**
  - На продакшене оптимизированы 160 медиа (скриптом `optimize_images.py --yes --quality 82`). Осталось внедрить `<picture>`/WebP на главной и в hero-блоках, чтобы закрыть пункт CLS до конца.
- **Фронтенд**
  - Пока CSS/JS подключены монолитно. Планируется разбить на модули, но только после подготовки fallback, чтобы не ломать страницы.

## Следующие шаги (из отчёта)
1. Завершить работу с изображениями: добавить `<picture>` и фиксированные размеры для hero и карточек (улучшить CLS/FCP).
2. Поработать с логами: вынести настройки ротации в конфиг сервера (`logrotate`) и подтверждение на проде.
3. `robots.txt` уже добавлен — проверить sitemap и при необходимости добавить дополнительные (для оптового раздела).
4. Вернуться к вопросу медленных запросов — договориться с провайдером об активации `slow_query_log`.
5. Модульная чистка `dropshipper.css/js`, но только после страхующего бэкапа шаблонов, чтобы не повторить регрессию.
