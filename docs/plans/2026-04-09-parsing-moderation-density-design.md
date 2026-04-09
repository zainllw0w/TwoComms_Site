# Parsing Moderation Density Design

**Problem:** The parsing moderation queue stops using horizontal space efficiently on smaller desktop screens. The action cell collapses too early, secondary metadata competes with primary data, and repeated CSS tweaks have not produced a stable layout.

**Constraints:**
- Keep the moderation queue as a table so moderators preserve fast column scanning.
- Do not change moderation API payloads or action semantics.
- Keep `Оглянути` readable and clickable on older desktop displays.
- Keep fast approve/reject as icon-only controls to save width.
- Avoid mobile/card redesigns for this task.

## Recommended Approach

Use a desktop-first compact table strategy instead of additional generic shrinking:

1. Rebalance the moderation `colgroup` around actual operator priority.
2. Split cell content into primary and secondary layers inside the same cell.
3. Give the action column a predictable rail with a stable minimum size.
4. Hide or compress only low-signal metadata at narrower desktop widths.
5. Preserve table semantics and existing JavaScript event wiring.

## Cell Priorities

- **Primary:** shop name, website entry point, city, niche status, review button, fast approve/reject.
- **Secondary:** full name, source, phone completion hint, keyword detail, website hostname/meta.

The compact design keeps primary information on the first visual line and moves secondary details into smaller subordinate rows/chips that can collapse at intermediate breakpoints without affecting moderation actions.

## Layout Changes

- Narrow the phone and niche columns slightly.
- Reallocate saved width to `Магазин`, `Сайт`, and `Дія`.
- Turn the action cell into a two-part rail:
  - left: a primary `Оглянути` button that remains comfortable to tap/click;
  - right: a fixed icon stack for approve/reject.
- Replace single-line truncation where it harms scanability with compact two-line wrapping for selected fields.

## Breakpoint Strategy

- `> 1500px`: full compact desktop layout with primary + secondary metadata.
- `1280px – 1500px`: suppress low-signal secondary text and reduce chip padding before shrinking the action rail.
- `<= 1280px` desktop: keep the table scroll-safe, but with a lower minimum width and a denser column map so the action rail remains visible earlier.

## Verification

- Add template regression coverage for the new moderation row structure and action rail hooks.
- Run targeted parser moderation tests.
- Validate the rendered layout in a browser at representative desktop widths.
- Deploy only the affected runtime template, because production has a dirty checkout and full `git pull` is unsafe.
