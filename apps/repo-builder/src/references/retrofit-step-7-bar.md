# Step 7 — Dispose the collisions, write both records, meet the bar

Part of [Retrofit](retrofit.md). Nothing here reaches the network. In order: the collisions, the two records, the tool declaration, normalization and the proofs, the autofix pass, the bar, the declared facts, and the review.

## The records and the collisions

**Two records are written here**, together, because both wait on step 6's moves: the decomposition architecture record, whose content [What the decomposition record will say](retrofit-step-5-units.md#what-the-decomposition-record-will-say) decided, and then the manifest.

**Write the decomposition record first, at the root documentation path**, under [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path). It carries the confirmed unit map: each unit's name and its source, the evidence for each half of the delivery test, the run and ship pair with its evidence and whether it was observed or accepted, the domains and their boundaries, the choke point observed per unit with *none of these bind* where none does, and every declared-but-not-built deployable. **Every path inside it is repository-relative**, since it sits at the root and covers every unit.

**Every remaining collision is proposed and disposed, per file.** Diff the destination's version against the payload's, state what each says, and let the operator pick payload, destination, or a merge. A disposition the payload wins writes the payload's mode too, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). No path-matching rule stands in for this.

**Where this run invalidated the destination's own stated reason, propose the payload's version and name the step that invalidated it**, so the operator can refuse it on the merits.

**A chosen destination version at a managed path is an [overridden path](lifecycle.md#overridden-paths)**, recorded with the reason it won. One that wins at a product path is already the destination's: report it with its reason and record nothing.

The ownership array is the payload's default. **A destination path still matching a managed pattern is a layout failure to fix in step 6**, never an ownership exception written here.

**The record carries no field naming the flow, no list of layout moves, no run or ship facts beside the unit names, and no destination-specific ownership entry**, because a field an update can read is a field it can branch on.

## The tool declaration and dependabot

**The tool declaration adds only what is missing**, at the template's floors, keeping any specifier the destination already declares. [Tools the first manifest must declare](lifecycle.md#tools-the-first-manifest-must-declare) is the list per language: tool lines and the configuration boundaries it names, and nothing else — making moved code build or import is step 6's repair. A destination that already declares its own settings keeps them. The file is product-owned, not an overridden path. Report each line added. Keep the lockfiles step 4 produced. Retire a rival tool only where another fills its exact role, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script). The operator may decline the declaration, and the report then says which capability the bar cannot reach.

**`.github/dependabot.yml` gains every entry the destination earns**, under [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present), derived here because step 6 settled where the manifests sit.

**Check what this step and step 6 wrote against this list before the bar runs:**

- The decomposition record carries `scope: [global]`, an `## Alternatives Considered` section covering the run fact, the ship fact and the unit split the operator rejected, and one statement per fact of where it came from: observed, forced by the check surface, or confirmed by the operator.
- Each rationale this flow writes has one home, the unit's `CLAUDE.md`; the root `CLAUDE.md` and the root manifest point to it.
- A table of the destination's harnesses quotes each harness's literal summary line.
- A manifest comment says what its setting does, never how the retrofit arrived at it.

## Normalize, prove, commit

**The candidate carries no untracked file when the bar is measured.** Read `git status --porcelain` for `??` entries *before* staging, since staging turns them into `A` and the one reading that names them is gone. The usual cause is step 6's ignore-file replacement; dispose it under that step's ignore rule.

Then stage everything, normalize it, and measure both proofs, from this repository:

```bash
git -C <candidate> add -A
python3 apps/repo-builder/src/scripts/retrofit.py normalize \
  --candidate <candidate> --records <records>
python3 apps/repo-builder/src/scripts/retrofit.py proofs --template-repo . \
  --target "<commit>" --subtree apps/github-repository-template/src/base-repo \
  --candidate "<candidate>" --base "<base-commit>" --records <records>
```

`normalize` runs `git add --renormalize`, clears the executable bit from staged files that do not start with `#!`, and runs the configuration's whitespace, end-of-file, line-ending and `adr-index` hooks over the staged paths, re-staging what they rewrite. It reports `renormalized`, `executable_cleared`, `rewritten` and `still_failing`; a `still_failing` entry is fixed by hand before the proofs.

