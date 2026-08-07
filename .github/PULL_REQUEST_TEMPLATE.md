## Summary

<!-- What changed and why. Two or three sentences. -->

## Linked issue or goal

<!-- URL or exact ticket ID, so a reviewer can fetch the original requirements and
     check this PR against what was actually asked for. Write "none" if there is
     no issue, and state the goal here instead. -->

## Verification

Evidence link:

<!-- Link the CI run, or paste raw command output. A reviewer should be able to
     confirm this PR works without taking anyone's word for it. Summaries of
     results are not evidence; the run or the output is. -->

Not verified:

<!-- What did you NOT check, and why? Untested paths, skipped cases, anything
     that only ran locally, anything you could not exercise. "Nothing" is a valid
     answer only if it is true. This section is more useful than the one above. -->

## Risk

Answer each. These are checkable against the diff.

- Database migration or schema change: yes / no
- Authentication, authorization, or permission logic touched: yes / no
- Secrets, credentials, or security config touched: yes / no
- Public API, CLI, or on-disk format changed in a way existing callers would notice: yes / no
- Dependencies added, removed, or upgraded: yes / no
- Deletes or overwrites existing data: yes / no

<!-- For every "yes", explain below what specifically changed and what happens if
     it is wrong. -->

Rollback:

<!-- How to undo this. If reverting the commit is enough, say so. If not, list
     the migration reversal, config change, or data restore required. -->

## Decisions a reviewer should check

<!-- What did you choose that could reasonably have gone another way? What were
     you unsure about? Where would a second opinion be most valuable?

     A diff shows what changed. It does not show what was considered and
     rejected, what was guessed, or which assumption the whole change rests on.
     Put those here. Leaving this empty claims the change had no judgment calls
     in it, which is rarely true. -->

## Scope

<!-- Anything touched that is not obviously part of the linked issue, and why it
     was necessary. Unrelated cleanup, drive-by refactors, and formatting churn
     belong in their own PR. -->

## Screenshots or demos

<!-- Required for UI changes. Otherwise write N/A. -->

## Checklist

- [ ] Verification section links a CI run or contains raw output.
- [ ] Every "yes" under Risk is explained.
- [ ] Decisions section lists real judgment calls, or the change genuinely had none.
- [ ] No secrets, tokens, passwords, or private data in the diff or in this description.
