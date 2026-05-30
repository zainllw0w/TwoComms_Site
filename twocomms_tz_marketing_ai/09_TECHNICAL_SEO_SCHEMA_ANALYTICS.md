# Техническое SEO, schema и аналитика

## 1. Цель

Сделать сайт понятным для Google, AI-поиска и пользователя. Техническая часть не заменяет сильные тексты, но помогает им работать.

## 2. Срочные SEO-проверки

1. Убрать/закрыть тестовую статью `111`.
2. Проверить sitemap.
3. Проверить robots.txt.
4. Проверить canonical для товаров с параметрами цвета/размера.
5. Проверить индексацию UA/RU/EN версий, если они есть.
6. Проверить hreflang.
7. Проверить 404/редиректы.
8. Проверить скорость мобильной версии.
9. Проверить alt-тексты изображений.
10. Проверить Open Graph для Telegram/Facebook.

## 3. Structured data

Добавить или проверить:

### Organization schema

Для бренда:

- name: TwoComms;
- url;
- logo;
- sameAs: social links;
- contactPoint;
- founder, если корректно реализуемо.

### Product schema

Для карточек товаров:

- name;
- image;
- description;
- brand;
- sku;
- offers;
- priceCurrency UAH;
- availability;
- aggregateRating, только если есть реальные отзывы.

### BreadcrumbList

Для навигации.

### Article schema

Для блога.

### FAQPage schema

Для FAQ-блоков на статьях, custom page и FAQ.

## 4. Merchant / товарные данные

Если подключается Google Merchant Center:

- корректные цены;
- наличие;
- изображения;
- описание;
- доставка;
- возврат/обмен;
- бренд;
- категории.

## 5. Analytics events

### Главная

- hero_catalog_click;
- hero_custom_click;
- route_catalog_click;
- route_custom_click;
- route_about_click;
- survey_start;
- survey_complete.

### Каталог

- category_view;
- filter_used;
- product_click;
- add_to_cart;
- size_select;
- color_select.

### Custom

- custom_start;
- custom_base_selected;
- custom_zone_selected;
- custom_file_upload;
- custom_quantity_selected;
- custom_submit;
- custom_contact_manager_click.

### Checkout

- begin_checkout;
- promo_apply;
- purchase;
- checkout_error.

### Loyalty

- register_click;
- register_complete;
- login_click;
- points_info_click;
- review_submit.

## 6. KPI

### Первые 30 дней после внедрения

Сравнить:

- CTR hero → catalog;
- CTR hero → custom;
- survey start rate;
- survey completion rate;
- registration after survey;
- add to cart rate;
- custom submit rate;
- organic impressions;
- pages indexed;
- average engagement time.

## 7. A/B тесты

Если возможно, тестировать:

### Hero H1

A:

> TwoComms — український streetwear з кодом продовження

B:

> TwoComms — одяг з кодом продовження

### CTA

A:

> Дивитись дропи

B:

> Перейти в каталог

### Survey text

A:

> Допоможи зробити TwoComms точнішим — отримай 200 грн

B:

> Пройди опитування й отримай промокод 200 грн

## 8. Прогноз

Техническое SEO особенно важно для товарных страниц, блога и AI-поиска. Хорошая schema не гарантирует рост сама по себе, но помогает Google и другим системам правильно понимать товары, бренд и статьи.