`proofs` measures from the index, so it runs while nothing is committed. It records `copy` (with `differing` and `missing`), `rename_purity`, `authored`, `deleted`, `applied`, `preserved`, `payload_total`, `overridden`, `emptied` and `workflows_without_pull_request`. A move edited past git's rename threshold appears as a deletion plus an `authored` path. It refuses an empty index and a candidate already past `<base-commit>`.

**Commit everything this flow wrote**, with the message in a file beside the candidate and `git commit -F <file>`: a message passed by process substitution has landed empty.

## The autofix pass

**The destination's own autofix runs before the bar, and nothing else does**, bounded to what its tools do unattended and committed alone; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why. No finding is fixed by hand here.

**First check each tool resolves its configuration inside the candidate.** The candidate sits under this repository's `tmp/`, so a tool that walks upward finds *this* repository's settings. Read each language's resolved settings path — `ruff check --show-settings .` prints it as `Settings path:` — and treat a path that cannot be read as outside. Where any tool fails, skip the pass, report the tool and the path, and measure the bar as it stood, saying which settings it was measured under.

```bash
python3 apps/repo-builder/src/scripts/retrofit.py autofix --candidate <candidate> \
  --template-repo . --target "<commit>" \
  --subtree apps/github-repository-template/src/base-repo --records <records>
```

It refuses uncommitted tracked changes, runs `scripts/fix` at most twice while a pass still changes something, and restores every path it rewrote that was a byte-identical payload copy, listing it under `reverted` as a payload defect to report. It reports `shipped`, `passes`, `exit_status`, `rewritten` and `reverted`. **Its exit status is not the bar.** Where `shipped` is false, the bar is measured without a pass. Then commit the pass alone, the same way.

The formatter is the part that costs something. Where the destination's test capability collects anything, report its result on both sides of the pass; where it collects nothing, say so.

## The bar

**The bar is the destination's own check surface passing on the candidate**, read by [Running the destination's checks](lifecycle.md#running-the-destinations-checks). `FAIL` and `unavailable` block; `not-applicable` does not. Stage before every run, re-runs included, since `scripts/structure` enumerates the index:

```bash
git -C <candidate> add -A
(cd <candidate> && scripts/summarize scripts/check) > <records>.check.txt
```

**Then execute the facts step 5 confirmed:**

```bash
python3 apps/repo-builder/src/scripts/retrofit.py facts --candidate <candidate> --records <records>
```

Per unit it runs `scripts/package <unit>` for real and `scripts/run <unit>` under `CI_DRY_RUN`, and flags either one that printed `No project manifest found` as doing nothing, since both exit zero there. Neither command is in the check surface, so a declaration that contradicts the tree passes the bar and fails the first time somebody uses it. A failure is a wrong fact or a missing descriptor: fix it, and re-read it with the operator where the fix changes a fact they confirmed.

**An unmet bar is a failed retrofit and it stops before the pull request**, naming the capability that could not pass and why. The fix does not ride along in the candidate. **The rest of that path is in [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md)**; a run that meets the bar never reads it.

## The review

**A met bar is followed by the review of the authored surface, before step 8 asks anything**; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why it runs here. Run the `/code-review` skill's `standard` scan — Standards, Spec, and Correctness/Logic — over the local candidate branch against the fixed point `origin/<default-branch>` at the commit step 2 fetched, the base the pull request will diff against. Scope it to the proofs record's `authored` and `deleted` paths, every `rename_purity` move that is not byte-identical, and the copy proof's `differing` paths, which together are [the retrofit's authored surface](reporting.md#reviewing-the-pull-request); the autofix commit is off it. Include a grep of the destination for every `deleted` path and each move's `from`, because a live reference in destination-owned prose is what no check reads.

Commit the corrections as their own commit, then stage and run the bar again over that head; repeat until every finding is corrected or recorded as incorrectly identified. Step 8's question is asked about this head, and step 9 publishes it unchanged.
