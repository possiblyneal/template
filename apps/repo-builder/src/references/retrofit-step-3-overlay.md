# Step 3 — Overlay the payload's absent paths

Part of [Retrofit](retrofit.md). Write the payload paths preflight found absent and no colliding path; every collision waits for step 7's per-file decision. Never copy everything and restore, which deletes destination content between the two steps.

The absent set is `absent_paths` in `<records>.preflight.json`, written as given; `<absent-paths>` below is that array, one path per line.

**The payload's placeholder unit is in neither list, and preflight holds it back.** `apps/app-name/` exists for [generate's Step 8 — Personalize the candidate](generate.md#step-8--personalize-the-candidate) to rename; a retrofit reads its units off the destination. Do not add it back because it is absent (see `PLACEHOLDER_UNIT_PREFIX` in `preflight.py`).

```bash
xargs -r -a <absent-paths> -d '\n' \
  git -C <template-repo> archive --format=tar "<commit>:<subtree>" -- |
  tar -x -i -C <candidate>
```

- `-r`: an empty set writes nothing; without it `git archive <tree> --` archives the whole payload over every collision.
- `-i`: tar reads past each archive's end marker when `xargs` batches a long list.
- `git archive` carries file modes, so `scripts/check` lands executable. [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content) covers the skipped colliding paths.

Count the extracted paths against the absent set before moving on, and trust the count, not the exit status: an empty set leaves `tar` on empty stdin, which exits non-zero on a correct run.

Leave untracked state in the operator's clone behind; step 4 rebuilds what the tracked manifests describe.
