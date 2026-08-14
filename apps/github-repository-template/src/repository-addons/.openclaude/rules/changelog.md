---
paths:
  - CHANGELOG.md
---
# Changelog Entries

Write for people deciding whether to upgrade, not for a commit log. Keep a notable change in the pull request that made it, and omit routine refactors, formatting, tests, and CI work.

A change is notable when it changes a user-facing contract:


| Change category | Notable when it…                                                                                    | Typical changelog section              |
| --------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Behavior        | changes what the project does, produces, accepts, or rejects                                        | Added / Changed / Fixed                |
| Interface       | adds, removes, or changes an API, CLI flag, configuration, schema, command, or generated artifact   | Added / Changed / Deprecated / Removed |
| Requirements    | changes supported environments, dependencies, credentials, setup, permissions, or operational steps | Changed / Security                     |
| Default         | changes behavior without an explicit user choice                                                    | Changed                                |
| Reliability     | fixes a bug users can encounter or removes a meaningful failure mode                                | Fixed                                  |
| Security        | reduces exposure, tightens validation, changes trust boundaries, or fixes a vulnerability           | Security                               |
| Compatibility   | changes upgrade, migration, interoperability, or backward-compatibility expectations                | Changed / Deprecated / Removed         |


A PR does not need an entry merely because it:

- has a feat or fix commit type,
- modifies many lines,
- changes internal architecture,
- adds or adjusts tests,
- reformats code or docs,
- changes CI that users do not consume,
- fixes only a developer-local workflow.

Use this for changelog entries:

- Write for humans: clear, concise, user-visible impact; skip routine internal churn.
- Add notable work under `## [Unreleased]`, grouped by one of six headings:
  - `Added` — new capability
  - `Changed` — intentional behavior change
  - `Deprecated` — still works, planned removal
  - `Removed` — no longer available
  - `Fixed` — previously incorrect behavior now corrected
  - `Security` — vulnerability-related change; lead with the CVE if there is one
- Put an item in exactly the category that describes its effect. Describe the user-facing consequence or omit them.
- Mark compatibility breaks inline: `- **Breaking:** …` under `Changed` or `Removed`, and state what users need to change. Link a migration guide if the steps are long.
- Keep entries as outcome statements, not commit messages: say what changed and why it matters, not implementation trivia.
- Do not add empty headings. Keep newest entries first.
