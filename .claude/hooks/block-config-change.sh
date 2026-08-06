#!/usr/bin/env bash
set -euo pipefail

# A session must not grant itself new permissions. Blocking here stops an
# edited settings or skill file from hot-reloading into the running session;
# the edit stays on disk for review and takes effect on the next session.
input="$(cat)"
source_type="$(jq -r '.source // "unknown"' <<<"$input")"
file_path="$(jq -r '.file_path // "unknown file"' <<<"$input")"

jq -n --arg reason "Blocked mid-session reload of $source_type ($file_path). The edit is still on disk: review the diff and start a new session to apply it." '{
  decision: "block",
  reason: $reason
}'
