#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
common_dir="$(git rev-parse --git-common-dir)"

config_file="$common_dir/config"
exclude_file="$common_dir/info/exclude"

mkdir -p "$(dirname "$exclude_file")"
touch "$exclude_file"

git config --local core.longpaths true

if git config --local --get extensions.worktreeConfig >/dev/null 2>&1; then
  git config --local --unset-all extensions.worktreeConfig
fi

declare -a patterns=(
  ".claude/worktrees/"
  ".cursor/worktrees/"
  ".codex/worktrees/"
)

for pattern in "${patterns[@]}"; do
  if ! grep -Fqx "$pattern" "$exclude_file"; then
    printf '%s\n' "$pattern" >> "$exclude_file"
  fi
done

# Keep nested agent worktrees out of repo context, even if other tools create them later.
find "$repo_root" -mindepth 3 -maxdepth 3 -type d \
  \( -path "$repo_root/.claude/worktrees/*" -o -path "$repo_root/.cursor/worktrees/*" -o -path "$repo_root/.codex/worktrees/*" \) \
  -print >/dev/null 2>&1 || true

printf 'antigravity guard: ok (%s)\n' "$config_file"
