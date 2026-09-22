---
type: Architecture Decision Record
title: Select the Runner Through a Repository Variable
description: Every workflow job reads `vars.RUNNER` and falls back to `ubuntu-latest`, so a repository redirects its own CI without editing a workflow the template owns.
scope: [global]
tags: [ci, template-payload]
generated: { by: "agent/claude-opus-5", at: "2026-09-22T01:53:21Z" }
superseded_by:
status: accepted
---

# Select the Runner Through a Repository Variable

## Decision

Every job in the four shipped workflows reads its runner from a
repository variable rather than naming one:

```yaml
runs-on: ${{ vars.RUNNER || 'ubuntu-latest' }}
```

`codeql.yml`'s `analyze` job is the one exception in form, because its
runner comes from a matrix `scripts/detect` builds:

```yaml
runs-on: ${{ matrix.runner == 'ubuntu-latest' && vars.RUNNER || matrix.runner }}
```

An unset or empty `RUNNER` is falsy in a GitHub expression, so both
forms collapse to what they said before. This decides where a job runs
and nothing else: it does not add a self-hosted runner, does not
recommend one, and does not change what any job does once it starts.

## Context

GitHub bills Actions minutes only for private repositories; a public
one runs free and unlimited. The free plan's monthly allowance is
therefore consumed entirely by private repositories, and this
operator's ran out with four private repositories averaging over 250
workflow runs a month between them. Paying for more minutes was
declined, and stopping the work was not acceptable, so the runs had to
move to hardware the operator already owns.

A self-hosted runner is free and unmetered, which answers the
allowance. It does not answer how a repository *chooses* it. Before
this decision the choice was a literal in a workflow file, and those
four workflows are payload the template owns: a repository that edited
`runs-on` would collide with the template on the next update, in a file
where a collision has to be reconciled by hand. Two of the four
repositories are generated from this template and would hit that; the
other two are not, and would each carry their own hand edit forever.

The variable moves the choice out of the file. The template keeps
owning the workflow, the repository owns one variable, and an update
carries the knob rather than overwriting the answer.

The default has to stay `ubuntu-latest`, and that is the part worth
reading twice. A self-hosted runner on a **public** repository lets any
fork's pull request execute arbitrary code on the host, and this
template's own repository is public, as is any generated repository
that goes public to get secret scanning, push protection, code scanning
and rulesets — the four things a public destination unlocks on this
plan. Defaulting to hosted means the dangerous configuration is never
what a repository gets by accident; it is something an operator sets
deliberately, per repository, on a repository they have judged safe.

## Alternatives Considered

- **Switch the workflows to `self-hosted` outright.** Rejected: it
  ships the fork-execution exposure above to every generated
  repository, including the public ones, and to this repository. The
  exposure is the reason the default is not negotiable.

- **Let each repository edit `runs-on` by hand.** Rejected: it puts a
  destination edit inside a managed payload file, so every template
  update to any of these four workflows becomes a collision to
  reconcile in a repository that had already answered the question.
  That is precisely the cost the ownership rules in
  `apps/repo-builder/src/references/lifecycle.md` exist to avoid.

- **Add the variable to the matrix in `scripts/detect` instead.**
  Rejected: `_language_capabilities_codeql_matrix` emits JSON consumed
  as matrix values, and GitHub does not re-evaluate an expression
  embedded in one. A `${{ … }}` written there would reach `runs-on` as
  a literal string. The comparison in `analyze` is where the choice can
  actually be made.

- **A per-job variable, so one workflow can be redirected without the
  others.** Rejected as speculative: nothing has asked to split them,
  and four variables per repository is four places for the answer to
  drift. One variable is the minimum that solves the stated problem,
  and splitting it later is a smaller change than unsplitting it.

## Consequences

A private repository out of minutes sets one variable and stops
consuming them:

```
gh variable set RUNNER --body self-hosted -R <owner>/<repository>
```

Nothing else changes, and unsetting the variable moves it back.

**A self-hosted runner is not a drop-in for `ubuntu-latest`, and this
decision does not pretend otherwise.** The hosted image ships a large
preinstalled toolchain and starts clean on every run; a self-hosted
machine has whatever it has and keeps state between runs. The
prerequisite is concrete: `git`, `gh`, `jq`, and `pipx` must be on the
machine, plus every toolchain the languages present need. `pipx` is on
that list for a language-independent reason — `ci.yml` installs
pre-commit with it before any toolchain is set up, and pre-commit runs
whatever the languages are. `codeql.yml`'s
`scanning` job is the first to notice a missing `gh` — one `gh api` call
is its whole body, and it is a required check on `main`, so a host
without `gh` turns a stand-down into a hard failure on exactly the
private repository this decision was written for. `release.yml` is the
next, since a release built on a dirty machine is a release built from
unknown inputs. Each repository that sets the variable owes itself one
green run before trusting it.

`RUNNER` names one label, not a set. `runs-on` takes the expression
result as a single literal, so a comma-joined value matches no runner
and the job queues until `timeout-minutes`. Selecting on several labels
would need `fromJSON`, which nothing has asked for.

Swift keeps its hosted macOS runner whatever `RUNNER` says, because the
matrix comparison lets that entry through untouched. A repository whose
CodeQL matrix includes Swift therefore still spends minutes on that one
job, and a Linux `RUNNER` cannot absorb it. That is correct rather than
unfortunate — the alternative is failing a scan that needs macOS.

The expression form `A && B || C` is doing real work in `analyze` and
is easy to break. Anyone editing it should know that an empty variable
is falsy, which is what makes the fallback collapse cleanly; rewriting
it as a ternary-looking construct that treats `''` as a value
reintroduces the bug this form avoids.
