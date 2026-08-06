#!/usr/bin/env bash
set -euo pipefail

# Symlinks and .. are resolved before comparison so that a path inside the
# repository cannot be used to reach outside it.
ask() {
  local reason="$1"

  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

allow() {
  exit 0
}

input="$(cat)"
file_path="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")"

if [[ -z "$file_path" ]]; then
  allow
fi

project_dir="${CLAUDE_PROJECT_DIR:-$(jq -r '.cwd // empty' <<<"$input")}"

if [[ -z "$project_dir" ]]; then
  ask "Cannot determine the repository root, so this write cannot be confirmed as inside it."
fi

resolved_project="$(realpath -m -- "$project_dir")"

if [[ "$file_path" != /* ]]; then
  file_path="$resolved_project/$file_path"
fi

resolved_target="$(realpath -m -- "$file_path")"

if [[ "$resolved_target" == "$resolved_project" || "$resolved_target" == "$resolved_project"/* ]]; then
  allow
fi

# Background jobs get a sanctioned scratch directory outside the repository.
if [[ -n "${CLAUDE_JOB_DIR:-}" ]]; then
  resolved_job_dir="$(realpath -m -- "$CLAUDE_JOB_DIR")"
  if [[ "$resolved_target" == "$resolved_job_dir"/* ]]; then
    allow
  fi
fi

ask "$resolved_target is outside the repository at $resolved_project."
