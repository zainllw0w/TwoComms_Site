# Instagram Runtime Recovery Findings — 2026-07-30

## Incident

At 15:11 Europe/Kyiv a customer sent `hellou`. Meta delivered the callback to
`POST /bot/webhook/`, but production returned `403`. The request was rejected
before JSON parsing, raw-event persistence, queueing, Gemini, and Send API.

## Confirmed credential identities

| Purpose | ID / variable | Confirmed source |
|---|---|---|
| Parent Meta app | `2120980214971807` / `META_APP_SECRET` | DIRECT_BOT, App settings > Basic |
| Instagram Login app | `533035169363490` / `IG_APP_SECRET` | BotTG-IG, Instagram > API setup with Instagram login |
| Instagram account token | `IG_INSTAGRAM_BOT` | Token generated for `twocomms` in the Instagram setup table |
| Instagram account | `17841467101471112` | `twocomms` row in Instagram setup |
| Webhook verify token | `IG_BOT_VERIFY_TOKEN` | Private operator-generated callback verification value |

The value `17866694895236716` is returned by the account
`subscribed_apps` edge. It is not used as the parent Meta App ID, Instagram App
ID, account ID, token, or secret selector.

## Root cause

The user correctly changed `IG_APP_SECRET` in cPanel, and the new Passenger
process environment contained the new value. Django then imported
`twocomms.production_settings`, which loaded `.env.production` with
`override=True`. That silently replaced cPanel's new Instagram secret with the
old parent Meta secret.

This produced a misleading split:

- `/proc/<passenger>/environ` showed the new cPanel fingerprint;
- Django's `os.environ` used the old `.env.production` value;
- every real Meta callback failed HMAC validation and returned `403`.

A signed synthetic request proved that LiteSpeed, Apache, and Passenger preserve
`X-Hub-Signature-256`: a request signed with the secret actually loaded by
Django returned `200`, while the other secret returned `403`.

## Live recovery evidence

The private `.env.production` file was backed up and synchronized without
printing either secret:

- `IG_APP_SECRET` now contains the Instagram Login app secret;
- `META_APP_SECRET` contains the parent DIRECT_BOT app secret.

After Passenger restart, real Meta callbacks changed from `403` to `200`:

- `16:04:01` — `POST /bot/webhook/` → `200`
- `16:05:13` — `POST /bot/webhook/` → `200`

Database evidence then confirmed the complete customer path:

1. raw webhook rows were created;
2. `webhook-test-1553` entered the durable queue;
3. the daemon processed it once;
4. Gemini returned successfully;
5. Send API completed with `send_state=sent`;
6. a model reply was stored;
7. the next customer message was also queued, analyzed, and answered.

## Permanent remediation

1. Production env files may fill missing values but must never override cPanel
   process variables.
2. Instagram Login webhook HMAC must use `IG_APP_SECRET` only.
3. Parent Meta OAuth and compliance callbacks must use `META_APP_SECRET`, with
   `FACEBOOK_APP_SECRET` retained only as a legacy alias.
4. `IG_INSTAGRAM_BOT` is an access token and must never be accepted as an HMAC
   secret.
5. Legacy `IG_MARKER`, `DIRECT_API`, and the invalid
   `IG_INSTAGRAM_APP_SECRET` are not part of the active Instagram Login
   transport and can be removed after the deployed code and production checks
   confirm no call site depends on them.

## Remaining product work

- Replace continuous Graph polling with an explicit durable “Оновити всіх
  користувачів” recovery run and visible progress.
- Import no more than the latest 20 messages per conversation.
- Skip hidden users before profile, message-history, and Gemini work.
- Analyze recovered history without creating customer auto-replies.
- Add a safe per-client funnel/context reset that preserves immutable history,
  payments, orders, refunds, opt-out, hidden state, and manager takeover.
