# Step 8 — The hosted-write gate

Part of [Retrofit](retrofit.md). A **hosted write** changes the destination's state on the host where no pull request can carry it: a repository setting, a branch rename, a label, a ruleset. Every one happens here, at one gate, after step 7's bar passed and its review's corrections were committed; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why this diverges from [generate](generate.md). The unmet-bar path's push and pull request fall under [Remote action gates](lifecycle.md#remote-action-gates), not here.

**The gate creates nothing.** It confirms the identity preflight proved against the origin and authorizes each write by naming the exact command that performs it. **No write is performed that the gate did not list.**

**Generate's ruleset probe is not performed**, so nothing is pushed at the default branch here. Enforcement is **not yet proven at this gate**; step 9's pull request proves it under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present).

Read the gate's question in one call and perform what it approved in a second. Neither touches the rename under 2:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py hosted read \
  --repository <owner>/<repository> --records <records>

python3 apps/repo-builder/src/scripts/retrofit.py hosted apply \
  --repository <owner>/<repository> --records <records> \
  --approve <write> [--approve <write> ...] \
  [--label <name> ...] [--keep-case-variants] \
  [--ruleset <body.json> [--replace-ruleset <id>]]
```

`read` reports `visibility`, `admin`, `default_branch`, `merge_settings`, `labels`, `dependabot`, `push_protection`, `rulesets` and `runner`. A refused reading carries `not offered` for the host's upgrade message and `permissions gap` for any other 403.

`apply` takes `--approve` once per approved write — `merge-settings`, `labels`, `dependabot-alerts`, `security-updates`, `push-protection`, `ruleset`, `runner-variable` — performs only those, in that order, and reports `writes`, `reasons`, `write_log` and `findings`. A write already in the log reports `logged` and is not performed again. `--label` names the labels in force (under 3); `--keep-case-variants` is for a destination whose own `triage-labels.md` is in force. `--ruleset` is the body composed under 4; `--replace-ruleset` names the destination ruleset it repairs in place.

Five writes, in this order, the last conditional.

**1. Merge settings, in one call.** `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge` and `delete_branch_on_merge` go in a single `PATCH`, since a half-applied merge policy is worse than none. State the four current values from `merge_settings` before overwriting them. All four `null` means the wrong field spelling (see [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings)), not every merge method disabled. Declinable; record a refusal and its reason in `generation.features`.

**2. The default-branch rename.** **Declining is a hard stop**: the payload's workflows pin the branch name, so CI would never fire on the old one.

**An open pull request whose head is the branch being renamed is a hard stop before any write at all**, because the host closes it rather than retargeting it. Enumerate **by head ref as well as by base ref**. The stop names the remedies: merge it, close it deliberately, or copy the branch and open a fresh pull request, losing the review conversation.

A ruleset naming the old branch literally is **repaired in place**, rewriting the name. Never switch it to a dynamic condition: that substitutes a rule the owner did not write.

The gate presents the four commands every existing clone needs:

```bash
git branch -m <old> <new>
git fetch origin
git branch -u "origin/<new>" <new>
git remote set-head origin -a
```

**3. Labels**, with the case-insensitive guard and payload-spelling rename [Remote action gates](lifecycle.md#remote-action-gates) specifies: a label carried under a different case is renamed, not created beside it, and the rename is its own line. List `code-reviewed` where the destination lacks it, since step 9 applies it.

**4. Security settings and the branch ruleset** — dependency alerts, security updates, push protection, and the ruleset generate creates. Declinable and recorded. Push protection refused on a private destination on a free plan is reported, not failed.

Name required checks by check run, not job id: `CI`, not `ci`; [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) has the full set. A misspelled context writes without error and silently blocks every pull request; step 9's `mergeable`/`mergeStateStatus` pair catches it.

An existing ruleset requires contexts from workflows that [the automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) replaced. Read its required contexts before writing, name at the gate every one the payload's workflows do not report, and repair it in place to the contexts that now exist.

**5. The runner variable**, only where both conditions in [The runner variable is set only where it is safe and answerable](lifecycle.md#the-runner-variable-is-set-only-where-it-is-safe-and-answerable) hold at this gate: the destination reads `PRIVATE` and a `dev-<repository>` runner reads `online`. Where either fails, say which and offer nothing. Declinable; step 9's `runner_name` on the pull request's jobs is its proof. **A runner the operator brings online later is a second `hosted apply --approve runner-variable`**, run before step 9's sweep removes the write log, never a hand-run `gh variable set`, so the report carries the write and its reverse command rather than `not requested`. If the pull request has already merged, the proof is `runner_name` on a rerun of the default branch's workflows.

**A refusal carrying the host's upgrade message means the feature is not offered**; `not offered for the plan` is the whole finding. The same refusal **without** that message is a permissions gap, raised at the gate: the credential cannot do what the gate authorized.

**Every post-write verification polls rather than reading once**, since the host can return the pre-write state right after an accepted write.

**There is no undo mechanism, so the report carries the before-state of every hosted write**, in **two separately named sections**: reversible writes with the command that reverses each, and irreversible ones with each one's cost. Never one section.
