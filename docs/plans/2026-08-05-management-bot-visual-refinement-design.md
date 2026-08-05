# Management Bot Visual Refinement Design

## Objective

Make the Instagram Direct manager workspace faster to scan without turning it
into a colour-heavy dashboard. The design makes verified commercial state
visible at a glance, lets the operator collapse the context panel, compresses
filters into a purposeful control, and keeps the three workspace panes aligned.

## Visual Language

The workspace remains a dark operational console. Colour is reserved for facts
that change an operator decision, with a slim left rail, a small state chip,
and a restrained tinted background rather than an entirely coloured card.

Commercial precedence is deterministic:

1. A linked real order in `ship` with a TTN is `shipped` (violet). A green
   confirmed-payment chip remains visible so shipment never hides the money
   provenance. A delivered `done` order stays green because it is no longer in
   transit.
2. A verified payment or manager-confirmed order is `paid` (green).
3. A pending payment or manager action is `attention` (amber), but only while
   no paid or shipped fact is present.
4. All other conversations are neutral. Hidden, spam, and explicit post-sale
   action states retain their existing distinct treatment.

Direct-message transport errors are deliberately excluded from this hierarchy:
they are operational warnings, not shipment evidence.

## Workspace Behaviour

On desktop the client context is a true optional third pane. The existing gear
button toggles it, persists the local preference, updates `aria-expanded`, and
reflows the list and conversation panes using CSS grid. On narrow screens it
continues to open the existing accessible modal/drawer rather than squeezing
three panes into a phone viewport.

The filter control keeps the high-frequency choices (`Усі`, `Активні`,
`Оплачені`) in a compact segmented row. Lower-frequency workflow categories
live behind a clearly labelled filter button/popover, preserving keyboard and
screen-reader access and reporting the active choice. The API view values stay
unchanged.

The conversation actions have one full-width primary control for pausing or
resuming automation, followed by a stable three-column secondary action grid.
Destructive controls do not shift around as their labels change.

## Delivery Slices

1. Evidence-based paid/shipped row treatment and a backend `commercial_visual_state` payload.
2. Toggleable desktop context panel, reflowed pane geometry, and equal visual rhythm.
3. Compact progressive-disclosure filters plus an aligned conversation-action grid.
4. Compact overview metrics and a more useful runtime-status composition after removing `Як працює`.
5. A separately reviewed Markdown audit with 100 ranked next-step improvements; it is not an unreviewed implementation backlog.

## Verification

Each slice gets a targeted server-side contract test before production changes,
template/JavaScript parsing checks, responsive browser checks at desktop and
mobile sizes, then a commit is integrated into `main`, pushed, deployed, and
proved by matching local, remote, and server SHAs. Deployment does not create
Meta events or send customer messages.
