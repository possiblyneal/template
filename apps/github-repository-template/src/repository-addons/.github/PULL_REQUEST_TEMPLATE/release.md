<!-- A named pull request template. GitHub fills a PR body from this file only
     when the URL asks for it by name:

       ?expand=1&template=release.md

     Nothing offers it in the UI. The default template at
     .github/PULL_REQUEST_TEMPLATE.md is what a PR gets otherwise, so link this
     one from there if it should be reachable by clicking. -->

## Release

Version:

<!-- The exact tag this release will carry, e.g. v1.4.0. -->

Range:

<!-- The compare link or commit range this release covers. A reader should be
     able to see everything shipping without reconstructing it. -->

## What is shipping

<!-- Written for whoever upgrades, not for whoever reviews the diff. Group by
     what a user would notice: new capability, changed behavior, fixes. -->

## Breaking changes

<!-- Every change existing callers would notice: removed or renamed API, changed
     defaults, changed on-disk or wire format, raised minimum versions. For each
     one, what a caller has to do about it. Write "none" only if it is true --
     a major version with nothing here is a claim worth checking. -->

## Migration required

<!-- Database migrations, config a deployer must add, data that must be
     backfilled, and the order these must happen in relative to the deploy. -->

## Verification

<!-- Link the CI run for the release commit. Say what was exercised beyond CI:
     the built artifact installed from a clean environment, the upgrade path
     from the previous version, a staging deploy. Building is not installing,
     and installing is not upgrading. -->

## Rollback

<!-- What undoing this release takes once it is published. Note anything that
     cannot be undone: a published package version that cannot be reused, a
     migration with no down path, an announcement already sent. -->

## Checklist

- [ ] The changelog has an entry for this version, and it matches the tag.
- [ ] The version is written wherever the project records it, and consistently.
- [ ] Every breaking change above appears in the changelog's breaking section.
- [ ] CI is green on the exact commit being tagged.
- [ ] Nothing in this release is undocumented that a user would need documented.
