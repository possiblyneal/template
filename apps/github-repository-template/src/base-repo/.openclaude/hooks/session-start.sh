#!/usr/bin/env bash
set -euo pipefail

# Stdout becomes session context for the agent. Runs on startup, resume,
# clear, and compact, so it must stay fast.
cd "${CLAUDE_PROJECT_DIR:-.}"

# Install the git hooks once per clone so agent commits are checked. More than
# one file is installed: pre-commit and, when the config asks for it,
# commit-msg. A clone predating the commit-msg hook already has the first, so
# testing only for that one would leave the message check permanently
# uninstalled on exactly the clones that have been around longest.
#
# Which hooks are owed is scripts/libs/precommit.sh's answer, not a second copy
# of it here. The two copies this replaced had already drifted apart in how
# they tested for a hook file, and a startup hook that disagrees with
# scripts/doctor about whether a clone is set up is worse than either answer.
if [[ -f .pre-commit-config.yaml ]] && command -v pre-commit >/dev/null 2>&1 \
  && [[ -f scripts/libs/precommit.sh ]]; then
  # shellcheck source-path=SCRIPTDIR
  # shellcheck source=../../scripts/libs/precommit.sh
  source scripts/libs/precommit.sh
  if [[ -n "$(pre_commit_hooks_missing .pre-commit-config.yaml)" ]]; then
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

echo "Read the nearest CLAUDE.md above every path you touch before editing, and update the owning docs after meaningful changes. The full documentation contract is .openclaude/rules/documentation.md."
