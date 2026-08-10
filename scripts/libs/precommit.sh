# shellcheck shell=bash
# Which pre-commit hooks this repository asks for, and which of them this clone
# is missing. Sourced by scripts/doctor and .claude/hooks/session-start.sh --
# one reports the gap, the other closes it, and both need the same answer.
#
# Sourced, never executed: no shebang, no executable bit, a .sh extension so
# linters recognize it. The same rule libs/detect.sh follows, for the same
# reason.
#
# This is not in libs/detect.sh. That module owns language-specific decisions
# and is dispatched by language_capabilities; a git hook is present in every
# repository whatever it is written in, so there is no language to detect.

# The hook types `pre-commit install` will write here.
#
# Parsed rather than grepped for one string, because both YAML forms are valid
# and a formatter or a hand-edit can turn either into the other:
#
#   default_install_hook_types: [pre-commit, commit-msg]
#
#   default_install_hook_types:
#     - pre-commit
#     - commit-msg
#
# A single-line pattern matches only the first. Against the second it finds
# nothing, reports no hook types beyond the default, and every caller quietly
# stops requiring the commit-msg hook -- a check that did not run reading as a
# check that passed, which is the failure this whole file exists to prevent.
#
# An absent key is not an error: pre-commit's own default is pre-commit alone,
# so that is what an absent key means here too.
pre_commit_hook_types() {
  local config="$1"
  local line value in_block=0 found=0 raw="" item
  local -a items

  [[ -s "$config" ]] || return 0

  while IFS= read -r line; do
    line="${line%%#*}"

    if [[ "$line" =~ ^default_install_hook_types:[[:space:]]*(.*)$ ]]; then
      found=1
      value="${BASH_REMATCH[1]}"

      if [[ -z "${value//[[:space:]]/}" ]]; then
        in_block=1
      else
        value="${value#*[}"
        value="${value%]*}"
        raw+=" ${value//,/ }"
      fi
      continue
    fi

    if (( in_block )); then
      if [[ "$line" =~ ^[[:space:]]+-[[:space:]]*(.+)$ ]]; then
        raw+=" ${BASH_REMATCH[1]}"
        continue
      fi
      # Any line back at column zero has ended the list.
      [[ "$line" =~ ^[^[:space:]] ]] && in_block=0
    fi
  done < "$config"

  (( found )) || raw="pre-commit"

  # A herestring rather than a pipe: under `set -euo pipefail` a reader that
  # exits early kills the writer with SIGPIPE and pipefail reports 141.
  read -ra items <<< "$raw"
  for item in "${items[@]:-}"; do
    item="${item//\"/}"
    item="${item//\'/}"
    [[ -n "$item" ]] && printf '%s\n' "$item"
  done

  return 0
}

# Of those hook types, the ones with no hook file in this clone. Empty output
# means every hook the config asks for is installed.
#
# The hook path comes from `git rev-parse --git-path` rather than a literal
# .git/hooks: in a linked worktree .git is a file, not a directory, and the
# hooks live in the shared common dir, so a hardcoded path reports an installed
# hook missing there.
pre_commit_hooks_missing() {
  local hooks_dir types hook_type

  hooks_dir="$(git rev-parse --git-path hooks 2>/dev/null || echo .git/hooks)"
  types="$(pre_commit_hook_types .pre-commit-config.yaml)"

  while IFS= read -r hook_type; do
    [[ -n "$hook_type" ]] || continue
    [[ -e "$hooks_dir/$hook_type" ]] || printf '%s\n' "$hook_type"
  done <<< "$types"

  return 0
}
