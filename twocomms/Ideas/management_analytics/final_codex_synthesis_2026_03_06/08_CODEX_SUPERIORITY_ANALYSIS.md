# Why Codex Is Still the Best Base Layer

## 1. Главный тезис

Если выбирать не “у кого ярче идеи”, а “с какой базы реально идти в имплементацию”, то `Codex` объективно сильнее `Gemini` и `Opus`.

Не потому, что у него были лучшие все идеи.
А потому, что именно у него был лучший `implementation backbone`.

## 2. Почему Codex сильнее Gemini

### 2.1 Implementation readiness
Gemini дал много сильных концептов, но слаб в:
- data contracts,
- API boundaries,
- acceptance tests,
- rollout safety,
- rollback logic,
- migration thinking.

Codex дал всё это.

### 2.2 Production safety
Gemini несколько раз уходил в идеи, которые опасны для реальной команды:
- auto `Shark Pool`,
- `Doomsday Screen`,
- бесконечный MMR,
- агрессивный survival framing.

Codex почти везде выбирал более безопасный operating model.

### 2.3 Role separation
Codex лучше всех разделил:
- manager view,
- admin view,
- what is motivational,
- what is supervisory,
- what is financial,
- what is disciplinary.

Gemini здесь часто смешивал мотивацию, наказание и геймификацию в один слой.

### 2.4 Multi-DB and DTF awareness
Codex лучше учёл:
- read-only bridge,
- no cross-DB FK,
- access matrix,
- phased integration.

Это сильно важнее, чем кажется, потому что именно тут обычно ломаются “красивые” идеи на живом проекте.

### 2.5 Auditability
Codex сильнее в:
- trust tiers,
- manual override logging,
- incident verification,
- explainability,
- anti-abuse by design.

Gemini чаще предлагал красивые эффекты до того, как фиксировал контрольные механизмы.

## 3. Почему Codex сильнее Opus

### 3.1 Decision governance
Opus силён в содержании, но слабее в lock-решениях.

Codex лучше зафиксировал:
- A/B/C branches,
- locked defaults,
- governance for future changes.

Это снижает хаос на этапе реальной разработки.

### 3.2 Acceptance matrix
Opus много дал в продуктовой логике, но Codex сильнее подготовил систему к проверке.

Acceptance criteria и тестовый каркас у Codex объективно лучше.

### 3.3 Rollout strategy
Opus слабее проработал:
- shadow mode,
- feature flags,
- rollback criteria,
- staged enablement.

Codex это сделал хорошо.

### 3.4 Admin/product separation
Opus лучше прорабатывал смысл score и B2B fit, но хуже разделял операционные роли и контрольные представления.

Codex здесь аккуратнее.

### 3.5 Contract thinking
Codex лучше упаковал:
- data model,
- endpoint logic,
- permissions,
- risk register,
- deploy brief.

Это и делает его лучшей базой для команды разработки.

## 4. Где Codex не победил

Чтобы критика была честной:
- EV fairness по типу базы у Gemini лучше.
- retention psychology и salary simulator у Gemini лучше.
- B2B cold calibration и heatmap from user request у Opus лучше.
- reminder cadence и workflow realism местами у Opus лучше.

Но это не отменяет основного вывода:

`Codex = лучший каркас`

`Gemini = лучший мотивационный и retention-слой`

`Opus = лучший бизнес-контекст и anti-gaming калибровщик`

## 5. Итоговый вердикт

Если бы пришлось брать одну базу без гибрида, я бы взял `Codex` и поверх него добавил:
- EV fairness,
- portfolio health,
- safer version of Tamagotchi and salary simulator,
- B2B gate recalibration,
- heatmap,
- better reminder ladder.

Именно поэтому новая финальная папка строится на логике:
- `Codex skeleton`,
- `Opus calibration`,
- `Gemini behavioral layer`.
