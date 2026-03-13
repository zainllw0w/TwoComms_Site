# Identity, Dedupe, Follow-Up And Anti-Abuse

## Canonical Role

This file defines how identity, duplicate detection, ownership safety, follow-up pressure and anti-abuse review must work over the current `management` stack.

## Identity Model

### Core entities

- `Client`
- `ManagementLead`
- `Shop`
- `ClientFollowUp`

### Identity keys

- `phone_normalized`
- `phone_last7`
- normalized shop/client name
- `normalized_name_hash` or equivalent exact precheck helper
- source external id or URL when available

### Important exclusions

- `city` is not a mandatory identity key;
- `website` is useful but not reliable enough as primary truth today;
- notes and comments are never primary identity.

## Normalization Contract

Before fuzzy matching, use multi-step normalization:
1. Unicode normalize
2. lowercase
3. strip punctuation
4. collapse whitespace
5. transliterate to comparable form
6. remove legal entity tokens
7. build `normalized_name_display` and `normalized_name_match_key`

Important:
- preserve meaningful root tokens;
- do not destroy branch/store semantics;
- phone normalization in current code is limited and must be treated as current-scope reality, not universal international coverage.

## Dedupe Strategy

### Candidate prefilter

- exact phone match;
- last-7 phone match;
- first normalized token;
- source external id when available.

### Candidate score

```python
candidate_score = (
    0.45 * name_match_score
    + 0.35 * phone_match_score
    + 0.10 * owner_match_score
    + 0.10 * source_link_score
)
```

### Final zones

| Zone | Rule | Action |
|---|---|---|
| `AUTO_BLOCK` | strong exact identity | do not create duplicate |
| `REVIEW` | ambiguous but plausible duplicate | open review flow |
| `SUGGESTION` | soft warning | allow creation with warning |
| `CLEAR` | no suspicion | normal create |

`AUTO_BLOCK` must stay conservative. Smarter search is allowed; aggressive auto-merge is not.

## Shared-Phone Contract

Shared switchboards are explicit reality.

Required fields or equivalent:
- `is_shared_phone`
- `phone_group_id`
- `shared_phone_reason`

If number is flagged as shared:
- exact phone alone is not enough for auto-block;
- review-first semantics apply.

## Create-Or-Append Contract

Default behavior must push toward append/review rather than blind-create:
1. normalize data;
2. search owner-scope candidates;
3. compute zones;
4. if blocked or reviewed, show the existing candidate;
5. only then allow new record.

Batch import must support preview-before-write with exact/review/clean counts.

## Ownership Safety

### Canonical ownership rule

Ownership must be explicit and reviewable.

Current code already has multiple patterns:
- `Client.owner`
- `Shop.created_by` and `Shop.managed_by`
- `ManagementLead.added_by`, `moderated_by`, `processed_by`

Portfolio interpretation must use the active responsible party, not naive creator semantics.

### Hard rules

- no silent ownership transfer;
- no fuzzy auto-merge across owners without review;
- ownership changes need audit trail;
- merge rollback window required.

## Follow-Up Contract

### Core statuses

- `OPEN`
- `DONE`
- `MISSED`
- `RESCHEDULED`
- `CANCELLED`

### Ladder

- `T-15m reminder`
- due-now reminder
- overdue same day
- next-day escalation
- accumulated-overdue escalation

### Physical capacity guard

`MAX_FOLLOWUPS_PER_DAY = 25` remains mandatory.

If due items exceed capacity:
- overload is redistributed;
- manager is not punished beyond physical throughput;
- admin sees overload alert.

### Neutrality rule

If effective due count is zero, follow-up score stays neutral.

## Reminder Delivery Contract

Required low-noise controls:
- reminder dedupe keys;
- digesting if reminder count spikes;
- `manager_timezone`;
- quiet hours;
- digest preference;
- existing `ReminderSent` / `ReminderRead` tracking should be reused.

## Import Burst And Duplicate Debt

Imported historical backlog must not instantly become personal negligence.

Required rules:
- grace window `24-48h`;
- imported backlog label;
- duplicate review debt only starts after grace expiry;
- import burst must be visible separately from organic missed follow-ups.

## Anti-Abuse Contract

### Review-first policy

- low sample -> alert only;
- repeated pattern + sufficient N -> review;
- only after review -> bounded production consequence.

### Required review signals

- callback cycling;
- batch logging with low meaningful progress;
- entropy + concentration instead of crude same-reason share only;
- cross-owner duplicate cluster visibility;
- self-selected warm source bias.

### Rate limiting

Use per-action budgets, not one generic limiter:
- reminder send;
- ownership claim;
- duplicate resolution;
- webhook retry;
- manual bulk updates.

Admin review actions have elevated or exempt budgets.

## Existing Production Realities To Preserve

- `Client.phone_normalized` already exists;
- `Client.points_override` exists and must be handled carefully in transition;
- `ClientFollowUp` already exists and should be extended, not replaced;
- parser/import flow already exists and must not become blind-create again;
- shop and lead entities must be considered in ownership truth.

## Implementation Landing

- extend `Client`, `ClientFollowUp`, import/parsing and lead workflows;
- create duplicate review and ownership log models only where current audit depth is insufficient;
- add background duplicate scan and reminder digest commands;
- keep merge flow conservative and auditable.

## Implementation Mistakes To Avoid

- dedupe by fuzzy name alone;
- exact-phone auto-block for known shared switchboards;
- turning imported backlog into immediate manager debt;
- punishing on one-day heuristic noise;
- ignoring multiple ownership patterns already present in code.
