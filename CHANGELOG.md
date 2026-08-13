# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `CHANGELOG.md` in the template payload, so a generated repository can record a
  change from its first commit rather than from its first release.
- Conventional Commits, enforced by commitlint at the `commit-msg` hook. A
  malformed commit message now fails locally instead of reaching review, and
  the commit type gives the changelog a signal about which changes are likely
  to owe an entry. Rules live in `.commitlintrc.yaml`. An existing clone needs
  `pre-commit install` run once more to pick up the second hook; `scripts/doctor`
  fails until it has been.
- `scripts/repo-settings check` reports whether squash merging is disabled. A
  squashed commit takes its subject from the pull request title, which no local
  hook can see, so the commit-message rules hold only while that setting is off.

### Changed

- User-level Claude Code configuration is symlinked from `~/.claude` into
  `apps/claude-user-level-files/src/` rather than copied, so settings changes
  arrive as reviewable diffs. On that machine, `/model` now writes to the
  working tree and a branch switch changes live configuration.
- The structure doc groups the files a repository adds later by the occasion each
  one answers, rather than as a single checklist for going public.
- `scripts/release` publishes the GitHub release rather than stopping short of
  it, using the `CHANGELOG.md` section for the tag as the release body. A tag
  whose section is missing or empty fails the release, so the tree and the
  releases page cannot disagree. `release.yml` holds `contents: write` to create
  the release, where it previously needed only `contents: read`.

### Removed

- The empty `tools/` directory from the payload. Where a helper that must be
  built before it runs belongs is still documented; the directory no longer
  ships to assert that every generated repository will grow one.

### Fixed

- `scripts/check` runs the pre-commit hooks over untracked files as well as
  tracked ones. `--all-files` enumerates through git, so a file written but not
  yet staged used to pass the gate without being read and then fail the hook at
  commit time — the blind spot sitting exactly where new files are.
- `.commitlintrc.yaml` is owned as a managed path, so a payload fix to the
  commit-message rules reaches a generated repository instead of being silently
  skipped as product. Root dotfiles match no directory pattern and need a rule
  each; the reference manifest in the repo-builder skill was missing one too.

[Unreleased]: https://github.com/possiblyneal/template/commits/main
