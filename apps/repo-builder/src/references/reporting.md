# Reporting

The end of every flow. [`lifecycle.md`](lifecycle.md) is the contract this sits under; read it first.

## Reviewing the pull request

A pull request this skill opens is not code-reviewed. Almost all of it is the payload at the target commit, copied byte for byte, and that content was reviewed in the template repository before it merged there; reviewing it again in every generated repository re-reviews the same lines once per destination and reports the template's own judgments as findings against a repository that did not make them. Where a hook or a reviewer asks for a review of this pull request, this section is the answer to give, and the final report says the review was skipped so that a green result is not read as a review that passed.

What replaces it is the check the copies actually need, which no reviewer was doing anyway: prove they are copies. Each flow runs it before its publish gate, because a check that runs once the pull request is open can no longer stop anything.

For every path in the candidate diff, compare the candidate blob against the blob it was copied from and collect the paths that differ. Read the diff from the index rather than from a commit range: every flow runs this before the step that commits, so a range against `HEAD` is empty here and would report a clean `0/0` over nothing at all.

```bash
git -C "<destination>" diff --cached --name-only --diff-filter=d |
  while read -r path; do
    git -C "<template>" cat-file -p "<commit>:<prefix>/$path" 2> /dev/null |
      diff -q - "<destination>/$path" > /dev/null || echo "$path"
  done
```

`<commit>` and `<prefix>` are each flow's own. Generate and update read the payload subtree at the target commit; adopt reads `repository-addons/` at the recorded commit, which is a sibling of the subtree rather than inside it. Where the template renamed a file its two names are two paths, so read the destination path against the payload's new one. A path `cat-file` cannot find was never a copy, and belongs to the authored surface instead.

What matches is the template's, already reviewed, and closed. What is left is the authored surface, short enough to read line by line. Read it that way, because it is where this skill's own mistakes land: a merge that keeps both intents can still leave a document asserting something the merge just made false, and a file the payload deletes can leave a live reference behind in destination-owned prose that no check reads. Grep the destination for every path the flow deletes or renames before calling the candidate verified.

Which files make up that surface differs by flow:

- **Update** — every managed file the destination had also changed and this skill hand-merged, plus `.repo-template.json`.
- **Generate** — everything step 8 personalized: the root `CLAUDE.md` Child Index, each `apps/<name>/` and its `.unit.json`, the ADRs, and `.repo-template.json`. This surface is larger than update's and it gets no second look, because a bootstrap generate merges its own pull request under [Generate](generate.md) step 12. Read it before that merge rather than after.
- **Adopt** — every region `addon-adoption.json` names for the addons taken. Here differing paths are the expected result rather than the exception: an addon is adopted by editing it, so byte-identity would mean the adoption never happened. Confirm that what differs is the named regions and nothing besides.

Report the authored surface in **File list**, so the reader sees which lines were the template's and which were this run's.

## Final report

Use this stable shape. On a generate into an empty destination the Reconciliation lines are empty or trivially everything, and File list carries the weight; a generate into a destination that already has content fills them like any other flow, Superseded included, since it is the only section reporting a file the payload ships and the candidate lacks, which no check can fail on. On an adopt the Template line shows the recorded commit on both sides because the pin does not move, and the Addon adoption block carries the weight. On a generate stopped at the wayfinding handoff there are no Application boundaries to report — that absence is the result; the Wayfinding line names the trigger and the map, Repository settings still reports the repository that exists, and Pending action carries the resume.

First prompt is a generate's only, and it is written for a reader this session never speaks to: whoever opens the first working session in a fresh clone of the new repository. Everything this session knows about that repository's initial state dies with it otherwise — which checks are red on purpose, what the tracker holds, what a clone still has to install — and the next session rediscovers each one as a defect. Emit it as a fenced block so it can be copied whole, fill every placeholder from what actually happened rather than from this shape, and drop a line whose condition did not arise rather than shipping it empty. On an update or an adopt the destination already has working sessions and there is no first prompt to write; omit the section. On a generate stopped at the wayfinding handoff the resume belongs to the operator of this session, not to a new one, so Pending action carries it and this section is still omitted.

````md
## Repo Builder Result

- Operation: generate | update | adopt | stopped
- Pull request: <URL or "not created">
- Template: <old full commit, or "not previously generated"> -> <target full commit>
- Destination: <owner/repository>

