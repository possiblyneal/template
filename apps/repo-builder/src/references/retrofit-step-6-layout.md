# Step 6 — Reconcile the destination's layout

Part of [Retrofit](retrofit.md). Turn the destination's tree into the template's layout with three instruments: **move** a path to where the rules put it, **repair** configuration a move broke, **retire** a destination artifact the payload already covers.

**The complete plan is presented before a single file moves**: every path, its destination, and its instrument, in one list. The operator disposes per path. A rejection with no correction stops the retrofit, as a rejected unit map does, since a partial layout is the one state no later run can reason about.

**Every root scoped folder the unit map claims moves to its unit.** Root `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` mean repository-wide. `scripts/structure` reports the scope rule `not-applicable`, so only the unit map decides this move.

**Data splits by whether the program writes it.**

- Read-only data, including a file the operator edits by hand, moves to the owning `assets/`.
- A written file moves to `apps/<unit>/state/` (excluded by the payload's `.gitignore` as `/apps/*/state/`): rewrite the path the program resolves and remove the tracked copy.
- A written file that also holds a record the program will not write again, such as a finished season, may keep that record as a read-only snapshot under `assets/` for the program to fall back to. That fallback is new code: the plan proposes it, and the flow writes it only once the operator confirms.
- A harness backup follows the file it backs up.
- The plan names each data file as read or written, since only the code that opens it can tell.
- The report tells the operator to carry each moved live file before pulling the merge: copy it into `apps/<unit>/state/`, then `git restore` the old path. The pull refuses to remove a tracked file they changed and silently removes one they did not.

**Documentation stays repository-wide**, even where every other scoped folder moved under the one unit, because `scripts/adr-index` indexes from a root path; see [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path). Migrate existing records to that path here, with the moves.

**A readme below the root is documentation and moves with it**, into the nearest owning `docs/` under a name describing its subject. The root readme stays, as an addon the destination already holds.

**A move that empties a directory can leave it standing in the operator's clone**, held open by untracked or ignored residue. The proofs record lists each such directory under `emptied`, with the residue read from the clone. Report each and remove none of it: an untracked file is the operator's to judge.

**The flow writes no `.structure-allow` entry.** Report a path that cannot be moved with the reason; the operator may add the entry afterwards, outside the flow.

**Configuration a move broke, the flow repairs, in the same change**: a test path, a build target, a workflow's working directory, a lint or coverage root. Rewrite a path reference only when it is **exactly** a path the flow moved. Report prose describing the old structure and leave it alone.

**An artifact is retired only when the payload covers its whole role**, judged by what it does in its flow, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script). Fully covered: retire it, repoint its callers, and record it in `generation.superseded`. Partially covered: it survives as a reported conflict naming the duplicated parts. The destination never loses a capability it had.

**Two collisions the overlay skipped are settled here.**

Where the payload ships no `.gitignore`, there is nothing to replace: report that and keep the destination's. Otherwise the ignore file is replaced outright, at the payload's mode as well as its content, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). Report destination rules the payload does not cover; do not re-add them. Where un-ignoring a generated directory makes the check surface (run under [Running the destination's checks](lifecycle.md#running-the-destinations-checks)) fail a row it passes with the ignore file as the destination had it, stop; the operator decides which rule survives. `unit-declaration` fails on both runs until step 7 writes the `.unit.json` files, so it is not a finding here.

**A rule the operator restores gets no [overridden path](lifecycle.md#overridden-paths) entry**: the entry would make every later update skip the ignore file. The restored rule surfaces as a collision at the next update instead. Report it, and report that the ignore file is no longer byte-identical to the payload's.

The instruction file is merged in step 7, after the records and before the bar is measured, so it describes what this run did and the bar reads it. This step takes the merge only as far as the layout facts.

**What this step promises.** For a checkable destination, `scripts/structure` passes on zero allowlist entries once step 7 has written the `.unit.json` declarations. It says nothing about the destination's own checks; step 7 measures those.
