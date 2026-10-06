# Retrofit

Rules from [`lifecycle.md`](lifecycle.md) that apply throughout, stated here so the file is never opened whole. Each links to its section for the reasoning; read that section only when the statement here is not enough.

- **Placeholders.** Quote every `<placeholder>` when substituting (`git push origin "$branch"`), and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell.
- **Ownership** ([`## Ownership`](lifecycle.md#ownership)). `managed` paths are reconciled with the destination's intent, never blindly overwritten. `product` paths are preserved: a payload path that collides with product content is reported and the run stops there. An unmatched path is product. The longest matching rule wins. A root file matches no directory pattern, so it is owned only where named individually. The root `CLAUDE.md` is managed and merged, not overwritten.
- **Overridden paths** ([`### Overridden paths`](lifecycle.md#overridden-paths)). A managed payload path whose destination version was chosen is recorded in `generation.overrides` as an entry with a `path` and a `reason`, one entry per path. Never for a product path, and never for a path replaced outright such as `.gitignore`. Steps 6 and 7 link the full rule where they record one.
- **Modes** ([`### The payload's mode travels with the payload's content`](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content)). A payload path landed over an existing file ends at the payload's mode, read from `git ls-tree <commit> -- <subtree>/<path>` at the resolved source commit. The archive step does this only for an absent path.
- **Resuming** ([`### Resuming`](lifecycle.md#resuming)), only when this run re-enters a stopped one. Re-invoking the command is the resume: re-observe live state and skip what is done.

Every other lifecycle section a retrofit needs is linked from the step that uses it and read there: [`## Manifest`](lifecycle.md#manifest) at step 5, [`## Dependabot entries follow the manifests present`](lifecycle.md#dependabot-entries-follow-the-manifests-present) and [`## Running the destination's checks`](lifecycle.md#running-the-destinations-checks) at step 6 where it un-ignores a directory and at step 7, [`## The runner variable is set only where it is safe and answerable`](lifecycle.md#the-runner-variable-is-set-only-where-it-is-safe-and-answerable) and [`## Remote action gates`](lifecycle.md#remote-action-gates) at step 8. `## Reviewing and reporting` only routes to `reporting.md`, which steps 7 and 9 link directly.

Shared mechanics stay in [`generate.md`](generate.md) and are cited by heading; follow a citation with `sed -n '/^### Step 3 /,/^### /p'` rather than opening the whole file.

A retrofit brings a repository that was never generated from this template under it: the destination has content and carries no record. Everything a generate builds from nothing, a retrofit reconciles against something somebody is already shipping. `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why the flow is shaped this way.

**No language is chosen on this path**, so [`wayfinding.md`](wayfinding.md) and [`choosing_a_language.md`](choosing_a_language.md) are not read. The destination committed to its languages before this flow existed; step 5 observes them.

**Every record this run keeps sits at one prefix**, `<records>`: `<absolute path to this repository>/tmp/<repository-name>.<first 12 of the payload commit>`. Every `retrofit.py` subcommand requires `--records <records>`, and each writes its JSON to `<records>.<name>.json`, removing its earlier record before it runs so a failed step leaves none: `proofs`, `normalize`, `facts`, `references`, `autofix`, `hooks`, `sync`, `sweep`, `hosted-read`, `hosted-apply`, `decisions`, and `upstream-merge` from `resume`, a name that leaves `<records>.resume.json` to the hooks' resume record. `hosted-apply` reads its earlier record first and keeps the writes a later call does not approve, and `references` reads its own first and keeps the moves it searched, in each case unless the sweep has run since it was written; `decisions` always reads its own, since judgements are recorded up to the report, after the sweep, and `resume` removes it, since a resumed run judges again. Preflight's goes to `<records>.preflight.json`, the bar's summary to `<records>.check.txt` (the latest run overwrites it), and hosted apply's write log to `<records>.writes.json`, a path derived from the prefix rather than passed. The report and the pull-request body read the records by name. The sweep removes only the write log of these.

## Steps

Read each step's file when the flow reaches it.

1. [Resolve the source commit and preflight](retrofit-step-1-preflight.md) — `preflight.py retrofit`
2. [Build the candidate](retrofit-step-2-candidate.md) — `git worktree add`; `retrofit.py sweep` at the end
3. [Overlay the payload's absent paths](retrofit-step-3-overlay.md) — `git archive | tar`
4. [Provision the environment and the hooks](retrofit-step-4-provision.md)
5. [Read the destination's units](retrofit-step-5-units.md)
6. [Reconcile the destination's layout](retrofit-step-6-layout.md)
7. [Dispose the collisions, write both records, meet the bar](retrofit-step-7-bar.md) — `retrofit.py normalize`, `proofs`, `references`, `autofix`, `scripts/summarize scripts/check`, `retrofit.py facts`, `/code-review`; [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md) only when the bar is unmet
8. [The hosted-write gate](retrofit-step-8-hosted-writes.md) — `retrofit.py hosted read`, `hosted apply`
9. [Publish, prove, and offer the merge](retrofit-step-9-publish.md) — `retrofit.py pr-body`, `gh pr create`; `retrofit.py hooks` and `sync` after a taken merge

Then the [report](retrofit-report.md) — `retrofit.py report`, filled with `retrofit.py decide`.
