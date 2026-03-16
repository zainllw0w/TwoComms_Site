---
name: coding-agent
description: Use when delegating work to Codex CLI, Claude Code, OpenCode, or Pi from within Codex, especially for long-running terminal sessions, parallel task execution, isolated workdirs, or when the user explicitly wants external coding agents coordinated instead of manual local edits.
---

# Coding Agent

Delegate coding work to external agent CLIs through terminal sessions. Start them with `functions.exec_command`, keep `tty:true`, isolate their `workdir`, and use `functions.write_stdin` to monitor or answer prompts.

## Core Workflow

1. Check which agent binary exists and whether the target directory is correct.
2. Choose a focused `workdir` or create a temp git repo/worktree.
3. Start the agent with `functions.exec_command` and `tty:true`.
4. For long tasks, let the command continue and capture the returned `session_id`.
5. Monitor with `functions.write_stdin` using empty `chars`, or send input with `chars:"...\n"`.
6. Report milestones, questions, errors, and completion back to the user.

## Tool Mapping

Use these developer tools instead of the OpenClaw-style `bash` and `process` examples from older versions of this skill:

- `functions.exec_command`: start the agent process
- `functions.write_stdin`: poll a running PTY session or send input

If the current Codex runtime exposes a generic terminal tool instead of these desktop wrappers, use the runtime's terminal execution tool plus its PTY/session continuation mechanism. The operational rules stay the same: focused `workdir`, PTY enabled, background session monitoring, and explicit user updates.

Recommended `exec_command` settings:

- `tty:true` for all coding-agent CLIs
- `workdir:"/absolute/path"` to keep context narrow
- `yield_time_ms:1000` to get fast initial feedback
- `max_output_tokens` high enough to capture the latest progress without flooding output

## Preflight

Before launching an agent:

```bash
command -v codex || true
command -v claude || true
command -v opencode || true
command -v pi || true
```

Prefer a real repo or worktree. For scratch work with Codex CLI, use either:

```bash
SCRATCH="$(mktemp -d)"
cd "$SCRATCH"
git init
codex exec "Your prompt here"
```

or, if git context is intentionally unnecessary:

```bash
codex exec --skip-git-repo-check "Your prompt here"
```

## One-Shot Runs

Prefer `codex exec` for finite tasks that should exit when done.

Examples:

```bash
codex exec --full-auto "Refactor the auth helper and run the relevant tests."
claude "Review the checkout templates for regressions."
opencode run "Explain the failing integration test and suggest a fix."
pi -p "Summarize the current src/ layout."
```

Use `--full-auto` for sandboxed automatic Codex execution. Use `--dangerously-bypass-approvals-and-sandbox` only when the user explicitly wants that behavior and the environment is already externally sandboxed.

## Long-Running Sessions

For longer tasks, start the agent with `functions.exec_command` and keep the PTY session alive.

Pattern:

1. Start with `tty:true` and a short `yield_time_ms`.
2. If the process keeps running, store the returned `session_id`.
3. Poll with `functions.write_stdin` and empty `chars`.
4. Send answers with `functions.write_stdin(chars:"...\n")`.

Typical polling rhythm:

- poll after startup
- poll again when you expect a milestone
- poll immediately if the agent may be waiting for input
- stop polling once the session exits

## Workdir Strategy

Keep each agent inside the smallest directory that contains the required context.

- Use the current repo when the task belongs to this workspace.
- Use a temp clone or git worktree for PR reviews.
- Use separate worktrees for parallel implementation tasks.
- Do not start an agent at `$HOME` or another overly broad directory.

## Codex CLI Notes

Prefer these patterns:

```bash
codex exec --full-auto "Implement the requested fix and run targeted verification."
codex exec --skip-git-repo-check "Draft a quick plan for this standalone snippet."
```

Use this flag only with explicit user intent and strong sandbox confidence:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox "..."
```

Good uses for Codex CLI:

- focused one-shot implementation
- background delegation while you supervise
- isolated reviews in worktrees
- repeatable prompts across multiple parallel sessions

## Claude Code, OpenCode, Pi

Respect the user’s requested tool when they name one explicitly.

- Use `claude "..."` for Claude Code if it is installed.
- Use `opencode run "..."` for OpenCode if it is installed.
- Use `pi "..."` or `pi -p "..."` for Pi if it is installed.
- If a requested binary is missing, say so immediately and either choose an available fallback with the user’s consent or stop.

## Parallel Delegation

When independent tasks can run separately:

1. Create separate worktrees or temp clones.
2. Launch one session per task.
3. Track each `session_id` with its directory and objective.
4. Monitor until each agent exits or needs input.
5. Merge or compare results only after each session finishes.

Example worktree flow:

```bash
git worktree add /tmp/issue-78 -b codex/issue-78 main
git worktree add /tmp/issue-99 -b codex/issue-99 main
```

Then launch one agent per worktree.

## Review and Isolation

For PR review or risky exploration:

- prefer a temp clone or git worktree
- avoid switching branches in a live working directory that contains unrelated edits
- keep review prompts read-only unless the user asked for changes

## User Communication

When coordinating background agents:

- send one short update when a session starts
- update again on milestone, question, error, or completion
- if you kill a session, say that you killed it and why

Do not let the user guess whether the child agent is still running.

## Rules

1. Always use `tty:true` for coding-agent CLIs.
2. Respect the user’s requested agent when possible.
3. Prefer `codex exec` for one-shot Codex tasks.
4. Prefer `--full-auto` over unsafe bypass flags.
5. Keep the child agent inside a focused `workdir`.
6. Use worktrees for parallel tasks and PR review isolation.
7. Do not silently replace explicit delegation with manual patching unless the user changes direction.
8. If a child agent hangs or fails, retry once if the cause is obvious; otherwise report the blocker.
