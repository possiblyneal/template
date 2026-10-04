# Retrofit report

Part of [Retrofit](retrofit.md), read once the flow ends or stops.

## Report additions

**Run the renderer, then fill its slots.** It writes the shape [Final report](reporting.md#final-report) fixes, with every count, setting, hosted write and reverse command, check result and cleanup outcome read from the records at `<records>`:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py report \
  --repository <owner>/<repository> --records <records> \
  [--pull-request <URL>] [--stopped "<what remains>"] [--resumed]
```

It requires the proofs record and `<records>.check.txt`, and reads every other record that exists; a record that is absent is a subcommand that did not run, rendered as such. It writes `<records>.report.md` and reports `path` and `slots`: the judgement lines left as `[[FILL: <what goes here>]]`. Fill every slot from what this run decided, delete the ones marked optional that do not apply, and change no rendered line; a rendered line that reads wrong is a defect in the record it came from. The finished report holds no `[[FILL:`.

Three of the shape's lines read differently here. **Code review** is never `skipped`: it carries the axes step 7's scan ran, the findings corrected, any recorded as incorrectly identified, and the `Reviewed-Head:` sha step 9 signed off, or that no sign-off was written and why. The renderer leaves out the choke-point and Wayfinding lines, since a retrofit chooses neither. A unit map the operator rejected with no correction is reported as the proposal and the rejection, with **Pending action** carrying the correction the flow is stopped for.

## Slot shapes

Under **Reconciliation**:

- Layout plan: <old path> -> <new path>: corrected by the operator to <path> | declined
- Unmovable: <path>: <why it could not move>; no allowlist entry written | none
- Data split: <file>: read, to `assets/` | written, to `state/`, and the operator copies their live file there and restores the old path before pulling the merge | written, to `state/`, with its finished record snapshotted to `assets/` and a fallback the operator confirmed, and the operator copies their live file there and restores the old path before pulling the merge | none
- References repaired: <file>: <the moved path rewritten> | none
- References reported, not rewritten: <file>: <the prose describing the old structure> | none
- Ignore rules the payload does not cover: <rule>: <what it ignored>, reported and not re-added | restored by the operator (<reason>), so the ignore file is authored and no override entry is recorded | none

Under **Application boundaries**:

- Unit map: <unit>: name from <the source it came from>, built by <evidence>, installed by <evidence>; run <value> and ships <value>, each <proposed from <evidence>, confirmed | corrected by the operator>; domains <names and the boundary the destination draws for each, or none>
- Ships nothing for want of an adapter: <unit>: <language> has no packaging adapter | none
- Declared but not built: <deployable>: declared by <the descriptor naming it>, filed under <the owning unit> | none

Under **Verification**:

- Untracked at the bar: none | <paths>: <the ignore rule step 6 replaced>, disposed by <the operator's decision>
- Tool declaration: <manifest>: added <tool at the template's floor> | kept <the specifier the destination already declared> | declined by the operator, so <capability> cannot reach the bar | nothing missing
- Configuration boundary: one row per language — <manifest> carries <the boundary the list names> | already declared by the destination, kept | the list names none for <language>, whose tools walk upward
- Autofix settings resolution: every tool resolved inside the candidate | SKIPPED: <tool> resolved `<path>`, outside the candidate — or no settings path could be read for <tool> — so no pass ran and the bar was measured under those settings
- Destination fix prepared (unmet bar only): branch <name> in <clone>, <commit> clearing <rule> at <paths>, worktree removed; <the rule count before and after under the candidate's target version>, read <by flag | in the candidate, revert verified clean>, <the harness delta | no harness exists in the destination> | partly prepared: <the same>, and left outstanding: <file and rule for each>, because <what the second reading still showed | the path exists only in the candidate> | nothing to prepare: <the capability was unavailable rather than failing> | nothing prepared: <tool> resolved `<path>`, outside the fix worktree — or no path could be read for it — so every finding is left outstanding, worktree removed
- Destination fix published (unmet bar only): push and pull request offered and awaiting the gate | authorized and performed, at <URL> | declined or never answered, branch left local | not reached, because nothing was prepared

Under **Hosted writes, irreversible**:

- <write>: was <before-state> -> <applied value>; no command reverses it, and <the cost of having made it>
- Ruleset enforcement: <step 9's `mergeable`/`mergeStateStatus` reading of the pull request> | not yet proven at the gate, and no pull request opened to prove it | n/a (no ruleset written)
