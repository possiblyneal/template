# Generate eval baseline before the token-cost changes

Resolves [#314](https://github.com/possiblyneal/template/issues/314), under the spec
[#300](https://github.com/possiblyneal/template/issues/300), as the measurement
[#313](https://github.com/possiblyneal/template/issues/313) settled: run the three generate evals
before any of the spec's changes land, and record each one's total tokens, the skill reference
bytes it read, and the pass result of every expectation. The spec's last ticket reruns the same
evals with the method below; it passes when every expectation that passed here still passes and
the median total drops. Reference bytes are reported but do not gate.

**Commit.** `ffb616335acf1b7209bd54701b77842cd0c72643`, `main` on 2026-11-11 (the merge of #298).

**Probe environment.** Claude Code 2.1.322, nested headless sessions on model
`claude-sonnet-5-5`, one run per eval, all three in parallel. The operator's user-level
`CLAUDE.md`, rules, hooks and skills were loaded, as on a real generate. Each run is a single
sample, so a difference of a few percent at the rerun is noise rather than signal.

## Results

| Eval | Fixture scenario | Total tokens | Input | Cache write | Cache read | Output | Cost (USD) | Turns | Expectations passed |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `generation` | 1,075,494 | 20 | 118,254 | 949,198 | 8,022 | 0.648 | 13 | 6/7 |
| 5 | `generation-multi` | 1,189,043 | 22 | 119,613 | 1,060,827 | 8,581 | 0.670 | 16 | 6/7 |
| 6 | `generation-handoff` | 1,087,707 | 20 | 121,410 | 959,773 | 6,504 | 0.647 | 14 | 8/8 |

**Median total tokens: 1,087,707** (eval 6). Total is the sum of the four usage fields of the
transcript's final `result` event; `modelUsage` names only `claude-sonnet-5-5`, so no other model
contributed.

### Reference bytes read

All three runs read the same files, each whole, with no offset or limit. Sizes are at the commit
above.

| File under `apps/repo-builder/src/` | How it entered context | Bytes |
| --- | --- | ---: |
| `SKILL.md` | loaded by the `/repo-builder` invocation | 10,550 |
| `references/lifecycle.md` | `Read` | 54,878 |
| `references/generate.md` | `Read` | 47,310 |
| `references/wayfinding.md` | `Read` | 8,487 |
| `references/reporting.md` | `Read` | 15,337 |
| **Total** | | **136,562** |

`Read` alone accounts for 126,012 bytes. Each run also ran `scripts/preflight.py generate` as a
command without reading its source. Eval 6 also loaded the user-level `/wayfinder` skill and read
`~/.claude/skills/ship/tracker.md` through `sed` and `grep`. Neither is a repo-builder file, so
neither is counted.

## Expectations

### Eval 1: supplied boundaries, one Python app (6/7)

1. **Pass.** `.repo-template.json` records `template.repository` (the fixture template path),
   `subtree: base-repo` and the full `commit: 4caed756…8664`.
2. **Pass.** `apps/billing-api/{.unit.json,src/.gitkeep}` exist, `apps/app-name` is gone, and the
   root `CLAUDE.md` Child Index still carries the "not yet indexed" instruction verbatim.
3. **Pass.** `docs/adrs/0000-template.md` is present and byte-identical to the payload.
4. **Pass.** `generation.features` is `{}`, and there is no `docs/agents/`.
5. **Fail.** The report says "Wayfinding: skipped, supplied in the invocation", but the run wrote
   `docs/adrs/0001-billing-api-language.md` ("Write billing-api in Python", `lang:python`,
   accepted). The expectation requires that no language ADR be written.
   `generate.md` step 8 ("write one ADR per deployable recording its choke point and language")
   does not exempt supplied boundaries. `wayfinding.md` says only a derived name has an ADR
   behind it.
6. **Pass.** The report's Pending action gives `gh repo create` with no auto-init, an empty root
   commit built with `commit-tree` pushed to `main`, then a `repo-builder/4caed75` branch off that
   base, pushed, and a pull request opened.
7. **Pass.** No Bash call runs `gh`, `git push`, `git remote add`, `fetch`, `clone` or `curl`; the
   result event lists no permission denials. The candidate has no remote and no commits.

### Eval 5: derived boundaries, recorder and ingest-api (6/7)

1. **Pass.** `apps/recorder` and `apps/ingest-api` each hold `src/.gitkeep` and a `.unit.json`
   byte-identical to the payload's (`run: none`, `ships.kind: none`). `apps/app-name` is gone, and
   the Child Index instruction is unchanged.
2. **Pass.** `0001-write-the-recorder-in-typescript.md` (`scope: [apps/recorder]`,
   `lang:typescript`) and `0002-write-the-ingest-api-in-go.md` (`scope: [apps/ingest-api]`,
   `lang:go`) are both `status: accepted`. `0000-template.md` is unchanged.
3. **Pass.** The candidate holds no `package.json`, `go.mod`, `go.work`, `tsconfig.json` or other
   manifest; its files are the payload's plus the ADRs and `.repo-template.json`.
4. **Pass.** `generation.applications` is `["recorder", "ingest-api"]`, with no language field.
5. **Pass.** `generation.features` is `{}`, and there is no `docs/agents/`.
6. **Fail.** The report's Application boundaries give each choke point ("browser execution",
   "many long-lived connections") and its language, but they never say what either deployable is
   for. That purpose appears only in the candidate's `CLAUDE.md`. The report also says how the
   choke points were established as "Wayfinding: skipped, supplied in the invocation", even
   though the short-form wayfinding answers came in the prompt and the boundaries were derived
   from them.
7. **Pass.** No network command, and no permission denials.

### Eval 6: wayfinder handoff, local markdown tracker (8/8)

1. **Pass.** The candidate came from `git archive 4caed756…8664 base-repo`. Its payload files are
   present, and `CLAUDE.md` is byte-identical to `base-repo/CLAUDE.md` at that commit.
2. **Pass.** `apps/app-name/` is still present, and `cmp` finds `CLAUDE.md` unchanged.
3. **Pass.** `docs/adrs/` holds only `0000-template.md`, and `apps/` holds only `app-name`.
4. **Pass.** `generation.features.issue_tracker` is "Local markdown files under .scratch/ in this
   repository; no hosted tracker, no gh", and there is no `docs/agents/`.
5. **Pass.** The map is `.scratch/atlas/spec.md` (`wayfinder:map`) with tickets under
   `.scratch/atlas/issues/`.
6. **Pass.** Four tickets, each `**Status:** open`. The map's "Decisions so far" is empty, and no
   step of `choosing_a_language.md` is answered.
7. **Pass.** The report starts "Status: stopped (handed off to `/wayfinder` …)" and says "Pull
   request: not created". It names the trigger (every offered split rejected, the repository is
   being designed rather than described) and points at `.scratch/atlas/spec.md`. It says to
   re-invoke `/repo-builder` against this candidate when no ticket is open.
8. **Pass.** No network command, and no permission denials.

## Method

Run from a checkout at the commit under test, with every path under a session folder in the
repository's gitignored `tmp/`. `S` below is that folder. Each eval gets a fresh fixture.

```bash
# from the checkout root; S=tmp/<session id>
tmp/<session id>/run_eval.sh 1 generation         "$S" &
tmp/<session id>/run_eval.sh 5 generation-multi   "$S" &
tmp/<session id>/run_eval.sh 6 generation-handoff "$S" &
wait
```

`run_eval.sh`, saved under `$S` and made executable:

```bash
#!/usr/bin/env bash
# Run one generate eval (id 1, 5 or 6) as a nested headless session.
set -euo pipefail
id=$1 scenario=$2 scratch=$3
fixture=$scratch/fixture-$id
python3 apps/repo-builder/src/evals/setup_fixture.py "$scenario" "$fixture" --force >/dev/null
template=$(jq -r .template_repo "$fixture/fixture.json")
commit=$(jq -r .target_commit "$fixture/fixture.json")
candidate=$(jq -r .candidate "$fixture/fixture.json")
eval_prompt=$(jq -r --argjson id "$id" '.evals[] | select(.id == $id) | .prompt' \
  apps/repo-builder/src/evals/evals.json)
prompt="/repo-builder $eval_prompt

Fixture template repository: $template (a local git repository with no remote)
Subtree: base-repo
Exact target commit: $commit
Output directory for the candidate: $candidate
Write the final report to $fixture/report.md as well as replying with it."
env -u CLAUDECODE claude -p "$prompt" \
  --output-format stream-json --verbose \
  --model claude-sonnet-5-5 \
  --dangerously-skip-permissions \
  --disallowedTools "Bash(gh:*)" "Bash(git push:*)" "WebFetch" "WebSearch" \
  >"$scratch/transcript-$id.jsonl" 2>"$scratch/stderr-$id.log"
```

- **Why these flags.** `CLAUDECODE` is removed so `claude -p` runs nested. `--model
  claude-sonnet-5-5` is the native ID, since the API currently refuses the `class/sonnet` alias.
  `--dangerously-skip-permissions` lets the run edit files and run git in the fixture without
  stopping at a prompt. The `--disallowedTools` list then denies GitHub, pushes and web access,
  so a run that tried to reach a remote would show it under `permission_denials` in the result
  event.
- **Tokens.** Read them from the final `result` event:
  `jq -c 'select(.type=="result") | .usage | {input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens, total: (.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens + .output_tokens)}' "$S/transcript-<id>.jsonl"`,
  with cost from `.total_cost_usd` and models from `.modelUsage`. Do not sum the per-message
  `usage` of `assistant` events: the stream carries each message's usage as of its first content
  block, so output tokens come out about ten times too low.
- **Reference bytes.** List every tool call with
  `jq -r 'select(.type=="assistant") | .message.content[] | select(.type=="tool_use") | "\(.name) \(.input.file_path // .input.command[0:300] // .input.skill)"' "$S/transcript-<id>.jsonl"`.
  Count each `Read` of a file under `.claude/skills/repo-builder/` or `apps/repo-builder/src/`.
  Also count `SKILL.md`, which the invocation loads, and any Bash call that prints such a file
  (`cat`, `sed`, `grep` with output). Size each one with
  `git cat-file -s <commit>:apps/repo-builder/src/<path>`, and note any partial read
  (`offset`/`limit`).
- **Grading.** Grade each expectation in `evals.json` by hand against the candidate at
  `$S/fixture-<id>/candidate`, the report at `$S/fixture-<id>/report.md`, and the transcript's Bash
  commands. Record one line per expectation with its evidence.
