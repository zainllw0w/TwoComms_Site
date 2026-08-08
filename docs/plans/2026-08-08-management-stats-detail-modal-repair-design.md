# Management Statistics Detail Modal Repair Design

Date: 2026-08-08

## Problem

The Stage 2 statistics detail surface is visually broken for real production data:

- a 420 px side drawer compresses charts, five-value cohort facts, and long labels;
- the overlay reads as a displaced panel instead of a focused analysis surface;
- raw analytics vocabulary (`silence`, `M`, `P90`, `n`, `rc`, `Top-N`, `remaining loss`, `snapshot`, `right-censored`) leaks into the administrator UI;
- repeated loss rows are not grouped across stages;
- structural episode events such as `new_deal_episode` are displayed as customer loss reasons;
- insufficient-data labels wrap into narrow, hard-to-scan columns.

## Approved Direction

Replace the narrow side drawer with a centered desktop modal and a full-screen mobile dialog. Preserve the main statistics context behind a restrained backdrop, but give detailed analysis enough width for real charts and cohort facts.

The modal is a focused analysis workspace, not another dashboard page:

1. A compact header identifies the selected period and optional funnel stage.
2. Visual diagnostic modules use a two-column desktop grid and a one-column narrow layout.
3. Exact cohort facts remain available below the visuals in a wide, scan-friendly structure.
4. Technical definitions move to accessible titles or concise help text instead of visible shorthand.

## Information Design

### Loss Reasons

- Group rows by normalized customer-facing reason.
- Map silence reasons to `Немає відповіді`.
- Exclude structural episode-boundary reasons from customer losses.
- Show recoverable and final loss as two visual segments.
- Replace `remaining loss` with `Інші причини`.
- Replace `total до Top-N` with `найчастіші причини`.

### Time On Stage

- Display human durations such as `4 хв`, `2,5 год`, or `2 дні`.
- Replace `M` with `Зазвичай`.
- Replace visible `P90` with `90% діалогів до`.
- Replace `n` with `Діалогів`.
- Replace `rc` / `right-censored` with `Ще тривають`.

### Cohort Facts

- Rename the section to `Переходи між етапами`.
- Use labels `На етапі`, `Перейшли`, `Втрачено`, `Ще в роботі`, and `Конверсія`.
- Use `Недостатньо даних` instead of `Мало даних CR`.
- Keep the values aligned and readable at every supported width.

### Current Stage Distribution

- Replace `Поточний snapshot` with `Розподіл поточних етапів`.
- Explain it as the share of active clients currently at each stage.

## Layout

Desktop:

- fixed viewport overlay;
- centered panel, `min(1080px, 100vw - 48px)`;
- maximum height around `88dvh` with one internal scroll container;
- two-column diagnostic grid;
- no nested floating panels or horizontal overflow.

Tablet and mobile:

- panel fills the viewport or nearly fills it;
- one-column diagnostics;
- cohort facts become a compact labeled grid;
- close control remains visible while content scrolls.

## Motion

- backdrop fades in;
- modal enters with a short opacity and vertical movement transition;
- no movement that changes layout or hides data;
- reduced-motion continues to disable transitions.

## Acceptance Criteria

- No raw service labels from the reported screenshots remain visible.
- Repeated silence loss rows are grouped.
- Structural episode events are absent from customer loss reasons.
- The desktop dialog is centered and wide enough for all modules.
- The dialog has no horizontal overflow at 1440, 1280, 768, 390, and 320 px.
- Escape, backdrop close, focus trapping, and focus return still work.
- Existing statistics truth semantics and API payloads remain unchanged.

