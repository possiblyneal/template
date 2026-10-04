# Retrofit

Read these sections of [`lifecycle.md`](lifecycle.md) first rather than the whole file, each with the subsections under it — `sed -n '/^## Manifest$/,/^## /p'` and its equivalent per heading. They apply throughout:

- the paragraph on quoting a `<placeholder>`, at the top of the file
- `## Manifest`
- `## Ownership`, with `### Overridden paths` and `### The payload's mode travels with the payload's content`
- `## Dependabot entries follow the manifests present`
- `## Running the destination's checks`, with `### Tools the first manifest must declare`, `### Working hooks in a candidate`, and `### Working hooks in the destination after a merge`
- `## The runner variable is set only where it is safe and answerable`
- `## Remote action gates`
- `## Reviewing and reporting`
- `### Resuming`, only when this run re-enters a stopped one

Every other lifecycle section a step links is read where the link sits, by its heading. Shared mechanics stay in [`generate.md`](generate.md) and are cited by heading; follow a citation with `sed -n '/^### Step 3 /,/^### /p'` rather than opening the whole file.

A retrofit brings a repository that was never generated from this template under it: the destination has content and carries no record. Everything a generate builds from nothing, a retrofit reconciles against something somebody is already shipping. `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why the flow is shaped this way.

**No language is chosen on this path**, so [`wayfinding.md`](wayfinding.md) and [`choosing_a_language.md`](choosing_a_language.md) are not read. The destination committed to its languages before this flow existed; step 5 observes them.

**Every record this run keeps sits at one prefix**, `<records>`: `<absolute path to this repository>/tmp/<repository-name>.<first 12 of the payload commit>`. Every `retrofit.py` subcommand requires `--records <records>`, and each writes its JSON to `<records>.<name>.json`, removing its earlier record before it runs so a failed step leaves none: `proofs`, `normalize`, `facts`, `autofix`, `hooks`, `sweep`, `hosted-read`, `hosted-apply`. Preflight's goes to `<records>.preflight.json`, the bar's summary to `<records>.check.txt` (the latest run overwrites it), and hosted apply's write log to `<records>.writes.json`, a path derived from the prefix rather than passed. The report and the pull-request body read the records by name. The sweep removes only the write log of these.

## Steps

Read each step's file when the flow reaches it.

1. [Resolve the source commit and preflight](retrofit-step-1-preflight.md) — `preflight.py retrofit`
2. [Build the candidate](retrofit-step-2-candidate.md) — `git worktree add`; `retrofit.py sweep` at the end
3. [Overlay the payload's absent paths](retrofit-step-3-overlay.md) — `git archive | tar`
4. [Provision the environment and the hooks](retrofit-step-4-provision.md)
5. [Read the destination's units](retrofit-step-5-units.md)
6. [Reconcile the destination's layout](retrofit-step-6-layout.md)
7. [Dispose the collisions, write both records, meet the bar](retrofit-step-7-bar.md) — `retrofit.py normalize`, `proofs`, `autofix`, `scripts/summarize scripts/check`, `retrofit.py facts`, `/code-review`; [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md) only when the bar is unmet
8. [The hosted-write gate](retrofit-step-8-hosted-writes.md) — `retrofit.py hosted read`, `hosted apply`
9. [Publish, prove, and offer the merge](retrofit-step-9-publish.md) — `retrofit.py pr-body`, `gh pr create`; `retrofit.py hooks` after a taken merge

Then the [report](retrofit-report.md) — `retrofit.py report`.
