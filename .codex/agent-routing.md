# .codex/agent-routing.md

## MCP routing

### Sequential Thinking MCP
Use when:
- the bug is non-obvious,
- root cause is unclear,
- architecture choices must be compared,
- a migration or refactor has multiple valid paths,
- the task may need revision, branching, or course correction.

Do not use for:
- trivial one-file edits,
- obvious fixes,
- cosmetic changes,
- predictable small CRUD changes.

### Context7 MCP
Use when the task depends on:
- external libraries,
- SDKs,
- APIs,
- framework behavior,
- setup or configuration,
- deployment tooling,
- auth flows,
- payment integrations,
- async systems,
- caching,
- third-party services.

Rules:
- pull docs before code when library behavior matters,
- if the exact library ID is known, use it directly,
- otherwise resolve the library first, then query docs,
- prefer version-specific documentation where relevant,
- do not rely on stale memory for framework details.

### Serena MCP
Use when:
- the repository is large,
- symbol-level navigation matters,
- you need references, call sites, or semantic code tracing,
- you need safe multi-file edits,
- file-wide dumping would waste context.

Prefer Serena over naive whole-file reading when symbol tools are sufficient.

## Skill routing

### Core default
- using-superpowers: preferred mindset/entry point for non-trivial tasks
- coding-agent: primary implementation workflow
- verification-before-completion: mandatory before final completion

### Planning and execution
- writing-plans: for non-trivial tasks
- executing-plans: when a plan exists and should be followed stepwise

### Debugging and correctness
- systematic-debugging: default for bugs and regressions
- test-driven-development: for new logic, regressions, and cases where a failing test can define the target behavior
- receiving-code-review: after larger or riskier changes
- finishing-a-development-branch: when work is complete and should be finalized cleanly

### Parallelism
- dispatching-parallel-agents: when independent investigation tracks can run in parallel
- subagent-driven-development: when isolated sub-workstreams are useful and context separation matters

Do not use parallelism for small tasks or tightly coupled edits.

### GitHub / review / CI
- gh-fix-ci: when CI is broken
- gh-address-comments: when addressing review comments
- requesting-code-review: when preparing for human review

### UI / browser validation
- playwright: repeatable browser flows and end-to-end checks
- playwright-interactive: exploratory UI investigation
- screenshot: capture visual evidence or before/after state

### Security
- security-best-practices: for auth, payments, admin, uploads, deploy, secrets, external integrations
- security-threat-model: when introducing or changing a security-sensitive surface
- security-ownership-map: when mapping critical trust boundaries and responsibility zones

### Notion / planning / knowledge
Use only when the task justifies process overhead:
- notion-spec-to-implementation: convert a spec into implementation work
- notion-research-documentation: research or technical writeups
- notion-knowledge-capture: durable project knowledge and runbooks
- notion-meeting-intelligence: meeting outputs and action items
- linear: task tracking in Linear

Do not use Notion-heavy workflows for tiny straightforward tasks.

### Specialized / task-specific
Use only when directly relevant:
- atlas
- brainstorming
- chatgpt-apps
- cloudflare-deploy
- codex-wrapped
- doc
- imagegen
- openai-docs
- openai-docs-compat
- pdf
- render-deploy
- skill-creator
- skill-installer
- slides
- sora
- spreadsheet
- using-git-worktrees
- writing-skills

For these, prefer the skill only when its name and SKILL.md clearly match the task.
If exact behavior is unclear, inspect the skill description before using it.

## High-level workflows

### Trivial edit
coding-agent -> verify

### Bug / regression
systematic-debugging -> Sequential Thinking if root cause is unclear -> Serena if tracing is needed -> verify

### External library / API / framework task
Context7 first -> coding-agent -> verify

### Large refactor / multi-file change
writing-plans -> Serena -> coding-agent -> receiving-code-review -> verify

### New feature with logic risk
writing-plans -> test-driven-development -> coding-agent -> verify

### UI bug or checkout/auth flow
playwright-interactive or playwright -> screenshot if useful -> verify

### CI issue
gh-fix-ci -> verify

### Security-sensitive change
security-best-practices -> security-threat-model if needed -> verify

### Deploy-ready completion
finishing-a-development-branch -> deploy workflow -> post-deploy verification
