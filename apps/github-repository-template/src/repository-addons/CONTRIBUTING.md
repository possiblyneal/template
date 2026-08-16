# Contributing to REPLACE-PROJECT-TITLE

Thank you for taking the time to contribute. This guide describes how work
actually reaches the default branch here, so that a change you spend effort on
is one the project can accept. Most of what follows is enforced by the tooling
already in this repository rather than by convention, so the fastest path
through review is the one the local checks describe.

<!-- ADOPT: replace REPLACE-PROJECT-TITLE above with the project name, and make
     the opening sentence describe what this project is and who it is for. That
     framing is the one part of this file the template cannot supply. Delete
     this comment when done. -->

By participating you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

<!-- ADOPT: the line above assumes CODE_OF_CONDUCT.md was adopted alongside this
     file. If it was not, delete that line rather than link a file that is not
     there. Delete this comment when done. -->

## Ways to contribute

Code is one path and not the only one. All of these are welcome:

- **Reporting bugs** — a clear report is a contribution in its own right.
- **Proposing enhancements** — describe the problem before the solution.
- **Improving documentation** — corrections, missing setup steps, unclear guides.
- **Triaging issues** — reproducing reports, adding detail, confirming fixes.
- **Reviewing pull requests** — a second reader catches what the author cannot.

<!-- ADOPT: trim this list to the paths this project can actually shepherd.
     Advertising a contribution type no maintainer has time to mentor invites
     work that then stalls, which reads worse than not inviting it. Delete this
     comment when done. -->

## Reporting a bug

Open an issue using the **Bug report** form on the repository's *New issue*
page. The form asks for the specific information a fix depends on — what you
did, what happened, what you expected, and how to reproduce it — so filling it
in fully is what lets someone act on the report instead of asking for more.

Search open and closed issues first; a report that already exists is better
served by adding your detail to it than by opening a second one.

**Do not open a public issue for a security vulnerability.** Report it privately
through the process in our [security policy](SECURITY.md) instead, so a fix can
ship before the weakness is public.

<!-- ADOPT: the security paragraph links SECURITY.md. Keep the link only if that
     addon was adopted. If it was not, replace the link with the private channel
     you actually watch (an email address, a GitHub private advisory), or delete
     the paragraph. A guide that tells someone to report a vulnerability through
     a channel that does not exist is the failure this whole section guards
     against. Delete this comment when resolved. -->

## Proposing an enhancement

Open an issue using the **Feature request** form and describe the problem you
are trying to solve before the change you have in mind — the problem is what a
maintainer weighs, and it often has a solution you would not have reached for.
For anything large, agree on the approach in an issue before writing code, so
review is about the details rather than the direction.

## Setting up your environment

This repository drives every language-specific tool through wrappers in
`scripts/`, so you run the same commands regardless of the stack:

- `scripts/doctor` — check that your local toolchains, dependencies, and hooks
  are present and correctly configured. Run this first.
- `scripts/dev` — start the development server.
- `scripts/fix` — apply formatting.
- `scripts/check` — run the full local gate: format, lint, type check, tests,
  build, and the security audit, across every language present.

`scripts/check` runs the same checks CI does, so a green run locally is the
strongest signal a pull request will pass. Run it before you push.

<!-- ADOPT: the concrete build and test commands for this project arrive with
     its first language manifest — until one exists there is nothing under these
     wrappers to run, and scripts/check reports exactly that. When the manifest
     lands, add the stack-specific steps a newcomer needs (which runtime
     version, how to install dependencies) here. Until then the wrappers above
     stay correct. Delete this comment when the section reflects a real stack. -->

## Making a change

1. **Branch first.** Commits to `main` are blocked by a local pre-commit hook,
   so create a branch before you start rather than discovering the block at
   commit time.
2. **Keep the change focused.** Everything in a pull request should trace to the
   problem it solves; unrelated cleanup and formatting churn belong in their own
   pull request.
3. **Run `scripts/check`** and make it pass before you push.

### Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
`type(optional scope): subject`, a blank line, then a body explaining *why*.
The rule is enforced by commitlint at commit time, so a malformed message fails
at the hook rather than in review. The body is where the reasoning behind a
change survives — write it for the person who has to understand this commit
later, and that person is often you.

## Opening a pull request

Push your branch and open a pull request against the default branch. The
repository's pull request template asks you to state what changed and why, link
the issue or goal, and provide evidence that it works — fill it in rather than
deleting it, because those are the questions a reviewer would otherwise have to
ask.

- All CI checks must pass.
- A reviewer confirms the change against the linked issue or goal.
- Keep your commit history clean — each commit a coherent step, each message
  following the convention above. Depending on how this repository merges pull
  requests, those commits may land on the default branch as they are.

Address review feedback by pushing additional commits to the same branch.

## Getting help

If you are unsure where to start or whether an idea fits, open an issue and ask
before investing the effort. A question asked early is cheaper than a pull
request rewritten late.
