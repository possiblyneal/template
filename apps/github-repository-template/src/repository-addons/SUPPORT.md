# Support

This document routes someone who needs help to a place that can give it, and
keeps the issue tracker for bugs and feature requests. Its failure mode is
quiet: a channel listed here that nobody reads sends a person away believing
they have asked, and the question is answered by no one. Every channel below has
to be one somebody actually watches, or it does not belong here.

GitHub looks for this file in the repository root, in `docs/`, and in
`.github/`, and links it from the banner shown when someone opens a new issue.
It ships at the root; move it if you want it elsewhere, but keep exactly one
copy. GitHub documents no precedence between those three locations, so two
copies means the one someone reads is the one you did not update.

## Before you ask

- Read the README, and any documentation it links to.
- Search the existing issues, open and closed. A closed issue often carries the
  answer and the reason.

## Where to ask

Ask here: [REPLACE: the support channel you actually read]. This is the one line
in this file that reports itself unfilled: it renders in the published document,
so an unadopted copy tells someone to take their question to a placeholder
rather than silently swallowing it.

<!-- ADOPT: name the channels that exist, and delete this comment once they do.
     Common choices are GitHub Discussions (enable it first -- Settings ->
     General -> Features -> Discussions -- or the link points at a tab that is
     not there), a chat server, a mailing list, or a public issue for questions
     when the project is small enough that one tracker is honest.

     Whichever you name, uncomment the contact_links block already sitting in
     .github/ISSUE_TEMPLATE/config.yml and point it at the same destination.
     That surfaces it on the template chooser, one step before the banner that
     links this file, which is where someone with a question rather than a bug
     is still deciding what to open. Two destinations shown seconds apart is
     worse than one. -->

Open an issue instead when you have a reproducible bug or a concrete feature
request; the issue forms will ask for what a maintainer needs.

Do not report a security vulnerability through any channel on this page. Every
one of them is public, and a vulnerability is disclosed by the act of reporting
it there.

<!-- ADOPT: point that paragraph somewhere. If SECURITY.md was adopted, link it
     and delete this comment. If it was not, this file is the only page a
     reporter reads, so name a private address here instead. -->

## What to include

A question that arrives with its context gets answered once instead of three
times:

- what you are trying to do, not only the error you hit;
- the version, tag, or commit, and the platform you are on;
- the exact command or code, and the output it produced, with tokens, keys,
  hostnames, and anything else private removed -- this is a public channel;
- what you have already tried.

## What to expect

<!-- ADOPT: this section is a promise someone measures the project against.
     The shipped wording commits to nothing specific on purpose, which is honest
     for a project maintained in spare time. Replace it with a real commitment
     only if it will be kept -- a stated response time that slips is worse than
     no statement, because someone waits on it instead of looking elsewhere.
     Delete this comment when the wording is true of this project. -->

This project is maintained on a best-effort basis. Questions are answered when a
maintainer has time, and an unanswered question is not a judgement about the
question. Support is not a commercial service and carries no response-time
guarantee.
