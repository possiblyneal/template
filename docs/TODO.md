# TODO

Backlogged, informal tasks for this repository. Tasks for the template itself,
not for a project cloned from it.

## Backlog

### Record a destination's added Dependabot ecosystem entries

A generated repository whose manifest the payload does not ship has to add its own
`updates` entry by hand, and nothing records that it did. `.github/` is replaced whole
by an update, under "The automation directory is replaced, not reconciled" in
`apps/repo-builder/src/references/lifecycle.md`, so the entry is dropped on the next
reconcile with no trace that it was ever there.

This repository already carries the case and absorbs the cost manually: the root-only
`pip` entry in `.github/dependabot.yml`, the one its comment marks "Root-only", exists
because the payload ships no
`pyproject.toml`, `scripts/github-parity` names `dependabot.yml` its one content
exception to permit the divergence, and the entry's own comment says to re-add it when
reconciling, the same as the deleted `codeql.yml`.

The asymmetry is the gap. `generation.features` in `.repo-template.json` records
deliberate *omissions*, which is how `codeql.yml` survives being dropped
(`"codeql": "omitted-by-choice"`). There is no equivalent slot for a deliberate
*addition*, so a destination's added ecosystem entry has nowhere to be written down.
`possiblyneal/glydr` is a live instance: it has `apps/glydr/go.mod`, no `gomod` entry,
and `"features": {}`. Filed there as issue #150.

Wanted: somewhere in the manifest for a destination to declare the entries it added, and
a reconcile step in `apps/repo-builder/src/references/generate.md` that restores them.

Not conditional generation keyed on a detected manifest. "Step 7 — Derive the
application boundaries" in `apps/repo-builder/src/references/generate.md` refuses to
render a root manifest even when wayfinding picked a language, and cites this exact file
as the precedent: "A wrong guess is worse than an absent file, the same reasoning
`.github/dependabot.yml` follows in listing only the two manifests the template itself
ships." The fix is a record of what a human chose, not an inference.
