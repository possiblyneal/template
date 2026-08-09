#!/usr/bin/env bash
set -euo pipefail

# Stdout becomes session context for the agent. Runs on startup, resume,
# clear, and compact, so it must stay fast.
cd "${CLAUDE_PROJECT_DIR:-.}"

# Install the git hooks once per clone so agent commits are checked. Two files
# are installed, not one: pre-commit and, when the config asks for it,
# commit-msg. A clone predating the commit-msg hook already has the first, so
# testing only for that one would leave the message check permanently
# uninstalled on exactly the clones that have been around longest.
#
# --git-path rather than a literal .git/hooks, because in a linked worktree
# .git is a file and the hooks live in the shared common dir.
if [[ -f .pre-commit-config.yaml ]] && command -v pre-commit >/dev/null 2>&1; then
  hooks_dir="$(git rev-parse --git-path hooks 2>/dev/null || echo .git/hooks)"
  if [[ ! -f "$hooks_dir/pre-commit" ]] \
    || { grep -q '^default_install_hook_types:.*commit-msg' .pre-commit-config.yaml \
         && [[ ! -f "$hooks_dir/commit-msg" ]]; }; then
    pre-commit install >/dev/null 2>&1 || true
  fi
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git branch --show-current 2>/dev/null || true)"
  echo "Branch: ${branch:-(detached HEAD)}"

  # head closes the pipe once it has its 20 lines, so git dies of SIGPIPE on a
  # large working tree and pipefail propagates 141. Without the `|| true` that
  # exit status ends the hook under `set -e`, and the branch, commits, and
  # documentation reminder below are all lost — on exactly the messy tree that
  # needs them most.
  status="$(git status --short 2>/dev/null | head -20 || true)"
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
