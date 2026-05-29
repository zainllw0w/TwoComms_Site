# TWOCOMMS Survey V3.4 — Review Notes

## Что изменено после комментария внешнего ИИ

V3.4 закрывает три production-риска, найденные в V3.3:

1. **Pointer mismatch в `q403_price_ladder`.**
   - Добавлен отсутствующий контекст `team_unit_per_unit` в `ladder_points_by_context`.
   - Для `team_unit_bulk_fallback` теперь явно указаны:
     - `use_prompt_variant: team_unit_per_unit`
     - `use_ladder_points: team_unit_per_unit`
     - `set_price_context_key: team_unit_per_unit`
   - Добавлен `range_context_map`, чтобы каждый `dynamic_matrix_ranges` ключ имел валидный контекст ladder points.
   - Добавлены `compile_time_validation_rules` для QA.

2. **Pure B2B больше не проходит personal retail style profiling.**
   - `s030_style_axes` теперь пропускается для:
     - `answers.q010_entry_goal == 'partner'`
     - `answers.q020_purchase_stage == 'partner_discussion'`
   - На уровне вопросов `q040` и `q041` добавлен `skip_if` как дополнительная защита.
   - `custom_team_unit` НЕ пропускает style axes, потому что стиль влияет на командный/кастомный заказ.

3. **NBA syntax унифицирован.**
   - `nba_urban_casual_balanced` больше не использует `derived_fields.style_two_axis_segment`.
   - Условие заменено на плоский ключ: `{ "style_segment": "urban_casual_balanced" }`.
   - Это снижает риск, что JSON-интерпретатор не поддержит dot-notation.

## Что проверять дальше

- Полный path для pure B2B: `partner -> partner_discussion`.
- Full path для `custom_team_unit`:
  - `1_5`, `6_20` → team/unit per unit ladder;
  - `21_50`, `50_plus` → project budget ladder.
- Все `routing_modifiers` в `q403` должны проходить compile-time validation.
- Финальное CTA для `urban_casual_balanced` должно срабатывать через плоский `style_segment`.

## Вердикт

V3.4 уже ближе к production-ready, чем V3.3. Основная ценность версии — не новые вопросы, а устранение runtime-risk: теперь логика цены, B2B-ветки и NBA-условий должна компилироваться стабильнее.
