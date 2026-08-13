#!/usr/bin/env bash
input=$(cat)

rgb() { printf '\033[38;2;%d;%d;%dm' "$1" "$2" "$3"; }

# Snapshot the session's current cumulative totals (tokens, durations, line
# counts) into the baseline file, so widgets can show deltas since last reset.
# The cache counters are baselined alongside the token totals because the session
# segment sums all four; offsetting only some of them would mix "since reset"
# with "since session start" inside one figure.
write_current_baseline() {
  echo "$input" | jq \
    --argjson total_in "$total_in" \
    --argjson total_out "$total_out" \
    --argjson cache_read "$session_cache_read" \
    --argjson cache_create "$session_cache_create" \
    --arg turn_id "$turn_id" \
    --argjson turn_in "$turn_in" \
    --argjson turn_out "$turn_out" \
    --argjson turn_cache_read "$cache_read" \
    --argjson turn_cache_create "$cache_create" \
    '{total_in: $total_in,
      total_out: $total_out,
      cache_read: $cache_read,
      cache_create: $cache_create,
      turn_id: $turn_id,
      turn_in: $turn_in,
      turn_out: $turn_out,
      turn_cache_read: $turn_cache_read,
      turn_cache_create: $turn_cache_create,
      lines_add: (.cost.total_lines_added // 0),
      lines_del: (.cost.total_lines_removed // 0)}' > "$1"
}

# Token accounting reads the transcript, not .context_window.current_usage: that
# block describes only the most recent API call, and a single user turn usually
# spans many (every tool round-trip is another call). Summing snapshots across
# renders cannot recover the truth either -- the statusline is sampled on
# terminal repaint, so it sees some calls several times while they stream and
# misses others entirely. The transcript is the authoritative per-call record.
#
# Emits: turn_in turn_out turn_cr turn_cc sess_in sess_out sess_cr sess_cc turn_id
# Sidechain (subagent) calls are excluded -- they bill separately and would swamp
# the figure for the turn the user is actually watching.
# shellcheck disable=SC2016 # jq variables deliberately expand inside jq, not Bash.
TOKENS_JQ='
  [ split("\n")[] | select(length>0) | (fromjson? // empty) ] as $rows
  # A turn starts at the last genuine human prompt. The noise filter mirrors the
  # tool-ratio block: slash commands, system notes and continuation notices all
  # arrive as user-type strings and would each falsely open a new turn.
  | ([ $rows | to_entries[]
       | select(.value.type=="user" and (.value.isMeta//false)==false
                and (.value.isSidechain//false)==false
                and (.value.message.content|type)=="string"
                and ((.value.message.content|test($noise))|not))
       | .key ] | last) as $b
  # One logical call can be logged more than once while its output streams.
  # Group by message id and take the high-water mark rather than adding.
  | def tally: group_by(.message.id)
      | map({i:(map(.message.usage.input_tokens//0)|max),
             o:(map(.message.usage.output_tokens//0)|max),
             r:(map(.message.usage.cache_read_input_tokens//0)|max),
             c:(map(.message.usage.cache_creation_input_tokens//0)|max)})
      | {i:(map(.i)|add // 0), o:(map(.o)|add // 0),
         r:(map(.r)|add // 0), c:(map(.c)|add // 0)};
    def billable: select((.isSidechain//false)==false and .message.usage!=null);
    ([ $rows[] | billable ] | tally) as $sess
  | ([ $rows[(($b // -1) + 1):][] | billable ] | tally) as $turn
  | [$turn.i, $turn.o, $turn.r, $turn.c,
     $sess.i, $sess.o, $sess.r, $sess.c,
     ($rows[$b // 0].uuid // "none")] | @tsv
'

# Slash commands and system notices arrive as user-type strings; neither opens a
# turn. Shared by the token accounting and the tool-ratio window.
PROMPT_NOISE='^Another Claude session sent a message:|^This session is being continued|^<system-reminder>|^\[System note\]|^Caveat:|<command-name>|<local-command-stdout>'

# Every scalar the payload supplies, read in one pass. These used to be sixteen
# separate `echo "$input" | jq` calls; each forked a jq and re-parsed the whole
# payload, which cost more than reading the transcript does. Tab-separated with a
# sentinel for absent fields, because @tsv would collapse an empty string and an
# absent key into the same thing and several segments key off "unset".
NUL=$'\x1f'
IFS=$'\t' read -r session_id transcript_path native_model used ctx_size \
  payload_total_in payload_total_out lines_add lines_del total_cost \
  effort agent_name five_hour_pct five_hour_reset seven_day_pct seven_day_reset \
  workspace_dir < <(
  echo "$input" | jq -r --arg nul "$NUL" '
    def s(f): (f // $nul) | tostring;
    [ s(.session_id), s(.transcript_path), (.model.display_name // "?"),
      s(.context_window.used_percentage), (.context_window.context_window_size // 200000),
      (.context_window.total_input_tokens // 0), (.context_window.total_output_tokens // 0),
      (.cost.total_lines_added // 0), (.cost.total_lines_removed // 0),
      (.cost.total_cost_usd // 0),
      s(.effort.level), s(.agent.name),
      s(.rate_limits.five_hour.used_percentage), s(.rate_limits.five_hour.resets_at),
      s(.rate_limits.seven_day.used_percentage), s(.rate_limits.seven_day.resets_at),
      s(.workspace.current_dir)
    ] | @tsv' 2>/dev/null
)
for v in session_id transcript_path used effort agent_name \
         five_hour_pct five_hour_reset seven_day_pct seven_day_reset workspace_dir; do
  [ "${!v}" = "$NUL" ] && printf -v "$v" '%s' ''
done
total_in=$payload_total_in
total_out=$payload_total_out

# The git segments describe the session's directory, which is what the payload
# reports -- not this process's cwd. They agree today, but only incidentally:
# nothing in the protocol promises the statusline is spawned from the session
# directory, and if they ever diverge the cwd version describes the wrong repo.
# Fall back to cwd only when the payload omits the field.
[ -n "$workspace_dir" ] && [ -d "$workspace_dir" ] || workspace_dir=$(pwd)

state_key=""
if [ -n "$transcript_path" ]; then
  state_key=$(printf '%s' "$transcript_path" | cksum | cut -d' ' -f1)
elif [ -n "$session_id" ]; then
  state_key="$session_id"
fi

reset_flag=""
legacy_reset_flag=""
baseline_file=""
alarm_turn_file=""
cache_alarm_file=""
cost_history_file=""
err_rotate_file=""
slot_rotate_file=""
if [ -n "$state_key" ]; then
  state_dir="/tmp/claude-statusline/${state_key}"
  mkdir -p "$state_dir" 2>/dev/null
  reset_flag="$state_dir/reset.flag"
  baseline_file="$state_dir/baseline.json"
  alarm_turn_file="$state_dir/alarm-turn.txt"
  cache_alarm_file="$state_dir/cache-alarm.txt"
  cost_history_file="$state_dir/cost-history.txt"
  err_rotate_file="$state_dir/err-rotate.txt"
  slot_rotate_file="$state_dir/slot-rotate.txt"
fi

# Cache rebuild >= this many tokens in one turn raises the alarm.
CACHE_REBUILD_TOKENS=20000
# How long the alarm stays visible after the spike.
CACHE_ALARM_LINGER_S=90
# Rolling window for the burn-rate figure.
BURN_WINDOW_S=600
# Transcript tail scanned for the repeated-error segment.
ERR_SCAN_LINES=400
# A signature must recur this many times before it is worth showing.
ERR_MIN_REPEAT=3
# ...and must have recurred within this many tool results, or it is stale.
ERR_LIVE_WINDOW=12
# Human:tool ratio is measured over the last N prompts, and only shown when it
# falls below the floor. Calibrated by replaying 80 windows across real sessions:
# median 10.2, p25 6.6. A floor of 4.5 fires on ~11% of them -- every sample in
# the 4.0-4.5 band was the short-directive grind ("y", "commit and push"), so the
# band is signal, not noise.
RATIO_PROMPTS=5
RATIO_FLOOR=4.5
# Upstream drift: refreshed by a background fetch no more often than this.
DRIFT_FETCH_INTERVAL_S=300
# Commits behind upstream before the drift segment is worth a rotation slot.
DRIFT_MIN_BEHIND=3
if [ -n "$session_id" ]; then
  legacy_reset_flag="/tmp/claude-statusline-reset-${session_id}.flag"
fi

if [ -n "$legacy_reset_flag" ] && [ "$legacy_reset_flag" != "$reset_flag" ] && [ -f "$legacy_reset_flag" ]; then
  touch "$reset_flag"
  rm -f "$legacy_reset_flag"
fi

BOLD='\033[1m'
DIM='\033[2m'
RST='\033[0m'
SEP=" ${DIM}│${RST} "

# -- Model (the routed slot of the launched profile) --
# The transcript is deliberately never consulted: it reports the literal string
# "unknown", and preferring it would reintroduce a dependency on model reporting
# that the statusline does not need. See ADR 008. The cost is that per-request
# routing overrides (webSearch, longContext, compact, CCR-SUBAGENT-MODEL) are
# invisible here -- this names the configured slot, not necessarily the model
# that served the last turn.
model="$native_model"

# The profile this session was launched with, if any: `ccr code --profile <name>`
# starts claude with a temp --settings file whose ANTHROPIC_BASE_URL ends in
# /profile/<name>, and the profile's Router overrides the base config's. Walk up
# the process tree, since the statusline may be spawned through a shell.
PROFILE_WALK_MAX_DEPTH=6
# Matched against each argv entry rather than the whole cmdline, so the trailing
# character class only has to stop at a quote the shell left in the argument.
PROFILE_SETTINGS_RE='(/tmp/claude-code-router/ccr-settings-[^"[:space:]]+\.json)'
# Every step reads /proc through bash builtins. The walk runs on each render and
# usually falls through all six levels without matching, so doing it with tr, grep
# and ps -- three forks per level -- cost ~165ms a render to answer "no profile".
# Redirections are written `2>/dev/null <` because the suppression must be in
# place before the open: a pid can exit mid-walk, and these reads are the only
# thing standing between that race and stderr.
ccr_launched_profile() {
  local pid=$PPID depth=0 arg settings url key val parent
  local -a argv
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null && [ "$depth" -lt "$PROFILE_WALK_MAX_DEPTH" ]; do
    argv=(); settings=""
    mapfile -d '' argv 2>/dev/null < "/proc/$pid/cmdline"
    for arg in "${argv[@]}"; do
      [[ $arg =~ $PROFILE_SETTINGS_RE ]] && { settings=${BASH_REMATCH[1]}; break; }
    done
    if [ -n "$settings" ] && [ -f "$settings" ]; then
      url=$(jq -r '.env.ANTHROPIC_BASE_URL // empty' "$settings" 2>/dev/null)
      case "$url" in
        */profile/*) printf '%s' "${url##*/profile/}"; return 0 ;;
      esac
    fi
    parent=""
    while read -r key val; do
      [ "$key" = "PPid:" ] && { parent=$val; break; }
    done 2>/dev/null < "/proc/$pid/status"
    pid=$parent
    depth=$((depth + 1))
  done
}

# Routing is by model tier (opus/sonnet/haiku), so mirror that here: map the tier
# Claude Code reports via .model.display_name to the launched profile's slot for
# that tier, then to Router.<tier>, then to Router.default. If nothing resolves,
# the native display name stands.
case "$(printf '%s' "$native_model" | tr '[:upper:]' '[:lower:]')" in
  *opus*)   ccr_tier="opus" ;;
  *sonnet*) ccr_tier="sonnet" ;;
  *haiku*)  ccr_tier="haiku" ;;
  *)        ccr_tier="default" ;;
esac

# Shared slot-lookup rule for both sources: the tier's slot, else the default slot.
# shellcheck disable=SC2016 # $t is a jq variable, not a Bash expansion.
tier_slot='.[$t] // .default // empty'

ccr_route=""
ccr_profile=$(ccr_launched_profile)
if [ -n "$ccr_profile" ]; then
  ccr_route=$(jq -r --arg p "$ccr_profile" --arg t "$ccr_tier" \
    '.[] | select(.name == $p) | .config | '"$tier_slot" \
    /home/neal/.claude-code-router/profiles.json 2>/dev/null)
fi
if [ -z "$ccr_route" ]; then
  ccr_route=$(jq -r --arg t "$ccr_tier" '.Router | '"$tier_slot" /home/neal/.claude-code-router/config.json 2>/dev/null)
fi

if [ -n "$ccr_route" ]; then
  ccr_selected_model=${ccr_route#*,}
  [ -n "$ccr_selected_model" ] && model="$ccr_selected_model"
fi

# Render model identifiers as readable labels only. Routing keeps using the raw
# identifier above; this runs solely on the value printed in the status line.
format_model_label() {
  local value=${1##*/} word lower formatted="" separator=""
  value=${value%:free}
  value=${value%-free}
  # Anthropic repeats its vendor prefix on every family model; the family name
  # is the useful part of a status line (e.g. "Opus 4.6").
  [[ $value =~ ^claude-[^0-9]*[[:alpha:]] ]] && value=${value#claude-}
  # Drop common version-date suffixes before converting separators to spaces.
  value=$(printf '%s' "$value" | sed -E     -e 's/-[0-9]{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])($|-)/\3/g'     -e 's/-(0[1-9]|1[0-2])-[0-9]{4}($|-)/\2/g'     -e 's/-[0-9]{2}(0[1-9]|1[0-2])($|-)/\1/g'     -e 's/([0-9]+)-([0-9]+)([^[:alnum:]]|$)/\1.\2\3/g')
  value=${value//-/ }
  value=${value//:/ }
  for word in $value; do
    lower=${word,,}
    if [[ $lower =~ ^[a-z]?[0-9]+([.][0-9]+)?[bmk]$ ]]; then
      word=${lower^^}
    else
      case "$lower" in
        gpt|glm|oss|it|vl|cli|pii|fim|xs|fp8|c4ai) word=${lower^^} ;;
        *) word=${lower^} ;;
      esac
    fi
    formatted+="${separator}${word}"
    separator=" "
  done
  printf '%s' "${formatted:-$1}"
}
model_display=$(format_model_label "$model")

# -- Context window --

# -- Token accounting (see TOKENS_JQ) --
# Both the per-turn and the session figures come from the transcript. The
# payload's totals stay as the fallback for the first render of a fresh session,
# before any assistant reply has been logged.
turn_in=0; turn_out=0; cache_read=0; cache_create=0
session_cache_read=0; session_cache_create=0
turn_id=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  read -r t_in t_out t_cr t_cc s_in s_out s_cr s_cc turn_id < <(
    jq -rR -s --arg noise "$PROMPT_NOISE" "$TOKENS_JQ" "$transcript_path" 2>/dev/null
  )
  # An empty or unparseable transcript still yields a full row of zeros, which is
  # non-empty and would shadow the payload's counters with 0. Only take the
  # transcript's session totals once it actually reports usage; the per-turn
  # figures have no other source, so they take the zeros either way.
  if [ -n "$t_in" ]; then
    turn_in=$t_in; turn_out=$t_out; cache_read=$t_cr; cache_create=$t_cc
    if [ "$((s_in + s_out + s_cr + s_cc))" -gt 0 ] 2>/dev/null; then
      session_cache_read=$s_cr; session_cache_create=$s_cc
      total_in=$s_in; total_out=$s_out
    fi
  fi
fi

# Reset baseline when requested via hook-created flag.
if [ -n "$reset_flag" ] && [ -f "$reset_flag" ]; then
  write_current_baseline "$baseline_file"
  rm -f "$reset_flag"
fi

# First run for this state key: the current totals become the baseline.
if [ -n "$baseline_file" ] && [ ! -f "$baseline_file" ]; then
  write_current_baseline "$baseline_file"
fi

baseline_total_in=0
baseline_total_out=0
baseline_cache_read=0
baseline_cache_create=0
baseline_turn_id=""
baseline_turn_in=0
baseline_turn_out=0
baseline_turn_cache_read=0
baseline_turn_cache_create=0
baseline_lines_add=0
baseline_lines_del=0
if [ -n "$baseline_file" ] && [ -f "$baseline_file" ]; then
  read -r baseline_total_in baseline_total_out baseline_cache_read baseline_cache_create baseline_turn_id baseline_turn_in baseline_turn_out baseline_turn_cache_read baseline_turn_cache_create baseline_lines_add baseline_lines_del < <(
    jq -r '[.total_in,.total_out,.cache_read,.cache_create,.turn_id,.turn_in,.turn_out,.turn_cache_read,.turn_cache_create,.lines_add,.lines_del] | map(. // 0) | @tsv' "$baseline_file" 2>/dev/null
  )
  baseline_total_in=${baseline_total_in:-0}
  baseline_total_out=${baseline_total_out:-0}
  baseline_cache_read=${baseline_cache_read:-0}
  baseline_cache_create=${baseline_cache_create:-0}
  baseline_turn_id=${baseline_turn_id:-}
  baseline_turn_in=${baseline_turn_in:-0}
  baseline_turn_out=${baseline_turn_out:-0}
  baseline_turn_cache_read=${baseline_turn_cache_read:-0}
  baseline_turn_cache_create=${baseline_turn_cache_create:-0}
  baseline_lines_add=${baseline_lines_add:-0}
  baseline_lines_del=${baseline_lines_del:-0}
fi

# Clamp invalid totals.
if [ "$total_in" -lt 0 ] 2>/dev/null; then total_in=0; fi
if [ "$total_out" -lt 0 ] 2>/dev/null; then total_out=0; fi

# Apply baseline offsets for resettable status widgets.
raw_total_in=$total_in
raw_total_out=$total_out

# Baselines written before turn snapshots existed can still be reconciled. If a
# reset happened during the active turn, its contribution is the part of the
# baseline above the session total immediately before that turn. If it happened
# earlier, the difference is negative and correctly becomes zero.
if [ -z "$baseline_turn_id" ] && [ -n "$turn_id" ]; then
  baseline_turn_id=$turn_id
  baseline_turn_in=$((baseline_total_in - (raw_total_in - turn_in)))
  baseline_turn_out=$((baseline_total_out - (raw_total_out - turn_out)))
  baseline_turn_cache_read=$((baseline_cache_read - (session_cache_read - cache_read)))
  baseline_turn_cache_create=$((baseline_cache_create - (session_cache_create - cache_create)))
  [ "$baseline_turn_in" -lt 0 ] && baseline_turn_in=0
  [ "$baseline_turn_out" -lt 0 ] && baseline_turn_out=0
  [ "$baseline_turn_cache_read" -lt 0 ] && baseline_turn_cache_read=0
  [ "$baseline_turn_cache_create" -lt 0 ] && baseline_turn_cache_create=0
fi

total_in=$((raw_total_in - baseline_total_in))
total_out=$((raw_total_out - baseline_total_out))
if [ "$total_in" -lt 0 ]; then total_in=$raw_total_in; fi
if [ "$total_out" -lt 0 ]; then total_out=$raw_total_out; fi
if [ "$total_in" -lt 0 ]; then total_in=0; fi
if [ "$total_out" -lt 0 ]; then total_out=0; fi

if [ "$session_cache_read" -ge "$baseline_cache_read" ]; then
  session_cache_read=$((session_cache_read - baseline_cache_read))
fi
if [ "$session_cache_create" -ge "$baseline_cache_create" ]; then
  session_cache_create=$((session_cache_create - baseline_cache_create))
fi

# A compact/reset can occur during a turn. The total above starts fresh at that
# point, so this same in-progress turn must start fresh too. For later turns the
# ids differ and their complete per-turn totals remain intact.
if [ -n "$turn_id" ] && [ "$turn_id" = "$baseline_turn_id" ]; then
  turn_in=$((turn_in - baseline_turn_in))
  turn_out=$((turn_out - baseline_turn_out))
  cache_read=$((cache_read - baseline_turn_cache_read))
  cache_create=$((cache_create - baseline_turn_cache_create))
  [ "$turn_in" -lt 0 ] && turn_in=0
  [ "$turn_out" -lt 0 ] && turn_out=0
  [ "$cache_read" -lt 0 ] && cache_read=0
  [ "$cache_create" -lt 0 ] && cache_create=0
fi

# Cache-invalidation alarm: a large cache_creation across a turn means the prompt
# prefix was rebuilt from scratch and re-paid at write rate. Stamp it so the
# segment can linger -- the spike happens on one turn and would otherwise scroll
# past unseen. A smoothed hit-rate hides exactly this event. Stamped once per
# turn: cache_create only grows as the turn's calls land, so an unguarded check
# would re-arm the alarm on every render and leave it permanently lit.
if [ -n "$cache_alarm_file" ] && [ -n "$alarm_turn_file" ] && [ -n "$turn_id" ] &&
   [ "$cache_create" -ge "$CACHE_REBUILD_TOKENS" ] 2>/dev/null; then
  read -r prev_alarm_turn 2>/dev/null < "$alarm_turn_file" || prev_alarm_turn=""
  if [ "$turn_id" != "$prev_alarm_turn" ]; then
    printf '%s %s\n' "$(date +%s)" "$cache_create" > "$cache_alarm_file"
    printf '%s\n' "$turn_id" > "$alarm_turn_file"
  fi
fi

# Efficiency = reused cache / total input work across session
cache_total=$((session_cache_read + session_cache_create + total_in))
if [ "$cache_total" -gt 0 ]; then
  cache_eff_pct=$((session_cache_read * 100 / cache_total))
else
  cache_eff_pct=0
fi

# -- Cost & velocity --
lines_add=$((lines_add - baseline_lines_add))
lines_del=$((lines_del - baseline_lines_del))

if [ "$lines_add" -lt 0 ]; then lines_add=0; fi
if [ "$lines_del" -lt 0 ]; then lines_del=0; fi

# -- Format token counts --
fmt_tok() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then
    printf '%s.%sM' "$((n / 1000000))" "$((n % 1000000 / 100000))"
  elif [ "$n" -ge 1000 ]; then
    printf '%s.%sK' "$((n / 1000))" "$((n % 1000 / 100))"
  else
    printf '%s' "$n"
  fi
}

# -- Burn rate (rolling window) --
# Session-average $/hr flattens out: one expensive stretch is diluted by every
# idle minute before it. Instead sample the cumulative cost over time and take
# the slope across BURN_WINDOW_S, so the figure reflects what the last few
# minutes actually cost and reacts when a session turns pathological.
burn_rate=""
if [ -n "$cost_history_file" ]; then
  now_s=$(date +%s)
  printf '%s %s\n' "$now_s" "$total_cost" >> "$cost_history_file"

  # Drop everything older than the window. Retaining a pre-window sample as the
  # baseline would be tempting, but after an idle gap that sample can be hours
  # old -- the span would silently stretch and the figure would no longer be the
  # rolling average it claims to be. Better to show nothing until the window
  # refills than to show an hour-long average labelled as ten minutes.
  cutoff=$((now_s - BURN_WINDOW_S))
  awk -v cutoff="$cutoff" '$1 >= cutoff' "$cost_history_file" > "${cost_history_file}.tmp" 2>/dev/null &&
    mv "${cost_history_file}.tmp" "$cost_history_file"

  # Slope over the retained span, projected to an hourly rate. Needs a span of
  # real elapsed time before the extrapolation means anything.
  burn_rate=$(awk '
    NR == 1 { t0 = $1; c0 = $2 }
    { t1 = $1; c1 = $2 }
    END {
      span = t1 - t0
      delta = c1 - c0
      if (span >= 60 && delta > 0) printf "%.2f", delta * 3600 / span
    }
  ' "$cost_history_file" 2>/dev/null)
fi

# -- Cache invalidation alarm --
cache_alarm=""
if [ -n "$cache_alarm_file" ] && [ -f "$cache_alarm_file" ]; then
  # The file can be read while another render is writing it, so the timestamp may
  # arrive truncated or absent. Default it to 0 unless it is all digits: ${x:-0}
  # alone only covers empty, and arithmetic on a partial write is a visible error.
  alarm_ts=""; alarm_tokens=""
  read -r alarm_ts alarm_tokens 2>/dev/null < "$cache_alarm_file"
  case $alarm_ts in ''|*[!0-9]*) alarm_ts=0 ;; esac
  alarm_age=$(( $(date +%s) - alarm_ts ))
  if [ "$alarm_age" -le "$CACHE_ALARM_LINGER_S" ] 2>/dev/null; then
    cache_alarm=$(fmt_tok "${alarm_tokens:-0}")
  else
    rm -f "$cache_alarm_file"
  fi
fi

# -- Repeated tool error --
# A scattering of one-off failures is normal and not worth screen space. The
# actionable signal is one failure recurring: the same thing has been retried
# and is still broken. So a signature has to clear two bars to be shown --
# repeated at least ERR_MIN_REPEAT times, and seen again within the last
# ERR_LIVE_WINDOW tool results. The second bar is what makes it self-clearing:
# once the fix lands and the call stops failing, it ages out on its own.
#
# The signal is .is_error on the tool_result block, not stderr -- stderr holds
# only a benign cwd notice, and real failures land in stdout mixed with normal
# output. Signature = the last failure-ish line of the result, digits masked so
# that line numbers, PIDs and timings collapse into one signature.
err_repeat=""
err_repeat_count=0
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  err_hits=$(tail -n "$ERR_SCAN_LINES" "$transcript_path" 2>/dev/null | jq -rc '
    select(.type=="user") | .message.content[]?
    | select(.type=="tool_result")
    | if (.is_error // false) then
        ((if (.content|type)=="string" then .content
          else ((.content[]?|select(.type=="text")|.text)//"") end)
         | gsub("\\[[0-9;]*m"; "")
         | gsub("<tool_use_error>|</tool_use_error>"; "")
         | split("\n") | map(select(test("\\S")))
         | map(select(test("complete log of this run|^\\s*at ")|not))
         | ( (map(select(test("(?i)error|fatal|cannot|not found|no such|denied|invalid|failed|refused|timed out")))[-1])
             // (map(select(test("^Exit code \\d+$")|not))[-1]) // .[0] // "" )
         | sub("^\\s+";""))
      else "" end
  ' 2>/dev/null \
    | sed -E 's/[0-9]+/N/g' | cut -c1-56 \
    | grep -v "doesn't want to proceed with this tool use" \
    | awk -v min="$ERR_MIN_REPEAT" -v live="$ERR_LIVE_WINDOW" '
        { n++; if ($0 != "") { cnt[$0]++; last[$0] = n } }
        END {
          for (s in cnt)
            if (cnt[s] >= min && n - last[s] < live)
              printf "%d\t%s\n", cnt[s], s
        }' | sort -rn)

  if [ -n "$err_hits" ]; then
    err_total=$(printf '%s\n' "$err_hits" | wc -l)

    # More than one thing broken at once: rotate a slot per render so each gets
    # seen, rather than pinning the loudest and hiding the rest.
    err_idx=0
    if [ "$err_total" -gt 1 ] && [ -n "$err_rotate_file" ]; then
      [ -f "$err_rotate_file" ] && read -r err_idx < "$err_rotate_file"
      err_idx=$(( (${err_idx:-0}) % err_total ))
      printf '%s\n' "$(( (err_idx + 1) % err_total ))" > "$err_rotate_file"
    fi

    err_line=$(printf '%s\n' "$err_hits" | sed -n "$((err_idx + 1))p")
    err_repeat_count=${err_line%%$'\t'*}
    err_repeat=${err_line#*$'\t'}
  elif [ -n "$err_rotate_file" ]; then
    rm -f "$err_rotate_file"
  fi
fi

# -- Human:tool leverage ratio --
# Tool calls per prompt over the last RATIO_PROMPTS prompts. Windowing by prompt
# rather than by transcript line matters: a line window reports 0 during long
# autonomous stretches, which is maximum leverage being misread as none. Only the
# low end is interesting -- a high ratio is the tool working as intended -- so
# this shows up only under the floor. Slash commands, teammate messages and
# continuation notices arrive as user-type strings and would inflate the prompt
# count, so they are filtered out.
ratio_val=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  ratio_val=$(tail -n "$ERR_SCAN_LINES" "$transcript_path" 2>/dev/null | jq -rc --arg noise "$PROMPT_NOISE" '
    select(.type=="user" and (.isMeta//false)==false and (.isSidechain//false)==false)
    | if (.message.content|type)=="array" and ([.message.content[]?|select(.type=="tool_result")]|length)>0 then "T"
      elif (.message.content|type)=="string" then
        (.message.content | if test($noise) then empty else "H" end)
      else empty end
  ' 2>/dev/null | awk -v k="$RATIO_PROMPTS" -v floor="$RATIO_FLOOR" '
      { seq[++n] = $0; if ($0 == "H") hidx[++hn] = n }
      END {
        if (hn < k) exit
        t = 0
        for (i = hidx[hn - k + 1]; i <= n; i++) if (seq[i] == "T") t++
        r = t / k
        if (r < floor) printf "%.1f", r
      }')
fi

# -- Upstream drift --
# Commits behind upstream. "Behind" is the actionable half: the branch moved
# under you and a rebase is cheapest before conflicts form. The count is only as
# fresh as the last fetch, so refresh in the background on an interval and read
# the ref inline -- rev-list against an existing ref is ~3ms, a fetch is ~700ms
# and would be paid on every render.
# The stamp is located with --git-path rather than assembled as "$git_root/.git":
# in a worktree or submodule .git is a file, not a directory, so the assembled
# form both fails the -d test and names a path that does not exist. Worktrees are
# a normal way to work here, and the whole segment was silently dead in them.
drift_behind=0
# --git-path is relative in an ordinary repo and absolute in a worktree, so it is
# resolved against the workspace rather than stat'd as-is from this process's cwd.
drift_stamp=$(git -C "$workspace_dir" rev-parse --path-format=absolute --git-path FETCH_HEAD 2>/dev/null)
if [ -n "$drift_stamp" ]; then
  drift_age=$DRIFT_FETCH_INTERVAL_S
  [ -f "$drift_stamp" ] && drift_age=$(( $(date +%s) - $(stat -c '%Y' "$drift_stamp" 2>/dev/null || echo 0) ))
  if [ "$drift_age" -ge "$DRIFT_FETCH_INTERVAL_S" ] 2>/dev/null; then
    (timeout 20 git -C "$workspace_dir" fetch --quiet >/dev/null 2>&1 &) >/dev/null 2>&1
  fi
  drift_behind=$(git -C "$workspace_dir" rev-list --count 'HEAD..@{u}' 2>/dev/null)
  drift_behind=${drift_behind:-0}
fi

# -- Rotating advisory slot --
# These four fire on unrelated conditions and are all threshold-gated, so they
# are usually absent. Sharing one slot keeps line 1 from growing when more than
# one does fire; whichever are live take turns across renders.
slot_text=""
slot_items=()
[ -n "$err_repeat" ] && slot_items+=("$(rgb 240 90 60)🔁 ${err_repeat_count}× $(rgb 220 160 140)${err_repeat:0:34}")
[ -n "$cache_alarm" ] && slot_items+=("$(rgb 220 40 20)🧊 ${cache_alarm}")
[ -n "$ratio_val" ] && slot_items+=("$(rgb 250 200 90)🪢 ${ratio_val}:1")
[ "$drift_behind" -ge "$DRIFT_MIN_BEHIND" ] 2>/dev/null && slot_items+=("$(rgb 160 160 255)🌿 ↓${drift_behind}")

if [ "${#slot_items[@]}" -gt 0 ]; then
  slot_idx=0
  if [ "${#slot_items[@]}" -gt 1 ] && [ -n "$slot_rotate_file" ]; then
    [ -f "$slot_rotate_file" ] && read -r slot_idx < "$slot_rotate_file"
    slot_idx=$(( ${slot_idx:-0} % ${#slot_items[@]} ))
    printf '%s\n' "$(( (slot_idx + 1) % ${#slot_items[@]} ))" > "$slot_rotate_file"
  fi
  slot_more=""
  [ "${#slot_items[@]}" -gt 1 ] && slot_more=" +$(( ${#slot_items[@]} - 1 ))"
  slot_text="${slot_items[$slot_idx]}${slot_more}${RST}"
elif [ -n "$slot_rotate_file" ]; then
  rm -f "$slot_rotate_file"
fi

# -- Effort + agent --

# -- Token speed (CCR-only) --
token_speed=""
token_ttft=""
CCR_DEBUG_LOG="/tmp/ccr-statusline-debug.log"
ccr_debug() {
  [ "${CCR_STATUSLINE_DEBUG:-0}" = "1" ] || return 0
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$CCR_DEBUG_LOG"
}

ccr_debug "start session_id=$session_id"

if [ -n "$session_id" ]; then
  speed_file="/tmp/claude-code-router/session-${session_id}.json"
  ccr_debug "check speed_file=$speed_file exists=$([ -f "$speed_file" ] && echo yes || echo no)"
  if [ -f "$speed_file" ]; then
    speed_data=$(cat "$speed_file" 2>/dev/null)
    tps=$(echo "$speed_data" | jq -r '.tokensPerSecond // 0' 2>/dev/null)
    ts_stamp=$(echo "$speed_data" | jq -r '.timestamp // 0' 2>/dev/null)
    now_ms=$(($(date +%s) * 1000))
    age_s=$(( (now_ms - ts_stamp) / 1000 ))
    ccr_debug "file tps=$tps age_s=$age_s"
    # Also gates the ccr fallback below; see the comment there.
    TPS_FALLBACK_MAX_AGE_S=60
    # Persist last-nonzero tps to a sidecar so it lingers TPS_LINGER_S seconds
    # even after CCR overwrites the speed_file with tokensPerSecond:0 between turns.
    TPS_LINGER_S=15
    lastgood_file="/tmp/claude-code-router/session-${session_id}.tpslast"
    if [ "$tps" -gt 0 ] 2>/dev/null; then
      printf '%s %s\n' "$tps" "$ts_stamp" > "$lastgood_file"
    fi
    lastgood_tps=0; lastgood_ts=0
    [ -f "$lastgood_file" ] && read -r lastgood_tps lastgood_ts < "$lastgood_file"
    lastgood_age_s=$(( (now_ms - lastgood_ts) / 1000 ))
    if [ "$lastgood_tps" -gt 0 ] 2>/dev/null && [ "$lastgood_age_s" -le "$TPS_LINGER_S" ] 2>/dev/null; then
      token_speed="${lastgood_tps}"
      ccr_debug "lastgood accepted token_speed=$token_speed lastgood_age_s=$lastgood_age_s"
    else
      ccr_debug "lastgood rejected lastgood_tps=$lastgood_tps lastgood_age_s=$lastgood_age_s"
    fi
    # Time-to-first-token (ms) from the same file. Unlike live speed, this
    # lingers: it shows the last response's TTFT even when idle (no freshness gate).
    ttft_ms=$(echo "$speed_data" | jq -r '.timeToFirstToken // empty' 2>/dev/null)
    if [ -n "$ttft_ms" ] && [ "$ttft_ms" -gt 0 ] 2>/dev/null; then
      if [ "$ttft_ms" -ge 1000 ]; then
        token_ttft=$(awk -v m="$ttft_ms" 'BEGIN{printf "%.1fs", m/1000}')
      else
        token_ttft="${ttft_ms}ms"
      fi
      ccr_debug "ttft accepted token_ttft=$token_ttft"
    fi
  fi
fi

# Fallback: ask CCR to render statusline and parse its speed segment. This forks
# node and costs ~500ms -- by far the most expensive thing on the render path --
# so it runs only where it can actually recover something.
#
# Two conditions narrow it. With no sidecar at all there is nothing to recover:
# CCR derives its figure from the session file that was never written, so the
# fork can only return the same blank the fast path already produced. And once
# the sidecar is older than TPS_FALLBACK_MAX_AGE_S the session is simply idle
# between turns -- there is no in-flight response to measure, and the fork
# returns nothing while costing half a second on every repaint.
if [ -z "$token_speed" ] && [ -n "$speed_file" ] && [ -f "$speed_file" ] &&
   [ -n "$age_s" ] && [ "$age_s" -le "$TPS_FALLBACK_MAX_AGE_S" ] 2>/dev/null &&
   command -v ccr >/dev/null 2>&1; then
  ccr_out=$(printf '%s' "$input" | ccr statusline 2>/dev/null | tr -d '\r')
  ccr_line=$(printf '%s' "$ccr_out" | grep -m1 -oE '⚡[0-9]+(\.[0-9]+)?[[:space:]]*t/s|[0-9]+(\.[0-9]+)?[[:space:]]*t/s')
  ccr_debug "fallback ccr_line=${ccr_line:-<empty>}"
  if [ -n "$ccr_line" ]; then
    token_speed=$(printf '%s' "$ccr_line" | grep -oE '[0-9]+(\.[0-9]+)?' | head -n1)
    ccr_debug "fallback accepted token_speed=$token_speed"
  fi
fi

ccr_debug "final token_speed=${token_speed:-<empty>}"


# -- Context tokens --
# Context alarm thresholds (tokens in use).
CTX_DANGER_TOKENS=150000
CTX_WARN_TOKENS=125000

# Mid-response, Claude Code intermittently emits a payload whose context_window
# block is zeroed while .cost stays populated, so used_percentage arrives as 0.
# Persist the last real reading and show it through the gap, rather than claiming
# the context emptied. (The token counters are immune -- they read the
# transcript -- but this segment still comes from the payload.)
ctx_pct_file=""
[ -n "$state_key" ] && ctx_pct_file="/tmp/claude-statusline/${state_key}/last-ctx-pct.txt"
if [ -n "$ctx_pct_file" ]; then
  if [ -z "$used" ] || [ "${used%%.*}" -eq 0 ] 2>/dev/null; then
    [ -f "$ctx_pct_file" ] && read -r used < "$ctx_pct_file"
  else
    printf '%s\n' "$used" > "$ctx_pct_file"
  fi
fi

if [ -n "$used" ]; then
  pct=$(printf '%.0f' "$used")
  if [ "$ctx_size" -gt 0 ]; then
    used_tokens=$((pct * ctx_size / 100))
  else
    used_tokens=0
  fi

  used_k=$((used_tokens / 1000))
  total_k=$((ctx_size / 1000))

  if [ "$used_tokens" -ge "$CTX_DANGER_TOKENS" ]; then
    status_emoji="💀 "
    pc=$(rgb 220 40 20)
  elif [ "$used_tokens" -ge "$CTX_WARN_TOKENS" ]; then
    status_emoji="⚠️ "
    pc=$(rgb 220 200 0)
  else
    status_emoji="🪟 "
    pc=$(rgb 0 200 80)
  fi
  ctx_part="${status_emoji}${pc}${used_k}K/${total_k}K${RST}"
else
  ctx_part="$(rgb 60 60 60)--K/--K${RST}"
fi

# -- Rate limits --
format_time_remaining() {
  local epoch=$1 now remaining days hours minutes
  [ -n "$epoch" ] || return 0
  [ "$epoch" -gt 0 ] 2>/dev/null || return 0

  now=$(date +%s)
  remaining=$((epoch - now))
  if [ "$remaining" -lt 0 ]; then remaining=0; fi

  if [ "$remaining" -ge 86400 ]; then
    days=$((remaining / 86400))
    hours=$(((remaining % 86400) / 3600))
    printf '%sd%sh' "$days" "$hours"
  elif [ "$remaining" -ge 3600 ]; then
    hours=$((remaining / 3600))
    printf '%sh' "$hours"
  elif [ "$remaining" -ge 60 ]; then
    minutes=$((remaining / 60))
    printf '%sm' "$minutes"
  else
    printf '%ss' "$remaining"
  fi
}

rate_limit_segment() {
  local label=$1 pct_raw=$2 reset_epoch=$3 used_pct remaining_pct time_remaining
  [ -n "$pct_raw" ] || return 0

  used_pct=$(printf '%.0f' "$pct_raw" 2>/dev/null) || return 0
  if [ "$used_pct" -lt 0 ] 2>/dev/null; then used_pct=0; fi
  if [ "$used_pct" -gt 100 ] 2>/dev/null; then used_pct=100; fi
  remaining_pct=$((100 - used_pct))

  time_remaining=$(format_time_remaining "$reset_epoch")
  if [ -n "$time_remaining" ]; then
    printf '%b' "${label} ${remaining_pct}% ${time_remaining}"
  else
    printf '%b' "${label} ${remaining_pct}%"
  fi
}

rate_limit_parts=""
five_hour_part=$(rate_limit_segment "5h" "$five_hour_pct" "$five_hour_reset")
seven_day_part=$(rate_limit_segment "7d" "$seven_day_pct" "$seven_day_reset")
if [ -n "$five_hour_part" ]; then
  rate_limit_parts="$five_hour_part"
fi
if [ -n "$seven_day_part" ]; then
  if [ -n "$rate_limit_parts" ]; then
    rate_limit_parts+="${SEP}${seven_day_part}"
  else
    rate_limit_parts="$seven_day_part"
  fi
fi

# -- Effort icon --
effort_str=""
if [ -n "$effort" ]; then
  case "$effort" in
    low)   ei="🐢" ;;
    medium) ei="⚙️" ;;
    high)  ei="🧠" ;;
    xhigh) ei="💪" ;;
    max)   ei="🔮" ;;
    *)     ei="⚙️" ;;
  esac
  effort_str="${ei} ${effort}"
fi

# -- Git segment (tmux2k-style behavior) --
build_git_segment() {
  local path branch git_status git_changes
  local added=0 modified=0 updated=0 deleted=0
  local display_status
  local added_icon modified_icon updated_icon deleted_icon repo_icon diff_icon no_repo_icon
  local branch_fmt x y line
  local top_level repo_name remote_url repo_url repo_label

  path=$workspace_dir
  branch=$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null)

  display_status="false"
  added_icon=""
  modified_icon=""
  updated_icon=""
  deleted_icon=""
  repo_icon=""
  diff_icon=""
  no_repo_icon=""

  if [ -n "$branch" ]; then
    branch_fmt=$(printf '%.20s ' "$branch")
    git_status=$(git -C "$path" status -s 2>/dev/null)

    top_level=$(git -C "$path" rev-parse --show-toplevel 2>/dev/null)
    repo_name=$(basename "$top_level")
    remote_url=$(git -C "$path" remote get-url origin 2>/dev/null)
    repo_url=""
    if [ -n "$remote_url" ]; then
      case "$remote_url" in
        git@github.com:*) repo_url="https://github.com/${remote_url#git@github.com:}" ;;
        git@gitlab.com:*) repo_url="https://gitlab.com/${remote_url#git@gitlab.com:}" ;;
        git@bitbucket.org:*) repo_url="https://bitbucket.org/${remote_url#git@bitbucket.org:}" ;;
        http://*|https://*) repo_url="$remote_url" ;;
      esac
      repo_url=${repo_url%.git}
    fi

    if [ -n "$repo_url" ]; then
      repo_label="\033]8;;${repo_url}\a${repo_name}\033]8;;\a"
    else
      repo_label="$repo_name"
    fi

    branch_fmt="${repo_label} ${branch_fmt}"

    if [ -n "$git_status" ]; then
      while IFS= read -r line; do
        [ -z "$line" ] && continue

        x=${line:0:1}
        y=${line:1:1}

        if [ "$x" = "?" ] && [ "$y" = "?" ]; then
          added=$((added + 1))
          continue
        fi

        case "$x" in
          A) added=$((added + 1)) ;;
          M) modified=$((modified + 1)) ;;
          U) updated=$((updated + 1)) ;;
          D) deleted=$((deleted + 1)) ;;
        esac

        case "$y" in
          A) added=$((added + 1)) ;;
          M) modified=$((modified + 1)) ;;
          U) updated=$((updated + 1)) ;;
          D) deleted=$((deleted + 1)) ;;
        esac
      done <<< "$git_status"

      git_changes=""
      [ "$added" -gt 0 ] && git_changes+="${added} $(rgb 0 200 80)${added_icon}${RST} "
      [ "$modified" -gt 0 ] && git_changes+="${modified} $(rgb 220 200 0)${modified_icon}${RST} "
      [ "$updated" -gt 0 ] && git_changes+="${updated} $(rgb 100 180 255)${updated_icon}${RST} "
      [ "$deleted" -gt 0 ] && git_changes+="${deleted} $(rgb 220 40 20)${deleted_icon}${RST} "
      git_changes=${git_changes% }

      if [ "$display_status" = "false" ]; then
        if [ -n "$diff_icon" ]; then
          printf '%b' "$(rgb 220 200 0)${diff_icon}${RST} ${git_changes} $(rgb 163 230 53)${branch_fmt}${RST}"
        else
          printf '%b' "${git_changes} $(rgb 163 230 53)${branch_fmt}${RST}"
        fi
      else
        if [ -n "$diff_icon" ]; then
          printf '%b' "$(rgb 220 200 0)${diff_icon}${RST} $(rgb 163 230 53)${branch_fmt}${RST}"
        else
          printf '%b' "$(rgb 163 230 53)${branch_fmt}${RST}"
        fi
      fi
    else
      if [ -n "$repo_icon" ]; then
        printf '%b' "$(rgb 0 200 180)${repo_icon}${RST} $(rgb 163 230 53)${branch_fmt}${RST}"
      else
        printf '%b' "$(rgb 163 230 53)${branch_fmt}${RST}"
      fi
    fi
  else
    printf '%b' "$(rgb 120 120 120)${no_repo_icon}${RST}"
  fi
}

# ===== LINE 1: Model (hyperlink) / Effort / Context / Tokens / Token Speed =====
L1=""
L1+="$(rgb 236 72 153)🤖 ${BOLD}\033]8;;http://10.10.10.50:3458/\a${model_display}\033]8;;\a${RST}"

if [ -n "$effort_str" ]; then
  L1+="${SEP}${effort_str}"
fi

if [ -n "$agent_name" ]; then
  L1+="${SEP}$(rgb 163 230 53)🧩 ${agent_name}${RST}"
fi

L1+="${SEP}${ctx_part}"

L1+="${SEP}$(rgb 255 120 160)+↓$(rgb 140 210 255)$(fmt_tok "$((turn_in + cache_read + cache_create))")${RST} $(rgb 255 120 160)+↑$(rgb 255 190 140)$(fmt_tok "$turn_out")${RST}"
L1+="${SEP}$(rgb 120 230 160)↓$(rgb 100 180 255)$(fmt_tok "$((total_in + session_cache_read + session_cache_create))")${RST} $(rgb 120 230 160)↑$(rgb 255 160 100)$(fmt_tok "$total_out")${RST}"
L1+="${SEP}$(rgb 0 200 180)♻️ ${cache_eff_pct}%${RST}"

if [ -n "$burn_rate" ]; then
  L1+="${SEP}$(rgb 255 160 100)🔥 \$${burn_rate}/hr${RST}"
fi

if [ -n "$slot_text" ]; then
  L1+="${SEP}${slot_text}"
fi


# ===== LINE 2: Coding velocity + git =====
git_part=$(build_git_segment)
L2="$(rgb 0 200 80)+${lines_add}${RST} $(rgb 220 40 20)-${lines_del}${RST}${SEP}${git_part}"

if [ -n "$token_ttft" ]; then
  L2+="${SEP}$(rgb 0 200 180)⏱️ ${token_ttft}${RST}"
fi

if [ -n "$token_speed" ]; then
  L2+="${SEP}$(rgb 255 200 40)⚡$(rgb 0 200 180)${token_speed} t/s${RST}"
fi

L2+="${SEP}$(rgb 251 146 60)\033]8;;https://infer-runtime-broker.lan/\a 󰜎 \033]8;;\a${RST}"
L2+="$(rgb 217 119 87)\033]8;;https://claude.ai/new\a  \033]8;;\a${RST}"
L2+="$(rgb 116 209 178)\033]8;;https://chatgpt.com/\a  \033]8;;\a${RST}"
L2+="$(rgb 110 168 254)\033]8;;https://gemini.google.com/app\a  \033]8;;\a${RST}"
if [ -n "$rate_limit_parts" ]; then
  L2+="${SEP}${rate_limit_parts}"
fi

printf '%b\n' "$L1"
printf '%b\n' "$L2"
