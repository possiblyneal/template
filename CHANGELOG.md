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

### Changed

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

[Unreleased]: https://github.com/possiblyneal/template/commits/main
