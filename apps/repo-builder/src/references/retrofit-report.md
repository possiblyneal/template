# Retrofit report

Part of [Retrofit](retrofit.md), read once the flow ends or stops.

## Report additions

**Run the renderer, then fill its slots.** It writes the [Final report](reporting.md#final-report) shape, reading every count, setting, hosted write and reverse command, check result and cleanup outcome from the records at `<records>`:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py report \
  --repository <owner>/<repository> --records <records> \
  [--pull-request <URL>] [--stopped "<what remains>"] [--resumed]
```

`--repository` is `<owner>/<repository>`, or the origin path where origin is one. It requires the proofs record and `<records>.check.txt` and reads every other record that exists; an absent record renders as the fact that its subcommand did not run (`unknown (hosted read did not run)`), never as a blank or a slot. It writes `<records>.report.md` and reports `path` and `slots`, the judgement lines left as `[[FILL: <key>: <what goes here>]]`.

**Fill a slot by recording the decision, never by editing the markdown**, then render again:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py decide --records <records> \
  --key <key> --value "<the line's text>"
```

`decide` merges each call into `<records>.decisions.json`, which survives the sweep though not a `resume`, and both `report` and `pr-body` read it, so a judgement the two share (`unit-map`, `merged`, `conflicted`, `summary`) is recorded once. Record each where the flow makes it rather than all at the end. Deciding `none` drops an optional line (`layout-corrections`, `declined-writes`, and `left-for-the-operator` beside rendered entries). Change no rendered line: a record's value outranks a decision, so a decision on a key a record fills applies only where the record leaves it a slot, and a wrong rendered line is a defect in its record. The finished report holds no `[[FILL:`.

## Judgement slots

Every slot left after the renderer runs is one no record can fill, for the reason beside it, and its key is the one `decide --key` takes. A value a record holds is rendered, and a defect in that line is fixed in the record's subcommand. `conflicted`, `superseded`, `partially-covered`, `unmovable`, `untracked` and `retries` render `none` until decided otherwise.

- Reconciliation, `merged` (the payload change and destination text each merged path carries; the paths themselves are rendered), `conflicted`, `superseded`, `partially-covered`: the reading of what a file did and what carries it now is the flow's, and the proofs record holds paths and classes, never intent.
- `layout-corrections`, `unmovable`, `data-split`, `ignore-rules`: each is the operator's answer to a question the flow asked.
- `references-repaired`: the rewrite is an edit the flow made by hand, and the references record is rewritten after it, so it holds only what remains.
- Application boundaries, `adr-fields-defaulted`, `unit-map`, `declared-not-built`: the evidence behind each is read from the destination's files by the flow, and the proofs record holds only the ADR paths written. `ships-nothing` renders from the facts record: a unit shipping `none` beside a manifest no packaging adapter reads.
- `issue-tracker` renders from the proofs record, which reads the heading of `docs/agents/issue-tracker.md`; it is a slot only where that first heading names no tracker after `Issue tracker:`.
- `labels-reason` and `declined-writes`: the reason a write was not approved is the operator's, and `hosted apply` records only the writes it was asked to make.
- `irreversible-writes`: the cost of having made it is a judgement over the write.
- `ruleset-enforcement` and `default-branch`: step 9 reads the host after the report's records are written.
- `code-review`: the axes run and the findings corrected are the review's own account, and the sign-off sits in a pull-request comment.
- `untracked`, `autofix-settings`: each describes what the flow read from the candidate at step 7, which no record captures. **Tool declaration** renders from the proofs record's `manifests`, each manifest's added, changed and removed keys, and is the `tool-declaration` slot only where a manifest has no parser. **Configuration boundary** renders from its `configuration`, one row for the root and one per declared unit.
- `reverted-rules`: the autofix record lists the reverted path without the rule. The autofix commit sha renders from the facts record, which finds the commit by its exact subject on the candidate's first-parent line; it is the `autofix-commit` slot only where no commit carries it.
- `fix-prepared` and `fix-published` (unmet bar only), `left-for-the-operator`, `pending-action`: each reports a decision made or awaited.
- Resumption, `re-observed`, `read-back`, `redone`, `retries`: the resumed run's own observations.

Three lines differ from the shape:

- **Code review** is never `skipped`: it carries the axes step 7's scan ran, the findings corrected, any recorded as incorrectly identified, and the `Reviewed-Head:` sha step 9 signed off, or that no sign-off was written and why.
- The renderer omits the choke-point and Wayfinding lines; a retrofit chooses neither.
- A unit map the operator rejected without a correction is reported as the proposal and the rejection, with **Pending action** carrying the correction the flow is stopped for.

## Slot shapes

Under **Reconciliation**:

- Layout plan: <old path> -> <new path>: corrected by the operator to <path> | declined
- Unmovable: <path>: <why it could not move>; no allowlist entry written | none
- Data split: <file>: read, to `assets/` | written, to `state/` | written, to `state/`, with its finished record snapshotted to `assets/` and a fallback the operator confirmed | none. A written file adds where its live file went: carried there and the old path restored before the clone pulled, or, where the merge was declined, left for the operator to copy there and restore the old path before pulling
- References repaired: <file>: <the moved path rewritten> | none
- Ignore rules the payload does not cover: <rule>: <what it ignored>, reported and not re-added | restored by the operator (<reason>), so the ignore file is authored and no override entry is recorded | none

Under **Application boundaries**:

- ADR fields defaulted: <ADR path>: <field> set to the payload template's <value>, no evidence in the ADR | none
- Unit map: <unit>: name from <the source it came from>, built by <evidence>, installed by <evidence>; run <value> and ships <value>, each <proposed from <evidence>, confirmed | corrected by the operator>; domains <names and the boundary the destination draws for each, or none>
- Ships nothing for want of an adapter: <unit>: <language> has no packaging adapter | none
- Declared but not built: <deployable>: declared by <the descriptor naming it>, filed under <the owning unit> | none

Under **Verification**:

- Untracked at the bar: none | <paths>: <the ignore rule step 6 replaced>, disposed by <the operator's decision> | <paths>: generated output, the payload ships no `.gitignore`, removed
- Tool declaration, where it is a slot: <manifest>: added <tool at the template's floor> | kept <the specifier the destination already declared> | declined by the operator, so <capability> cannot reach the bar | nothing missing
- Configuration boundary, where it is a slot: one row per language — <manifest> carries <the boundary the list names> | already declared by the destination, kept | the list names none for <language>, whose tools walk upward
- Autofix settings resolution: every tool resolved inside the candidate | SKIPPED: <tool> resolved `<path>`, outside the candidate — or no settings path could be read for <tool> — so no pass ran and the bar was measured under those settings
- Destination fix prepared (unmet bar only): branch <name> in <clone>, <commit> clearing <rule> at <paths>, worktree removed; <the rule count before and after under the candidate's target version>, read <by flag | in the candidate, revert verified clean>, <the harness delta | no harness exists in the destination> | partly prepared: <the same>, and left outstanding: <file and rule for each>, because <what the second reading still showed | the path exists only in the candidate> | nothing to prepare: <the capability was unavailable rather than failing> | nothing prepared: <tool> resolved `<path>`, outside the fix worktree — or no path could be read for it — so every finding is left outstanding, worktree removed | declined by the operator, so no worktree or branch was prepared
- Destination fix published (unmet bar only): push and pull request offered and awaiting the gate | authorized and performed, at <URL>, merged at <sha> and the run resumed | authorized and performed, at <URL>, left open because <what kept it from merging> | declined or never answered, branch left local | not reached, because nothing was prepared or the operator declined the fix

Under **Hosted writes, irreversible**:

- <write>: was <before-state> -> <applied value>; no command reverses it, and <the cost of having made it>
- Ruleset enforcement: <step 9's `mergeable`/`mergeStateStatus` reading of the pull request> | not yet proven at the gate, and no pull request opened to prove it | n/a (no ruleset written)
