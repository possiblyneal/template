# Step 7 — Dispose the collisions, write both records, meet the bar

Part of [Retrofit](retrofit.md). Nothing here reaches the network. In order: the two records, the unit declarations, the remaining collisions, the instruction file, the tool declaration, normalization and the proofs, the autofix pass, the bar, the declared facts, and the review.

## The records and the collisions

**Write two records here, together, since both wait on step 6's moves:** the decomposition architecture record (content decided in [What the decomposition record will say](retrofit-step-5-units.md#what-the-decomposition-record-will-say)), then the manifest.

**Write the decomposition record first, at the root documentation path**, under [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path). It carries the confirmed unit map:

- each unit's name and source
- the evidence for each half of the delivery test
- the run and ship pair, its evidence, and whether it was observed or accepted
- the domains and their boundaries
- the choke point observed per unit, or *none of these bind*
- every declared-but-not-built deployable

**Every path inside it is repository-relative**, since it sits at the root and covers every unit.

**Then write each unit's `.unit.json`** at the unit root, from the pair step 5 confirmed, with `ships.targets` only where the kind is `executable`. Nothing earlier writes it, and `scripts/structure`'s `unit-declaration` cannot pass without it.

**Then propose and dispose every remaining collision, per file**, `CLAUDE.md` included. Diff the destination's version against the payload's, state what each says, and let the operator pick payload, destination, or a merge. No path-matching rule stands in for this. A disposition the payload wins writes the payload's mode too, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content).

**Where this run invalidated the destination's stated reason, propose the payload's version and name the step that invalidated it**, so the operator can refuse it on the merits.

**A destination version chosen at a managed path is an [overridden path](lifecycle.md#overridden-paths)**, recorded with the reason it won. One that wins at a product path is already the destination's: report it with its reason and record nothing.

**Then write the `CLAUDE.md` the disposition chose**, merged where it chose a merge, so it describes the whole run and the bar measures it. It is written before the bar and after its collision is disposed.

The ownership array is the payload's default. **A destination path still matching a managed pattern is a layout failure to fix in step 6**, never an ownership exception written here.

**The record carries no field naming the flow, no list of layout moves, no run or ship facts beside the unit names, and no destination-specific ownership entry**: an update could branch on any field it can read.

## The tool declaration and dependabot

**The tool declaration adds only what is missing**, at the template's floors, keeping any specifier the destination already declares and any settings it already has. [Tools the first manifest must declare](lifecycle.md#tools-the-first-manifest-must-declare) is the per-language list: tool lines and the configuration boundaries it names, nothing else; making moved code build or import is step 6's repair. The language adapter wins where it differs: write the line it reads (for instance `test = "unittest"`) in the root manifest, where the adapter's own pattern finds it, instead of the list's tools.

- The file is product-owned, not an overridden path.
- Report each line added.
- Keep the lockfiles step 4 produced.
- Retire a rival tool only where another fills its exact role, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script).
- The operator may decline the declaration; the report then says which capability the bar cannot reach.

**`.github/dependabot.yml` gains every entry the destination earns**, under [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present), derived here because step 6 settled where the manifests sit.

**Before the bar runs, check what this step and step 6 wrote against this list:**

- The decomposition record carries `scope: [global]`, an `## Alternatives Considered` section covering the run fact, the ship fact and the unit split the operator rejected, and one statement per fact of its source: observed, forced by the check surface, or confirmed by the operator.
- Each rationale this flow writes has one home, the unit's `CLAUDE.md`; the root `CLAUDE.md` and the root manifest point to it.
- A table of the destination's harnesses quotes each harness's literal summary line.
- A manifest comment says what its setting does, never how the retrofit arrived at it.

## Normalize, prove, commit

**The candidate carries no untracked file when the bar is measured.** Read `git status --porcelain` for `??` entries *before* staging, since staging turns them into `A`. The usual cause is step 6's ignore-file replacement; dispose it under that step's ignore rule. Where the payload ships no `.gitignore`, generated output such as `__pycache__` is the cause: never stage it. Removal alone does not stop a re-run regenerating it, so remove what exists, append one exclude pathspec per generated path to every `git add -A` below (`-- . ':(exclude,glob)**/__pycache__/**'`), and report the paths. Not `info/exclude`: it sits in the clone's common git dir, and the clone stays untouched.

Then stage everything, normalize it, and measure both proofs, from this repository:

