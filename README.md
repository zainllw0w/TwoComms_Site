# TwoComms — DTF Redesign (Control Deck × Lab Proof)

This repository contains the DTF redesign for **dtf.twocomms.shop**.
Source of truth: `PROMPT_GPT52_CODEX_DTF_TwoComms_Redesign_v3.md`.

## Key Docs
- `CHECKLIST_DTF_REDESIGN.md` — progress checklist
- `specs/` — phase specs (`00`–`07`)
- `ASSETS_MANIFEST.md` — Gemini handoff list
- `GEMINI_ASSETS_PROMPT.md` — detailed asset production brief

## Assets (Gemini pipeline)
- All visual assets live in `twocomms/dtf/static/dtf/assets/`.
- **Do not** fake complex art with CSS. Use placeholders + ASSET_REQUEST.
- Update `ASSETS_MANIFEST.md` when assets are delivered.

## Frontend
- Tokens: `twocomms/dtf/static/dtf/css/tokens.css`
- Main styles: `twocomms/dtf/static/dtf/css/dtf.css`
- JS: `twocomms/dtf/static/dtf/js/dtf.js` (idempotent init + HTMX re-init)

## Deploy (safe)
- **Do not** hardcode secrets in repo or commit history.
- Use environment variables or secret store in CI.
- Example pattern:

```bash
sshpass -p "$DEPLOY_PASS" ssh -o StrictHostKeyChecking=no "$DEPLOY_USER@$DEPLOY_HOST" \
  "bash -lc 'source /path/to/venv/bin/activate && cd /path/to/project && git pull'"
```

## Notes
- Local server should **not** be started for this project (env is tied to prod).
- Validate UI after push + deploy on staging/production.
