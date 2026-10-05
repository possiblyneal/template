# Retrofit report

Part of [Retrofit](retrofit.md), read once the flow ends or stops.

## Report additions

**Run the renderer, then fill its slots.** It writes the [Final report](reporting.md#final-report) shape, reading every count, setting, hosted write and reverse command, check result and cleanup outcome from the records at `<records>`:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py report \
  --repository <owner>/<repository> --records <records> \
  [--pull-request <URL>] [--stopped "<what remains>"] [--resumed]
```

`--repository` is `<owner>/<repository>`, or the origin path where origin is one. It requires the proofs record and `<records>.check.txt` and reads every other record that exists; an absent record renders as the fact that its subcommand did not run (`unknown (hosted read did not run)`), never as a blank or a slot. It writes `<records>.report.md` and reports `path` and `slots`, the judgement lines left as `[[FILL: <what goes here>]]`. Fill every slot from this run's decisions, delete optional slots that do not apply, and change no rendered line; a wrong rendered line is a defect in its record. The finished report holds no `[[FILL:`.

## Judgement slots

Every slot left after the renderer runs is one no record can fill, for the reason beside it. A value a record holds is rendered, and a defect in that line is fixed in the record's subcommand.

- Reconciliation, **Conflicted** (intents each merge settled), **Superseded**, **Partially covered, not cut**: the reading of what a file did and what carries it now is the flow's, and the proofs record holds paths and classes, never intent.
- **Layout plan** (corrections and declines), **Unmovable**, **Data split**, **Ignore rules the payload does not cover**: each is the operator's answer to a question the flow asked, and no subcommand records an answer.
- **References repaired**, **References reported, not rewritten**: the rewrite is an edit the flow made by hand, and no record lists it.
- Application boundaries, **ADR fields defaulted**, **Unit map**, **Ships nothing for want of an adapter**, **Declared but not built**: the evidence behind each is read from the destination's files by the flow, and the proofs record holds only the ADR paths written.
- **Issue tracker**'s tracker: it is named inside `docs/agents/issue-tracker.md`, a file's content rather than a record.
- Labels **reason none were created**, and Hosted writes, reversible, the **declined** line: the reason a write was not approved is the operator's, and `hosted apply` records only the writes it was asked to make.
- Hosted writes, irreversible, **each irreversible write**: the cost of having made it is a judgement over the write.
- **Ruleset enforcement** and **Default branch after merge**: step 9 reads the host after the report's records are written, and no subcommand records that reading.
- **Code review**: the axes run and the findings corrected are the review's own account, and the sign-off sits in a pull-request comment.
- **Untracked at the bar**, **Tool declaration**, **Configuration boundary**, **Autofix settings resolution**: each describes what the flow wrote into or read from the candidate at step 7, which no record captures.
- **Autofix**'s commit sha, and the rule or formatter behind a **reverted** payload path: the flow makes the commit after the autofix record is written, and the record lists the path without the rule.
- **Destination fix prepared** and **published** (unmet bar only), **Left for the operator**'s other paths, **Pending action**: each reports a decision made or awaited.
- **Resumption**: what live state showed, what was read back, redone and retried are the resumed run's own observations.

The renderer adds a **References not repaired** section after Cleanup, one line per hit left in `<records>.references.json` with its suggested replacement, or `none`. It has no slot.

Three lines differ from the shape:

- **Code review** is never `skipped`: it carries the axes step 7's scan ran, the findings corrected, any recorded as incorrectly identified, and the `Reviewed-Head:` sha step 9 signed off, or that no sign-off was written and why.
- The renderer omits the choke-point and Wayfinding lines; a retrofit chooses neither.
- A unit map the operator rejected without a correction is reported as the proposal and the rejection, with **Pending action** carrying the correction the flow is stopped for.

## Slot shapes

Under **Reconciliation**:

- Layout plan: <old path> -> <new path>: corrected by the operator to <path> | declined
- Unmovable: <path>: <why it could not move>; no allowlist entry written | none
- Data split: <file>: read, to `assets/` | written, to `state/`, and the operator copies their live file there and restores the old path before pulling the merge | written, to `state/`, with its finished record snapshotted to `assets/` and a fallback the operator confirmed, and the operator copies their live file there and restores the old path before pulling the merge | none
- References repaired: <file>: <the moved path rewritten> | none
- References reported, not rewritten: <file>: <the prose describing the old structure> | none
- Ignore rules the payload does not cover: <rule>: <what it ignored>, reported and not re-added | restored by the operator (<reason>), so the ignore file is authored and no override entry is recorded | none

Under **Application boundaries**:

- ADR fields defaulted: <ADR path>: <field> set to the payload template's <value>, no evidence in the ADR | none
- Unit map: <unit>: name from <the source it came from>, built by <evidence>, installed by <evidence>; run <value> and ships <value>, each <proposed from <evidence>, confirmed | corrected by the operator>; domains <names and the boundary the destination draws for each, or none>
- Ships nothing for want of an adapter: <unit>: <language> has no packaging adapter | none
- Declared but not built: <deployable>: declared by <the descriptor naming it>, filed under <the owning unit> | none

Under **Verification**:

- Untracked at the bar: none | <paths>: <the ignore rule step 6 replaced>, disposed by <the operator's decision> | <paths>: generated output, the payload ships no `.gitignore`, removed
- Tool declaration: <manifest>: added <tool at the template's floor> | kept <the specifier the destination already declared> | declined by the operator, so <capability> cannot reach the bar | nothing missing
- Configuration boundary: one row per language — <manifest> carries <the boundary the list names> | already declared by the destination, kept | the list names none for <language>, whose tools walk upward
- Autofix settings resolution: every tool resolved inside the candidate | SKIPPED: <tool> resolved `<path>`, outside the candidate — or no settings path could be read for <tool> — so no pass ran and the bar was measured under those settings
- Destination fix prepared (unmet bar only): branch <name> in <clone>, <commit> clearing <rule> at <paths>, worktree removed; <the rule count before and after under the candidate's target version>, read <by flag | in the candidate, revert verified clean>, <the harness delta | no harness exists in the destination> | partly prepared: <the same>, and left outstanding: <file and rule for each>, because <what the second reading still showed | the path exists only in the candidate> | nothing to prepare: <the capability was unavailable rather than failing> | nothing prepared: <tool> resolved `<path>`, outside the fix worktree — or no path could be read for it — so every finding is left outstanding, worktree removed | declined by the operator, so no worktree or branch was prepared
- Destination fix published (unmet bar only): push and pull request offered and awaiting the gate | authorized and performed, at <URL>, merged at <sha> and the run resumed | authorized and performed, at <URL>, left open because <what kept it from merging> | declined or never answered, branch left local | not reached, because nothing was prepared or the operator declined the fix

Under **Hosted writes, irreversible**:

- <write>: was <before-state> -> <applied value>; no command reverses it, and <the cost of having made it>
- Ruleset enforcement: <step 9's `mergeable`/`mergeStateStatus` reading of the pull request> | not yet proven at the gate, and no pull request opened to prove it | n/a (no ruleset written)
