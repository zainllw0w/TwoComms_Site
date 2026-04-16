#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD_SCRIPT="$ROOT_DIR/scripts/antigravity_git_guard.sh"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_repo_is_sanitized() {
  local repo_path="$1"

  (
    cd "$repo_path"

    if git config --local --get extensions.worktreeConfig >/dev/null 2>&1; then
      echo "extensions.worktreeConfig was not removed"
      exit 1
    fi

    if [[ "$(git config --local --get core.longpaths)" != "true" ]]; then
      echo "core.longpaths was not forced to true"
      exit 1
    fi

    for pattern in '.claude/worktrees/' '.cursor/worktrees/' '.codex/worktrees/'; do
      if ! grep -Fxq "$pattern" .git/info/exclude; then
        echo "missing exclude pattern: $pattern"
        exit 1
      fi
    done
  )
}

repo="$tmpdir/repo-direct"
mkdir -p "$repo"
git init "$repo" >/dev/null 2>&1

(
  cd "$repo"
  git config --local core.longpaths false
  git config --local extensions.worktreeConfig true
  mkdir -p .git/info .claude/worktrees/example .cursor/worktrees/example .codex/worktrees/example
  printf '%s\n' '# test exclude' > .git/info/exclude
  "$GUARD_SCRIPT"
)

assert_repo_is_sanitized "$repo"

repo="$tmpdir/repo-hook"
mkdir -p "$repo"
git init "$repo" >/dev/null 2>&1

(
  cd "$repo"
  git config user.name test >/dev/null 2>&1
  git config user.email test@example.com >/dev/null 2>&1
  git config --local core.longpaths false
  git config --local extensions.worktreeConfig true
  mkdir -p .git/info .claude/worktrees/example
  printf '%s\n' '# test exclude' > .git/info/exclude
  mkdir -p scripts .githooks
  cp "$ROOT_DIR/scripts/antigravity_git_guard.sh" scripts/antigravity_git_guard.sh
  cp "$ROOT_DIR/.githooks/post-checkout" .githooks/post-checkout
  chmod +x scripts/antigravity_git_guard.sh .githooks/post-checkout
  git config --local core.hooksPath .githooks
  touch README.md
  git add README.md
  git commit -m "init" >/dev/null 2>&1
  git config --local extensions.worktreeConfig true
  git checkout -b sanity-branch >/dev/null 2>&1
)

assert_repo_is_sanitized "$repo"

echo "antigravity git guard test: ok"
