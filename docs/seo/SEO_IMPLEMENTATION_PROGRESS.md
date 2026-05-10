# SEO Implementation Progress Tracker

> Этот файл — единый источник правды для прогресса по плану `docs/seo/TWOCOMMS_SEO_IMPLEMENTATION_PLAN_2026-05-10.md` и расширенному плану `~/.windsurf/plans/twocomms-seo-full-implementation-3dcd3f.md`. Обновлять после КАЖДОГО завершённого шага.

**Phone:** `+380966543212`
**LocalBusiness strategy:** OnlineStore + areaServed=UA, без физ. адреса.
**Reviews:** полная модель (звёзды + фото + verified_purchase), guest=premoderation, registered_with_purchase=auto-approve, AggregateRating только при ≥3 одобренных.

---

## Status Legend
- [ ] pending
- [~] in progress
- [x] done
- [!] blocked / needs decision

---

## PR-1: P0 cleanup [in progress — code done, awaiting deploy verify]
- [x] T1.1 single-line `{# #}` уже валидны Django; multi-line преобразованы в предыдущем коммите (b5c07041)
- [x] T1.2 `test_product_page_does_not_leak_template_syntax` зелёный
- [x] T2.1 Удалён visible fake rating `4.9 (45 відгуків)` в `tc-product-meta` и `tc-related-rating 4.9`
- [x] T2.2 `product_rating_schema` переписан: AggregateRating рендерится только при `review_count >= 3`; не вызывается в шаблонах PDP
- [x] T2.3 Регрессии добавлены: `test_product_page_does_not_render_fake_aggregate_rating`
- [x] T3.1 Удалён inline Organization из `base.html`; добавлены `{% organization_schema %}` + `{% website_schema %}` глобально
- [x] T3.2 `online_store_schema` теперь использует +380966543212, areaServed=UA, OnlineStore type, parentOrganization @id
- [x] T3.3 Старый placeholder `local_business_schema` заменён на alias к `online_store_schema`
- [x] T3.4 Регрессия: `test_product_page_does_not_emit_legacy_inline_organization` (count==1)
- [x] T4.1 Удалён `<meta name="keywords">` из `base.html` и `partials/seo_meta.html`
- [ ] T4.2 Production curl verify (после деплоя)

## PR-2: variants/canonical
- [ ] T5.1 `ProductVariantSitemap` — исключить size-only one-segment URLs
- [ ] T5.2 Регрессионный тест sitemap (size-only нет, color/fit есть)
- [ ] T6.1 `variant_meta.build_variant_meta` — size-only one-segment → canonical=base, is_self_canonical=False
- [ ] T6.2 Тесты canonical (`/product/x/m/`→base, `/product/x/black/`→self, `/product/x/oversize/`→self, `/product/x/black/m/`→base)
- [ ] T7.1 `generate_product_schema` принимает canonical_path/selected_variant
- [ ] T7.2 Product schema `url` совпадает с canonical
- [ ] T7.3 Color image для Product schema/OG/Twitter

## PR-3: categories
- [ ] T8.1 Добавить поля `seo_title`, `seo_h1`, `seo_description` в `Category`
- [ ] T8.2 Обновить `CategoryAdmin`
- [ ] T8.3 Миграция
- [ ] T8.4 `pages/catalog.html` — fallback для title/H1/description/OG/Twitter
- [ ] T9.1 Уникальная копия для `tshirts`, `hoodie`, `long-sleeve` (через админ/data migration)
- [ ] T9.2 Production verify 3 категорий
- [ ] T10.1 Сменить дублирующий H2 "Створи свій дизайн" на категорийный CTA
- [ ] T10.2 `general_catalog_seo` — убрать ссылки на `?color=` (noindex)
- [ ] T10.3 Регрессия: top query URLs без `?color=`

## PR-4: reviews system (новый блок)
- [ ] R1 Создать app `reviews` (или модуль в storefront), settings INSTALLED_APPS
- [ ] R2 Модели: Review, ReviewImage (max 5), ReviewVote
- [ ] R3 Миграции
- [ ] R4 Forms: ReviewForm (auth + guest), валидация фото, honeypot
- [ ] R5 Views: create, vote, helpful; rate-limit для гостей
- [ ] R6 URL routes
- [ ] R7 Admin: pending list, approve/reject bulk, moderation_note
- [ ] R8 Email/Telegram notify модератору о pending
- [ ] R9 Permissions: registered может оставить отзыв только если есть оплаченный заказ с product
- [ ] R10 Сводка/гистограмма/фильтры/сортировка в `pages/product_detail.html`
- [ ] R11 Карточка отзыва (verified badge, фото lightbox, helpful)
- [ ] R12 Личный кабинет — раздел "Мої відгуки"
- [ ] R13 `aggregate_rating_for_product()` helper, AggregateRating только при ≥3 approved
- [ ] R14 Review JSON-LD nested в Product (топ-5)
- [ ] R15 IndexNow trigger при approve (signal post_save)
- [ ] R16 Тесты: модерация, verified, rating threshold, photo limit, regression PDP

## PR-5: content/FAQ
- [ ] T11.1 Удалить `CITY_KEYWORDS` из `top_queries`
- [ ] T11.2 Заменить SEO-видимый текст на buyer-facing
- [ ] T11.3 Тест без city/SEO-операционных слов
- [ ] T12.1 Не автогенерировать universal ProductFAQ
- [ ] T12.2 FAQ остаётся UI, но без FAQPage JSON-LD при дублях
- [ ] T12.3 FAQPage schema на /faq/, /delivery/, /povernennya-ta-obmin/, категорийных
- [ ] T13.1 PDP cross-links → support pages
- [ ] T13.2 Support pages → category links
- [ ] T14 Топ-20 unique copy (отдельным трекингом, требует ручной выверки)

## PR-6: schema graph + feed + images + IndexNow
- [ ] T15.1 PDP `@graph`: Org, WebSite, Breadcrumb, Product (+rating), FAQPage if unique
- [ ] T15.2 Category/Home `@graph`
- [ ] T16.1 Image sitemap: main + display + gallery + color variants, dedupe
- [ ] T16.2 Команда отчёта о продуктах без картинок
- [ ] T17.1 `g:gtin` если barcode есть
- [ ] T17.2 `g:custom_label_0..4`
- [ ] T17.3 OOS strategy alignment
- [ ] T18.1 Verify INDEXNOW_ENABLED/KEY на проде
- [ ] T18.2 Dry-run reindex_indexnow
- [ ] T18.3 Логи accepted submissions

## PR-7: trust + a11y
- [ ] T19.1 Factual badges около CTA в PDP
- [ ] T19.2 Линки на support pages
- [ ] T20.1 Lighthouse + ручная проверка ключевых страниц
- [ ] T20.2 Touch targets, focus, contrast, lazy-load reviews

---

## Cross-cutting (этап G)
- [ ] G1 Footer/contacts: tel:+380966543212
- [ ] G2 online_store_schema use phone
- [ ] G3 Order email/Telegram notify use phone

---

## Notes / Decisions
- Phone подтверждён: +380966543212.
- Reviews — отдельное Django app `reviews` для изоляции.
- AggregateRating threshold: 3 одобренных отзыва.
- Photos per review: max 5.
- Verified purchase: проверка через `Order` с `payment_status=paid` и `OrderItem.product == product`.
- Guests: pending + honeypot + ratelimit (1/30 min/IP).
- Registered without purchase: form blocked с сообщением.

## Open questions for later
- Q1: GTIN — поле существует в Product/ProductVariant? (проверка в PR-6)
- Q2: Топ-20 продуктов для Task 14 — источник данных (Search Console/orders).
