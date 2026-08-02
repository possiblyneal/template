#!/usr/bin/env bash
set -euo pipefail

# Stdout becomes session context for the agent. Runs on startup, resume,
# clear, and compact, so it must stay fast.
cd "${CLAUDE_PROJECT_DIR:-.}"

# Install the pre-commit hook once per clone so agent commits are checked.
if [[ -f .pre-commit-config.yaml && ! -f .git/hooks/pre-commit ]] \
  && command -v pre-commit >/dev/null 2>&1; then
  pre-commit install >/dev/null 2>&1 || true
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git branch --show-current 2>/dev/null || true)"
  echo "Branch: ${branch:-(detached HEAD)}"

  status="$(git status --short 2>/dev/null | head -20)"
  if [[ -n "$status" ]]; then
    echo "Uncommitted changes:"
    echo "$status"
  else
    echo "Working tree clean."
  fi

  echo "Recent commits:"
  git log --oneline -5 2>/dev/null || echo "(no commits yet)"
fi

echo "Read the nearest CLAUDE.md above every path you touch before editing, and update the owning docs after meaningful changes. The full documentation contract is .claude/rules/documentation.md."
