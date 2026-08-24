<!-- A named pull request template. GitHub fills a PR body from this file only
     when the URL asks for it by name:

       ?expand=1&template=hotfix.md

     Nothing offers it in the UI. The default template at
     .github/PULL_REQUEST_TEMPLATE.md is what a PR gets otherwise, so link this
     one from there if it should be reachable by clicking.

     This template is shorter than the default on purpose. It is not a lighter
     standard -- it asks the questions that are answerable while something is
     broken, and defers the rest to the follow-up issue at the bottom. -->

## What is broken

<!-- The user-visible failure, in production, right now. Not the code defect --
     what someone is unable to do. -->

Impact:

<!-- Who is affected and how badly: all users or a subset, data loss or
     degradation, whether a workaround exists. -->

Since:

<!-- When it started, and the deploy, release, or change that introduced it if
     that is known. "Unknown" is an acceptable answer here and a useful one. -->

Evidence:

<!-- The alert, the log, the error rate, the report. Link it. -->

## Why this cannot wait

<!-- What going through the normal path would cost. If the honest answer is that
     it could wait, use the default template instead -- a hotfix that did not
     need to be one spends the exception for the next real emergency. -->

## The fix

<!-- What this change does, and why it is the smallest change that stops the
     bleeding. A hotfix that also refactors is two changes, and the second one
     is untested. -->

Root cause:

<!-- If known, state it. If not, say so plainly and say what this fix does
     instead -- suppressing a symptom is a legitimate hotfix and a dangerous
     thing to leave undeclared. -->

## Verification

Done:

<!-- What was actually run, and where. Link the CI run if it finished. -->

Skipped:

<!-- What the normal process would have caught that this did not run: review
     depth, integration tests, staging, manual QA. This section is the point of
     the template. An empty one claims the shortcut was free. -->

## Rollback

<!-- How to undo this specific change if it makes things worse, and how quickly.
     Whether reverting returns to the broken state or to a worse one. -->

## Follow-up

Issue:

<!-- Link the issue tracking the real fix, the missing test, and the postmortem.
     File it before merging this -- a hotfix whose follow-up is written after
     the incident closes is a follow-up nobody writes. -->

## Checklist

- [ ] The change is the minimum that stops the failure; nothing else rides along.
- [ ] Skipped verification is listed above, honestly.
- [ ] A follow-up issue exists and is linked.
- [ ] This lands on every branch that needs it, not only the release line.
