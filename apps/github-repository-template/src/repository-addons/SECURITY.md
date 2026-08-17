# Security Policy

This document is how a security vulnerability reaches the maintainers privately,
and what happens after it does. Its failure mode is being trusted: a policy that
routes a report to a channel nobody watches, or promises a response nobody keeps,
is worse than no policy at all, because a reporter relies on it at the one moment
it matters and the weakness goes public instead. Every commitment below is one
this project can actually honour, or it does not belong here.

GitHub reads this file from `.github/`, then the repository root, then `docs/` --
first one found wins. It ships at the root; move it if you want it elsewhere,
but do not keep two copies, because only the first is ever read. When present,
GitHub links it from the repository's **Security** tab and from the banner shown
when someone opens a new issue.

## Reporting a vulnerability

**Do not report a security vulnerability in a public issue, pull request, or
discussion.** A public report describes the weakness to everyone who can read the
repository -- including anyone who would exploit it -- before a fix exists. Report
it privately instead:

Email the details to [REPLACE: the private security address you monitor]. This is
the one line in this file that reports itself unfilled: it renders in the
published policy, so an unadopted copy tells a reporter to email a placeholder
rather than silently swallowing the report.

<!-- ADOPT: two decisions are hiding in the paragraph above, and the manifest
     entry for this file spells both out.

     1. The channel. The bracketed address is one option. The other is GitHub's
        Private Vulnerability Reporting: a "Report a vulnerability" button on the
        repository's Security tab that opens a private advisory, no shared inbox
        required. It has to be turned on first (Settings -> Advanced Security ->
        Private vulnerability reporting) and is offered on public repositories,
        or private ones with GitHub Advanced Security -- not on a private
        repository on the free plan. Nothing in this repository reports whether
        it is on, so if you choose it, enable it and then rewrite this paragraph
        to point at the button, deleting the email line. If you keep email, fill
        the bracket with an address someone actually reads.

     2. Whichever you keep, delete the other, so the file names one channel and
        not two. Delete this comment once both are resolved. -->

To help a fix land quickly, include as much of the following as you can:

- the affected version, tag, or commit, and the platform you saw it on;
- steps to reproduce, or a proof of concept;
- the impact -- what an attacker gains, and under what conditions;
- any mitigation or workaround you already know of.

## What to expect

- An acknowledgement that your report arrived, within a stated window.
- An assessment of whether it is a vulnerability and how severe, kept in the
  private thread with you.
- A fix developed under coordinated disclosure, and credit to you when it ships
  unless you ask to stay anonymous.

<!-- ADOPT: the acknowledgement window is a promise a reporter measures you
     against, so state a number only if you will keep it -- "within three
     business days" that slips to three weeks is the same broken trust this file
     exists to prevent, discovered at the worst moment. If you cannot commit to a
     window, say "as soon as we are able" rather than inventing one. Delete this
     comment when the wording is a commitment you can hold. -->

## Supported versions

Security fixes are applied to the versions below. Anything not listed here has
reached end of life and will not receive them; upgrade to a supported version
before reporting.

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

<!-- ADOPT: that table is a plausible-looking guess, not a fact about this
     project -- it validates and renders while telling users the wrong versions
     are maintained, which is a silent failure rather than an error. Replace its
     rows with the versions this project actually supports. A project with a
     single line of releases, or one still before its first release, is better
     served by deleting the table and stating the policy in a sentence: "The
     latest release is supported; older releases are not." Delete this comment
     when the section is true. -->

## Disclosure

This project follows coordinated disclosure. Please give the maintainers a
reasonable period to develop and release a fix before disclosing the issue
publicly; the private thread on your report is where that timeline is agreed.
Working this way keeps users protected during the window when a vulnerability is
known but not yet patched.