```bash
git -C <candidate> add -A [-- . '<exclude pathspec>'...]
python3 apps/repo-builder/src/scripts/retrofit.py normalize \
  --candidate <candidate> --records <records>
python3 apps/repo-builder/src/scripts/retrofit.py proofs --template-repo . \
  --target "<commit>" --subtree apps/github-repository-template/src/base-repo \
  --candidate "<candidate>" --base "<base-commit>" --records <records>
```

`normalize` runs `git add --renormalize`, clears the executable bit from staged files not starting with `#!`, and runs the configuration's whitespace, end-of-file, line-ending and `adr-index` hooks over the staged paths, re-staging what they rewrite. It reports `renormalized`, `executable_cleared`, `rewritten` and `still_failing`. Fix each `still_failing` entry by hand before the proofs.

`proofs` measures from the index, so it runs with nothing committed. It records `copy` (with `differing` and `missing`), `rename_purity`, `authored`, `deleted`, `applied`, `preserved`, `payload_total`, `overridden`, `emptied` and `workflows_without_pull_request`. A move edited past git's rename threshold appears as a deletion plus an `authored` path. It refuses an empty index and a candidate already past `<base-commit>`.

**Commit everything this flow wrote** with the message in a file beside the candidate and `git commit -F <file>`; a message passed by process substitution has landed empty.

## The autofix pass

**Only the destination's own autofix runs before the bar**, bounded to what its tools do unattended and committed alone; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why. Fix no finding by hand here.

**First check each tool resolves its configuration inside the candidate**, since the candidate sits under this repository's `tmp/` and a tool walking upward finds *this* repository's settings. Read each language's resolved settings path (`ruff check --show-settings .` prints it as `Settings path:`); treat an unreadable path as outside. Where any tool fails, skip the pass, report the tool and the path, and measure the bar as it stood, saying which settings it was measured under.

```bash
python3 apps/repo-builder/src/scripts/retrofit.py autofix --candidate <candidate> \
  --template-repo . --target "<commit>" \
  --subtree apps/github-repository-template/src/base-repo --records <records>
```

It refuses uncommitted tracked changes, runs `scripts/fix` at most twice while a pass still changes something, and restores every rewritten path that was a byte-identical payload copy, listing it under `reverted` as a payload defect to report. It reports `shipped`, `passes`, `exit_status`, `rewritten` and `reverted`. **Its exit status is not the bar.** Where `shipped` is false, measure the bar without a pass. Then commit the pass alone, the same way.

Where the destination's test capability collects anything, report its result on both sides of the pass, since the formatter is the risky part; where it collects nothing, say so.

## The bar

**The bar is the destination's own check surface passing on the candidate**, read by [Running the destination's checks](lifecycle.md#running-the-destinations-checks). `FAIL` and `unavailable` block; `not-applicable` does not. Stage before every run, re-runs included, since `scripts/structure` enumerates the index:

```bash
git -C <candidate> add -A [-- . '<exclude pathspec>'...]
(cd <candidate> && scripts/summarize scripts/check) > <records>.check.txt
```

**Then execute the facts step 5 confirmed:**

```bash
python3 apps/repo-builder/src/scripts/retrofit.py facts --candidate <candidate> --records <records>
```

Per unit it runs `scripts/package <unit>` for real and `scripts/run <unit>` under `CI_DRY_RUN`, and flags either that printed `No project manifest found` as doing nothing, since both exit zero there. Neither is in the check surface, so a wrong declaration passes the bar otherwise. A failure is a wrong fact or a missing descriptor: fix it, and re-read it with the operator where the fix changes a fact they confirmed.

**An unmet bar is a failed retrofit and stops before the pull request**, naming the capability that could not pass and why. The fix does not ride along in the candidate. **The rest of that path is in [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md)**; a run that meets the bar never reads it.

## The review

**A met bar is followed by the review of the authored surface, before step 8 asks anything**; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why. Run the `/code-review` skill's `standard` scan (Standards, Spec, and Correctness/Logic) over the local candidate branch against the fixed point `origin/<default-branch>` at the commit step 2 fetched, the base the pull request will diff against.

- Scope it to [the retrofit's authored surface](reporting.md#reviewing-the-pull-request): the proofs record's `authored` and `deleted` paths, every `rename_purity` move that is not byte-identical, and the copy proof's `differing` paths. The autofix commit is off it.
- Include a grep of the destination for every `deleted` path and each move's `from`, since no check reads a live reference in destination-owned prose.

Commit the corrections as their own commit, then stage and run the bar again over that head; repeat until every finding is corrected or recorded as incorrectly identified. Step 8's question is asked about this head, and step 9 publishes it unchanged.
