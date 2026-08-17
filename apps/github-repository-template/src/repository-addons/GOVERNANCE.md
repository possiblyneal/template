# Governance

This document records how decisions are made in this project: who has the final
say, how routine choices get made without invoking it, and what changes when the
project grows past the point this model fits. Like every file here it is only
worth having if it is true -- a governance document describing a process the
project does not actually follow promises contributors a say they do not have,
or an authority nobody exercises, and the gap surfaces at the first real
disagreement, which is the worst moment to discover it.

## The short version

This project is led by a single maintainer -- [REPLACE: the maintainer with final authority, as a GitHub @handle] -- who holds final authority over its
direction, its releases, and this document.

<!-- ADOPT: the bracket above is the one line that must be filled before this
     file is true. Nothing validates GOVERNANCE.md the way GitHub validates
     CODEOWNERS, so an unfilled handle renders in the published document and no
     tool reports it -- a human is the only check. Put the account that actually
     decides here. On a personal repository that is usually the repository
     owner; on an organization repository it is a person inside it, not the
     organization, because an organization does not make decisions. -->

## Roles

- **Maintainer** -- the single authority named above. Sets direction, reviews
  and merges contributions, cuts releases, and has the final word when a
  decision has to be made. Also the person who amends this document.
- **Contributors** -- anyone who opens an issue or a pull request. Contributors
  propose, discuss, and review; taking part needs no permission and no title.

## How decisions are made

Day to day, this project runs on lazy consensus: a proposal made in the open --
an issue or a pull request -- that draws no sustained objection is taken as
agreed, and whoever proposed it may act on it. Most changes never need more than
this.

When a decision cannot be reached that way -- a disagreement that does not
settle, or a choice that must be made deliberately rather than allowed to emerge
-- the maintainer decides, and that decision is final. Deciding in the open is
the expectation: the reasoning goes in the issue or pull request where the
question was raised, so the people a decision affects can find it later.

## Conduct and disputes

Disagreement about the work is normal and settles as above. Conduct is a
separate matter: it is governed by the project's [Code of
Conduct](CODE_OF_CONDUCT.md), and a violation is reported through the channel
that document names, not through the governance process here.

<!-- ADOPT: the Code of Conduct link assumes CODE_OF_CONDUCT.md was adopted
     alongside this file. Keep it only if that is true; delete this paragraph
     otherwise, rather than link a file that is not there. -->

## Changing this document

This document is amended the way anything else changes: a pull request the
maintainer approves.

<!-- ADOPT: before shipping, confirm the single-authority model this file
     describes actually matches how the project is run. If decisions are already
     shared among several accountable people, this template is the wrong shape --
     it states an authority one of them does not hold alone. Replace it with a
     multi-maintainer model rather than filling it in; CNCF publishes templates
     for the common ones (a self-selecting maintainer council, an elected
     steering committee, an umbrella of subprojects) at
     github.com/cncf/project-template. Delete this comment once the model is
     confirmed or replaced. -->

## When one maintainer becomes several

The moment a second person shares the decision -- not just contributes, but is
accountable for the whole -- this model stops describing the project, and
leaving it as written hands one person an authority the others in practice also
hold. That is the point to rewrite this file: name the maintainers, say how one
is added and how one steps down, and replace "the maintainer decides" with how
the group decides when it is split. Until then, a single accountable person is a
legitimate and common way to run a project, and the honest thing is to say so
plainly rather than describe a committee that does not meet.
