# Step 6 — Reconcile the destination's layout

Part of [Retrofit](retrofit.md). This step turns the destination's tree into the template's layout with three instruments: **move** a path to where the rules put it, **repair** the configuration a move broke, and **retire** a destination artifact the payload already covers.

**The complete plan is presented before a single file moves.** Every path, its destination, and which instrument applies, in one list. The operator disposes per path, and a rejection with no correction stops the retrofit exactly as a rejected unit map does: a partial layout is the one state no later run can reason about.

**Every root scoped folder the unit map claims moves to its unit.** `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` at the root mean repository-wide. `scripts/structure` reports the scope rule `not-applicable`, so the unit map is the only thing that makes this move decidable.

**Data splits by whether the program writes it.** What it only reads, including a file the operator edits by hand, moves to the owning `assets/`. A file it writes moves to `apps/<unit>/state/`, which the payload's `.gitignore` excludes as `/apps/*/state/`, with the path the program resolves rewritten and the tracked copy removed. A written file that also holds a record the program will not write again, such as a finished season, can keep that record as a read-only snapshot under `assets/` for the program to fall back to; that fallback is new code, so the plan proposes it and the flow writes it only once the operator confirms. A harness backup follows the file it backs up. The plan names each data file as read or written, since only the code that opens it can tell. The report tells the operator to carry each moved live file before pulling the merge — copy it into `apps/<unit>/state/`, then `git restore` the old path — because the pull refuses to remove a tracked file they changed and silently removes one they did not.

**Documentation stays repository-wide**, even where every other scoped folder moved under the one unit: `scripts/adr-index` indexes from a root path, under [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path). Migrate existing records to that path here, with the moves.

**A readme below the root is documentation and moves with it**, into the nearest owning `docs/` under a name describing what it is about. The root readme stays, as an addon the destination already holds.

**A move that empties a directory can leave it standing in the operator's clone**, held open by untracked or ignored residue the candidate never had. The proofs record lists each such directory under `emptied`, with the residue read from the clone. Report each one and remove none of it: a file git never tracked is the operator's, and only they know whether it is still wanted.

**The flow writes no `.structure-allow` entry.** A path that cannot be moved is reported with the reason; the operator may write the entry themselves afterwards, outside the flow.

**Configuration a move broke, the flow repairs, in the same change**: a test path, a build target, a workflow's working directory, a lint or coverage root. A path reference that is **exactly** a path the flow moved is rewritten. Prose describing the old structure is reported and left alone.

**An artifact is retired only when the payload covers its whole role**, judged by what it does in its flow, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script): fully covered is retired, with its callers repointed and `generation.superseded` recording it; partially covered survives as a reported conflict naming the duplicated parts. The destination never loses a capability it had before.

**Two collisions the overlay skipped are settled here.**

The ignore file is replaced outright, at the payload's mode as well as its content, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). Destination rules the payload does not cover are **reported rather than re-added**. Where un-ignoring a generated directory makes the candidate fail its own check surface, the flow stops and the operator decides which rule survives.

**A rule the operator restores gets no [overridden path](lifecycle.md#overridden-paths) entry**, because a path the flows replace outright can never be one: the entry would make every later update skip the ignore file. The restored rule surfaces as a collision at the next update instead. Report it, and report that the ignore file is no longer byte-identical to the payload's.

The instruction file is merged, and re-established as one of the last steps of the whole retrofit rather than here, so it describes what this run did. This step takes the merge as far as the layout facts.

**What this step promises.** For a checkable destination, `scripts/structure` passes on zero allowlist entries after it. That says nothing about the destination's own checks, which step 7 measures.
