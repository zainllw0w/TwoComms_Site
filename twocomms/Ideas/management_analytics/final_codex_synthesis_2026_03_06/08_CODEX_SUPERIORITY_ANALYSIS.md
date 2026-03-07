# Design Decision Log: Why This Final Architecture Uses Codex as the Base Skeleton

## 1. Почему файл переписан

Opus справедливо указал, что прежняя версия этого файла выглядела слишком self-promotional.

Этот файл остаётся в пакете, потому что пользователь прямо просил отдельную критику о том, чем `Codex` лучше двух других агентов.

Но теперь он оформлен как нейтральный decision log, а не как самореклама.

## 2. Core decision

Базовым skeleton для финальной архитектуры выбран `Codex`, потому что именно он лучше всего решал production problems:
- contracts,
- rollout,
- feature flags,
- testing,
- multi-DB awareness,
- role separation,
- risk control.

## 3. Почему не Gemini как base skeleton

`Gemini` дал сильнейшие идеи по:
- retention psychology,
- EV fairness,
- portfolio motivation,
- salary simulator,
- UX-energy.

Но как base skeleton он слабее из-за:
- низкой implementation readiness,
- слабой formalization of models/APIs,
- высокой доли risky mechanics,
- склонности смешивать motivation and punishment.

Итог:
- Gemini нельзя брать как основу,
- но его behavioural layer критически важен поверх финального каркаса.

## 4. Почему не Opus как base skeleton

`Opus/HES` дал сильную бизнес-калибровку:
- heatmap,
- B2B realism,
- callback discipline,
- anti-gaming logic,
- cold-cycle fit.

Но как base skeleton он слабее `Codex` в:
- locked decisions,
- acceptance criteria,
- rollout safety,
- deploy and rollback thinking,
- contract completeness.

Итог:
- Opus сильнее как calibrator and risk critic,
- Codex сильнее как implementation frame.

## 5. Что в итоге выбрано у Codex

- role separation,
- trust tiers,
- decision governance,
- gate thinking,
- acceptance matrix mindset,
- rollout sequencing,
- DTF read-only logic,
- anti-abuse contract thinking.

## 6. Что поверх него добавлено из Opus

- B2B cold-cycle realism,
- verified-progress gate `78`,
- stronger follow-up ladder,
- practical calibration pressure,
- safer criticism of noisy alerts,
- migration and fuzzy dedupe concerns,
- QA reliability and IRR focus.

## 7. Что поверх него добавлено из Gemini

- EV/source fairness spirit,
- 2.5% / 5% retention-first logic,
- portfolio health UX,
- salary simulator,
- no-touch report,
- micro-feedback,
- golden hour layer.

## 8. Что намеренно не принято

### Из Gemini
- automatic `Shark Pool`,
- `Doomsday Screen`,
- uncontrolled infinite MMR,
- overly aggressive survival framing.

### Из Opus
- перенос сложных advanced metrics в core without data maturity,
- попытка слишком рано тащить telephony-dependent intelligence в основную формулу.

### Из старого Codex
- слишком абстрактные thresholds,
- недостаточная B2B calibration,
- избыточная уверенность в некоторых defaults без numbers.

## 9. Итоговая decision formula

Финальная архитектура строится так:
- `Codex skeleton`
- `Opus calibration`
- `Gemini behavioral layer`
- `new guardrails and presets after Opus audit`

Это не компромисс ради компромисса.
Это наиболее реалистичный путь получить систему, которая:
- объяснима,
- внедряема,
- устойчива к абузу,
- мотивирует,
- и не ломается от человеческого фактора.
