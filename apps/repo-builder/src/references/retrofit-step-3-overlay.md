# Step 3 — Overlay the payload's absent paths

Part of [Retrofit](retrofit.md). Write the payload paths preflight found absent, and write no colliding path at all. Every colliding path stays in the collision list for step 7's per-file decision. Copy-everything-and-restore is rejected, because it deletes destination content in the window between the two steps.

The absent set is `absent_paths` in `<records>.preflight.json`, written as given. `<absent-paths>` below is that array written out one path per line.

**The payload's placeholder unit is in neither list, and preflight holds it back.** `apps/app-name/` exists for [generate's Step 8 — Personalize the candidate](generate.md#step-8--personalize-the-candidate) to rename; a retrofit reads its units off what the destination already delivers. Do not add it back because it is absent: `preflight.py`'s comment on `PLACEHOLDER_UNIT_PREFIX` says why.

```bash
xargs -r -a <absent-paths> -d '\n' \
  git -C <template-repo> archive --format=tar "<commit>:<subtree>" -- |
  tar -x -i -C <candidate>
```

- `-r` makes an empty absent set write nothing; without it `git archive <tree> --` archives the whole payload over every collision.
- `-i` keeps tar reading past the first archive's end marker when `xargs` batches a long list.
- `git archive` carries the file mode, so `scripts/check` lands executable. [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content) covers the colliding paths this step skips.

Count the extracted paths against the absent set before moving on, and read that count rather than the pipeline's exit status: an empty set leaves `tar` reading empty stdin, which exits non-zero on a run that correctly wrote nothing.

Untracked state in the operator's clone is deliberately left behind; step 4 rebuilds what the tracked manifests describe.
