# Instagram Structured Control Boundary Design

## Scope

Close Implement 2 W1.6 only:

- replace model-authored operational tags with a typed structured response;
- keep one fail-closed legacy adapter during rollout;
- prove customer prompt injection cannot grant payment, stock, consent, stage,
  or manager authority;
- remove the duplicate legacy payment protocol from the persisted base prompt
  without overwriting unrelated operator edits.

Sales-playbook expansion, adaptive context budgeting and provider function
calling remain outside this slice.

## Chosen approach

Gemini returns JSON with a customer-facing `reply_text` and a bounded list of
typed control commands. The provider request uses `responseMimeType` and a
closed `responseSchema`; application validation repeats the same allowlist and
per-command value checks because provider schema enforcement is not an
authorization boundary.

Legacy string replies pass through a compatibility adapter. Known tags are
converted into the same immutable control value object. Unknown, malformed or
conflicting controls make the complete operational control set invalid. All
control-shaped suffixes are removed before customer delivery, including typos,
so a failed command cannot leak as chat text.

Downstream payment, catalog, consent, stage and manager services retain final
authority. The typed response only proposes actions; it cannot manufacture a
verified payment, stock fact, opt-in, hard funnel stage or manager decision.

## Components

1. `management/services/ig_response_control.py`
   owns the JSON schema, immutable result/control types, strict structured
   validator and legacy adapter.
2. `call_ai_analysis.gemini_generate_text` gains an explicit parse mode while
   retaining its current default text contract.
3. `instagram_bot.gemini_generate` requests structured JSON and returns the
   typed result. The message worker normalizes mocked/legacy strings through
   the same boundary before any operational code runs.
4. The canonical runtime commerce protocol describes structured commands, not
   brackets. `DEFAULT_BOT_SYSTEM_PROMPT` loses its duplicate payment/control
   instructions.
5. Migration `0151` alters the default and removes only exact known legacy
   fragments from existing singleton prompts. Custom surrounding text is
   preserved byte-for-byte.

## Failure behaviour

- Non-object JSON, unknown fields, unknown command kinds, wrong value types,
  duplicate singleton commands or conflicting values: reply controls are
  invalid and no operational action executes.
- Empty/invalid `reply_text`: generation failure follows the existing safe
  deterministic fallback path.
- Legacy typo/lowercase/control-like brackets: stripped from customer text and
  classified invalid; never interpreted permissively.
- Valid proposals still pass through existing price, product, checkout,
  payment, stage, opt-out and manager guards.

## Verification

Use RED-first unit tests for schema/adapter failures, provider payload tests,
full worker adversarial tests and migration/prompt preservation tests. Run the
focused W1.6 modules plus adjacent payment/order tests, Django check,
makemigrations check, compileall and diff check. After deployment, verify the
exact SHA/migration, production prompt markers, provider-free parser probes,
one daemon and healthy queues. No live Gemini, Meta, Telegram or payment call is
part of acceptance.

