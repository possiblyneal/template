# Repo Builder Lifecycle Contract

## Contents

- [Manifest](#manifest)
- [Ownership](#ownership)
- [Generate](#generate)
- [Update](#update)
- [Remote action gates](#remote-action-gates)
- [Failure and recovery](#failure-and-recovery)
- [Final report](#final-report)

## Manifest

Every built repository tracks `.repo-template.json`:

```json
{
  "schema_version": 1,
  "template": {
    "repository": "https://github.com/possiblyneal/template",
    "subtree": "apps/github-repository-template/src/base-repo",
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "destination": {
    "repository": "owner/repository",
    "default_branch": "main"
  },
  "generation": {
    "application_name": "billing-api",
    "languages": ["python"],
    "package_manager": "uv",
    "visibility": "private",
    "features": {
      "codeql": "omitted-private-without-ghas"
    }
  },
  "ownership": [
    {"path": ".repo-template.json", "mode": "managed"},
    {"path": "scripts/**", "mode": "managed"},
    {"path": ".github/**", "mode": "managed"},
    {"path": ".claude/hooks/**", "mode": "managed"},
    {"path": ".claude/rules/**", "mode": "managed"},
    {"path": ".claude/settings.json", "mode": "managed"},
    {"path": ".pre-commit-config.yaml", "mode": "managed"},
    {"path": ".gitattributes", "mode": "managed"},
    {"path": ".gitignore", "mode": "managed"},
    {"path": ".worktreeinclude", "mode": "managed"},
    {"path": ".mcp.json", "mode": "managed"},
    {"path": "apps/**", "mode": "product"},
    {"path": "libs/**", "mode": "product"},
    {"path": "tests/**", "mode": "product"},
    {"path": "tools/**", "mode": "product"},
    {"path": "docs/**", "mode": "product"},
    {"path": ".claude/skills/**", "mode": "product"},
    {"path": ".claude/agents/**", "mode": "product"},
    {"path": ".claude/output-styles/**", "mode": "product"},
    {"path": ".claude/workflows/**", "mode": "product"}
  ]
}
```

Use a full lowercase 40-character commit. `template.commit` is the last template version successfully applied to the candidate state. Change it only after the candidate passes verification; commit it with the update it describes.

Record generation choices that change rendered files or repository settings. Do not record timestamps, a pending target commit, destination HEAD, or duplicate file contents.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it.

Unmatched defaulting to product is the safe direction for a path the template does not ship, and the wrong one for a path it does. A root dotfile matches no directory pattern, so `.pre-commit-config.yaml`, `.gitattributes`, and `.gitignore` fall through to product unless named individually — and those files carry the pinned hook revisions behind the secret scanner and the merge policy keeping a lockfile from being line-merged. A payload fix to any of them would land nowhere while the update reported success. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a file at the root.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

## Generate

1. Resolve the requested source to an exact commit and run:

   ```bash
   python3 .claude/skills/repo-builder/scripts/preflight.py generate \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --subtree apps/github-repository-template/src/base-repo \
     --destination-repository <owner/name> \
     --default-branch main
   ```

   `generate` validates the source only. It takes the destination as a name, never inspects it, and so cannot tell an empty repository from one with content. Establish that yourself before materializing.

2. Collect only unresolved decisions: owner/name, visibility, application boundary/name, stacks and package managers, public-repository files, release behavior, and feature availability.
3. Materialize the subtree from that exact commit into an isolated local directory. Do not substitute the current working tree.
4. Personalize the candidate:
   - move `apps/app-name` to the kebab-case application name (do not copy it), verify the old path is absent, and update every reference;
   - replace the root `CLAUDE.md` placeholder section and bootstrap Child Index with repository-specific content;
   - initialize `docs/lessons.md` metadata and remove generation placeholders while retaining its durable writing guidance;
   - keep `docs/adr/0000-template.md` as the reusable ADR template;
   - create `.repo-template.json`;
   - create an empty `.env` at the destination root, and report it as intentionally untracked. It is tracked inside the payload, where the `.gitignore` pattern does not reach it, and ignored at a destination root, where it does — so it can never be committed there and reaches no clone. Do not force it into the index;
   - render visibility and feature choices honestly. In particular, omit or explicitly disable CodeQL for a private repository without GitHub Advanced Security rather than leaving a workflow known to fail.
5. Initialize Git locally with no remote and run the candidate's documented checks. Install the local pre-commit hook if the candidate requires it. Report skipped or unavailable checks; do not call them passes.

   Stage the candidate before running the checks. `pre-commit run --all-files` enumerates through the Git index, so an unstaged candidate is checked as the empty set and reports a pass over nothing.

   Tools the candidate's scripts look up on `PATH` may also run inside pre-commit's pinned environments. A tool reported unavailable by a script and passing under pre-commit in the same run was not skipped; report what each surface actually did.

6. Verify the file list, not only the content. Compare the payload's tracked paths at the source commit against the candidate's, and account for every difference as intended or as a defect. A file the payload ships and the candidate lacks is invisible to every check, because a check reads content and absence has no runner. Compare against the working tree as well as the index: a path the destination ignores is present and untracked rather than missing, and `.env` is the one the payload ships that way.
7. Present the local diff, the file-list reconciliation, checks, repository settings, and exact pending remote commands at the remote action gate.
8. Create the GitHub repository without auto-initialization. Create and push one empty root commit to the default branch so the full generated payload can be reviewed in a PR.
9. Configure supported settings after the default branch exists: Dependabot alerts/security updates, push protection where available, and a branch ruleset appropriate to the repository. Confirm plan/visibility limitations instead of treating API success as proof a feature is active.
10. Branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body because the empty base does not yet contain the repository's PR template.
11. Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge.

    A first-generation pull request has no checks, and that is not a failure. GitHub registers workflows from the default branch, so a PR introducing `.github/workflows/` triggers no runs at all. Report the absence as unverified rather than passing: an empty check list and a green one are both "no failures", and only one of them means the workflows ran.

## Generate into a repository that already has content

The steps above assume an empty destination. A destination with existing content is a generation whose collisions are decided by hand, and it needs its own rules:

1. Establish that the destination is a clean worktree, and enumerate every payload path that already exists there before writing anything.
2. Apply non-colliding payload files as ordinary additions.
3. For each collision, decide between the payload version, the destination version, and a merge — then state the decision and the reason per file. Verify afterwards that no destination-only content was dropped, naming what was preserved.
4. Never delete destination content to resolve a collision. A payload path that cannot be reconciled is a conflict to report, not a file to overwrite.
5. Record the collision decisions in `generation`, since they are choices a later update has to respect rather than re-litigate.
6. Do not create the placeholder application when the destination already has its own application boundary. Record the real boundary in `generation.application_name` and drop the payload's Placeholders section.

Ownership still governs what a later update may touch, and a hand-merged file is managed content whose destination edits are real intent. Classify deliberately: marking a whole tree product to protect it also freezes it.

## Update

1. Require a clean destination clone and identify its origin/default branch. Do not stash or discard the user's work.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/.claude/skills/repo-builder/scripts/preflight.py update \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   The command validates the manifest, repository identities, clean worktree, old and target subtrees, full commits, ancestry, and ownership classification. A non-descendant target is a hard stop.
3. Inspect four sources of intent:
   - old payload at the recorded commit;
   - current destination;
   - new payload at the target commit;
   - recorded generation decisions.
4. Reconcile only paths in the preflight delta:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision.
5. Classify every delta path as `applied`, `preserved`, `renamed/deleted`, or `conflicted`. Do not leave conflict markers.
6. Run the destination's documented checks. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery.
7. After successful checks, update `template.commit` to the exact target, validate the manifest again, and rerun checks affected by that change.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths.

## Remote action gates

Repository creation, settings writes, pushes, and pull-request creation are separate outward-facing actions. Plan and validate locally first. Immediately before them, show:

```text
Remote execution
- create: owner/repository (private, uninitialized)
- push: empty root commit -> main
- settings: Dependabot alerts/updates; push protection if available; main ruleset
- push: repo-builder/<short-target> -> generated content or template update
- open PR: repo-builder/<short-target> -> main
```

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

Stop before remote actions when semantic intent conflicts or verification fails. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

Report a check by what it did, and keep the four outcomes distinct: a check that passed, one that reported nothing to do, one whose runner was missing, and one that never ran. The candidate's own scripts make that distinction, and collapsing it in the report discards the thing they were built to preserve. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; a file that was never written cannot fail.

## Final report

Use this stable shape:

```md
## Repo Builder Result

- Operation: generate | update | stopped
- Pull request: <URL or "not created">
- Template: <old full commit or "none"> -> <target full commit>
- Destination: <owner/repository>

### Reconciliation
- Applied: <paths or none>
- Preserved: <paths or none>
- Renamed/deleted: <paths or none>
- Conflicted: <paths and competing intents, or none>

### Repository settings
- <setting>: enabled | unavailable (<reason>) | not requested

### Verification
- `<exact command>`: pass | fail | unavailable (<reason>)

### Pending action
<none, or the exact decision/authorization needed>
```