### Reconciliation
- Applied: <paths or none>
- Preserved: <paths or none>
- Renamed/deleted: <paths or none>
- Conflicted: <paths and competing intents, or none>
- Superseded: <path>: <what it did> -> <the payload path or check now carrying it> | retired, callers repointed (<caller paths>) | none
- Partially covered, not cut: <script path>: <the parts the check surface already does> | none
- Overridden: <path>: <the recorded reason the destination's version was chosen> | expired, payload landed and entry dropped (<paths>) | none

### Application boundaries
- <deployable>: choke point <constraint, or "none bound; time-to-working-code"> -> <language>, <selected from list | reasoned from the seam contract | measured against it>
- Wayfinding: short form settled it | handed off to `/wayfinder` (<which trigger>), map at <URL or path> | skipped, supplied in the invocation
- ADRs written: <paths, or none>

### File list
- <payload paths accounted for, and every difference named as intended or as a defect>
- Authored surface: <paths whose candidate blob differs from the blob it was copied from, or none>

### Addon adoption
- <addon taken>: <slot token, review section, or external step>: filled | reviewed | done | OUTSTANDING (<what remains>)
- <addons offered and not taken, on one line>

### Repository settings
- <setting>: enabled | unavailable (<reason>) | not requested
- Drift (update and adopt): <setting>: <current> -> <proposed>: patched | declined by user | none found | not checked (<reason>)
- Merge settings overwritten (generate into existing content only): <setting>: <prior value> -> <applied value> | declined by user, recorded in `generation.features`
- Issue tracker: <GitHub | GitLab | local markdown | other>, recorded in `docs/agents/issue-tracker.md`, shipped by the payload | written by `/setup-matt-pocock-skills` | kept from the destination; labels: created (<names>) | renamed to the payload's spelling (<old -> new>; label search is case-sensitive, so anything pinned to the old string stops matching) | already present | none created (<reason>)

### Verification
One line per check, from `scripts/summarize <command>` rather than from a filter built for the occasion.

- `<exact command>`: pass | fail | unavailable (<reason>)
- Hooks: installed at <scope> into <hooks directory>; `core.hooksPath` left pinned there (update and adopt) | global `core.hooksPath` set to <value>, worked around rather than unset | `extensions.worktreeConfig` set on <clone> and left set (retrofit)
- Copied paths byte-identical to their source: <count>/<count>; the rest are the authored surface, under File list. An overridden path is in neither count, under Reconciliation instead
- Code review: skipped, as [Reviewing the pull request](#reviewing-the-pull-request) directs
- Default branch after merge: <check-suite result> | n/a (nothing merged)

### Resumption
Present only on a run that re-entered a stopped flow, as [Resuming](lifecycle.md#resuming) directs.

- Re-observed as already done: <what live state showed complete, so this run skipped it>
- Taken from the resume record: <the issues and decisions read back rather than repeated>
- Redone: <anything this run performed again, and why live state did not answer it>
- Retries: <the transient failures retried and their outcomes, or none>

### Pending action
<none, or the exact decision/authorization needed>

### First prompt
Generate only. Copy this into the first session opened in a clone of the new repository:

```text
Work <owner/repository>. Clone it and install the hooks: `pre-commit install`, or, if that
refuses because a `core.hooksPath` is already set on this machine, `pre-commit
init-templatedir` into a directory of its own with `core.hooksPath` pointed at it. Nothing
else installs them, and without them commits land unattributed and unchecked. Then read the
root `CLAUDE.md` before touching anything.

The plan of record is <the issue tracker named in docs/agents/issue-tracker.md>, not this
message. Open tickets: <count>. First with no open blocker: <#n — title>. Start there.

Expected initial state, not defects: <the absent root manifest scripts/doctor fails on |
the workflow count a stripped codeql.yml leaves, per lifecycle.md "Code scanning follows
visibility" | none>.

The first root manifest owes the checks their tools: <the declarations for the selected
language, from lifecycle.md "Tools the first manifest must declare" | none, <language>
declares no tools>. An undeclared tool reports `unavailable`, which fails the run.

Branch before you commit; a commit made on `main` is refused at the hook.
```
````

The manifest sentence's lead-in, `The first root manifest owes`, is what the generation eval reads the handover for; rewording it updates the eval in the same change.
