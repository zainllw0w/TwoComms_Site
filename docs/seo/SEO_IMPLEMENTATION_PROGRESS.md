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
- [x] T4.2 Production curl verify — `<meta name="keywords">` отсутствует на PDP/catalog (deploy fcb59822)

## PR-2: variants/canonical [in progress — code+tests done, OG/Twitter image override pending]
- [x] T5.1 `ProductVariantSitemap` — size-only урлы удалены (остались только color + fit)
- [x] T5.2 `ProductVariantSitemapPhase21Tests.test_variant_sitemap_excludes_size_only_urls`
- [x] T6.1 `variant_meta.build_variant_meta` — size-only single-segment → base canonical, `is_self_canonical=False`
- [x] T6.2 `VariantCanonicalPhase21Tests` (4 кейса: M, black, oversize, black/m)
- [x] T7.1 `generate_product_schema(canonical_path, selected_variant)` + `get_product_schema(...)` пропускает в генератор
- [x] T7.2 `test_product_schema_url_uses_canonical_path_when_provided` (Offer.url тоже обновлён)
- [~] T7.3 Реализовано для Product schema (variant images первыми); OG/Twitter изображения в base.html пока берут `og_image` block — добавить оверрайд в PDP на следующем шаге

## PR-3: categories [code+tests done, production verify pending]
- [x] T8.1 Поля `seo_title`, `seo_h1`, `seo_description` добавлены в `Category`
- [x] T8.2 `CategoryAdmin` показывает секцию «SEO ручні поля»
- [x] T8.3 Миграции: `0057_category_seo_overrides` + `0058_phase21_seed_category_seo_overrides` (сиды)
- [x] T8.4 `pages/catalog.html` — fallback для `title`, `description`, `og_title`, `og_description`, `twitter_*`, H1
- [x] T9.1 Сиды уникальной копии для `tshirts`, `hoodie`, `long-sleeve` (только если поле пусто, safe для прода)
- [x] T9.2 Production verify 3 категорий (deploy fcb59822) — tshirts/hoodie/long-sleeve отдают уникальные SEO-тайтлы
- [~] T10.1 «Create your design» дубль — не найден в current catalog.html (возможно уже правлено в Phase 10/15; проверить на live)
- [x] T10.2 `_CURATED_TOP_QUERIES` очищен от `?color=` URL, регрессия `GeneralCatalogSeoColorlessQueriesTests`
- [x] T10.3 Регрессия: top query URLs без `?color=` (`test_curated_top_queries_do_not_link_to_color_filtered_pages`)

## PR-4: reviews system [PR-4c3 complete: signals + nested Review JSON-LD]
- [x] R1 App `reviews` создан, INSTALLED_APPS обновлён
- [x] R2 Модели: `Review`, `ReviewImage` (max 5 будет enforced в форме), `ReviewVote` с unique constraints (per-user / per-anon)
- [x] R3 Миграция `reviews/0001_initial.py` + индексы `rev_pdp_lookup_idx` / `rev_status_product_idx`
- [x] R4 `ReviewForm` (auth + guest), валидация rating/body/email + honeypot `website`
- [x] R5 `submit_review` + `vote_review` views, rate-limit гостей (2/час per IP+product), photo cap ×5 / 5MB / JPEG·PNG·WebP
- [x] R6 URL routes в `reviews/urls.py`, завёрнуты в `/reviews/...`
- [x] R7 Admin: pending list, approve/reject bulk-actions, moderation_note, inline ReviewImage
- [x] R8 Telegram notify модератору при pending submit (`reviews/signals.py`); в отсутствие конфига silent-skip
- [x] R9 `has_paid_order_with_product()` — `is_verified_purchase` ставится автоматически при submit для auth с paid Order
- [x] R10 `partials/product_reviews.html` — summary header + histogram (5✦05✦41☆), инлайн-форма через `<details>`, список одобренных; подключён в PDP
- [x] R11 Карточка отзыва: stars, «Verified purchase» badge, фотогалерея (lazy + native lightbox через `<a target=_blank>`), helpful счётчик
- [ ] R12 Личный кабинет — раздел "Мої відгуки"
- [x] R13 `aggregate_rating_for_product()` + `ProductReviewSummary` датакласс; threshold=3 вынесён в `MIN_APPROVED_REVIEWS_FOR_RATING`
- [x] R14 `Product.aggregateRating` + nested top-5 Review JSON-LD в единый Product schema (только при `show_rating=True`)
- [x] R15 IndexNow ping при флипе status → approved (signal `post_save`, идемпотентно)
- [x] R16 31 тест (aggregate/lifecycle/schema/submit/vote/permissions/signals/nested-review)

## PR-5: content/FAQ [code+tests done; T13 cross-linking deferred]
- [x] T11.1 City chips block (Київ/Харків/Сample) вынесен из `_top_queries_for_product` с комментарием о причине
- [~] T11.2 Бывшие 4 городские chips просто удалены (custom-print + category-fallback chips остались). Добавить buyer-facing chips в следующем iter
- [x] T11.3 `test_does_not_include_city_chips` проверяет отсутствие городских слов
- [x] T12.1 `ProductFAQ` уже был admin-driven (не автоген) — проверено
- [x] T12.2 `{% faq_schema product_faq_items %}` убран с PDP (FAQ остаётся видимым, без JSON-LD)
- [x] T12.3 FAQPage schema остаётся на support_page.html в т.ч. /faq/, /delivery/, /povernennya-ta-obmin/, /cooperation/, /pro-brand/, /custom-print/, /wholesale/
- [ ] T13.1 PDP cross-links → support pages (отложено на следующую итерацию)
- [ ] T13.2 Support pages → category links (отложено)
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
