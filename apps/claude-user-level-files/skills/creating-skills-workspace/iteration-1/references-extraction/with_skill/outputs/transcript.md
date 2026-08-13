# Improvement Plan for verbose-skill

I read `/home/neal/.claude/skills/creating-skills/evals/files/verbose-skill/SKILL.md` and checked its size.

## Did I identify the line count problem (>500 lines)?

Yes. The current `SKILL.md` is 548 lines, so it exceeds the recommended 500-line limit for a skill body. This is the main structural problem: too much reference material is loaded every time the skill triggers.

## Approach: compress inline, move to references/, or both?

Both.

I would keep the core workflow, default report format, key writing rules, and essential error-handling guidance inline in `SKILL.md`, but compress them substantially. I would move detailed command/API/export/config reference material and extended examples into `references/` files so they are loaded only when needed.

The goal is not to delete useful information. The goal is to make `SKILL.md` a concise operating guide and move lower-frequency details into on-demand references.

## Sections to move to references/ vs trim inline

### Move to `references/`

I would move these sections out of `SKILL.md`:

1. `API Reference` lines 326-486
   - Move to `references/data-source-reference.md` or split by source:
     - `references/git-reference.md`
     - `references/jira-reference.md`
     - `references/slack-reference.md`
   - This includes the long Git command catalog, Jira API/JQL details, Jira pagination notes, and Slack export structure.

2. `Configuration` lines 487-518
   - Move to `references/configuration.md`.
   - The inline skill only needs a short note that environment variables/config files can be used, plus a pointer to the reference.

3. `Frequently Asked Questions` lines 520-548
   - Move to `references/faq.md` if the answers are worth preserving.
   - Alternatively, fold the most important FAQ items into concise inline guidance and move only the GitLab/multi-repo/statusignore details to the reference.

4. Extended examples lines 236-284
   - Move full examples to `references/examples.md`.
   - Keep only one compact inline example or a tiny before/after showing the desired abstraction level.

5. Advanced usage lines 286-306
   - Move to `references/advanced-usage.md`.
   - Calendar, automated weekly runs, and PR review API lookup are useful but not necessary for every status-report task.

### Trim inline

I would trim these sections while keeping their core guidance in `SKILL.md`:

1. `Background and Context` lines 9-13
   - Reduce to one sentence or remove entirely. The skill does not need a general explanation of why weekly reports exist.

2. `Data Sources` lines 15-108
   - Keep a short data-gathering workflow:
     1. Use Jira as structured backbone when available.
     2. Enrich with git commits.
     3. Add Slack blockers/decisions if provided.
     4. Deduplicate and flag unclear items.
   - Move detailed commands and API calls to references.

3. `Report Format` lines 109-142
   - Keep the default report template inline because it is central to the task.
   - Remove emoji if the target audience may need plain Markdown, or make emoji conditional on user preference/team style.
   - Keep the good/bad abstraction example, but shorten it.

4. `Writing Guidelines` lines 144-180
   - Keep the audience, tone, blocker, and confidentiality guidance, but compress each into bullets.

5. `Customization` lines 181-200
   - Keep the rule to use a user-provided template if supplied.
   - Keep the team-report branching question only as a concise prompt.
   - Move recurring-report history/diff suggestions to advanced usage.

6. `Error Handling` lines 202-234 and `Troubleshooting` lines 308-324
   - Merge into a single concise `Edge cases` section.
   - Keep only actionable behaviors: no git history, no Jira access, ambiguous commits, empty weeks, duplicates, wrong time period, too vague/too long.

## Proposed reference file layout

I would use this structure:

```text
verbose-skill/
├── SKILL.md
└── references/
    ├── data-source-reference.md
    ├── examples.md
    ├── configuration.md
    ├── advanced-usage.md
    └── faq.md
```

If `data-source-reference.md` becomes longer than about 100 lines, I would split it into:

```text
references/git-reference.md
references/jira-reference.md
references/slack-reference.md
```

That split may be better because the agent can load only the relevant source-specific reference.

## Would the resulting SKILL.md be under 500 lines?

Yes. With the API reference, configuration, FAQ, advanced usage, and extended examples moved out, `SKILL.md` would likely drop from 548 lines to roughly 120-180 lines. Even with pointers to references and a compact default template, it should comfortably stay under 500 lines.

## Would I add pointers in SKILL.md to each new reference file?

Yes. I would add explicit on-demand pointers in `SKILL.md`, for example:

- Read `references/git-reference.md` when you need more than the default git log command or need to inspect ambiguous commits.
- Read `references/jira-reference.md` when the user wants Jira integration or Jira API/JQL details are needed.
- Read `references/slack-reference.md` when the user provides a Slack export or asks to extract blockers/decisions from Slack data.
- Read `references/examples.md` when the user asks for examples or when choosing between report styles.
- Read `references/configuration.md` when setting up environment variables or a reusable config file.
- Read `references/advanced-usage.md` for calendar, scheduled report, or PR-review integrations.
- Read `references/faq.md` for multi-repo, GitLab, colleague reports, exclusions, or custom date-window questions.

These pointers should be short and conditional so the agent does not load every reference by default.

## Summary

The improvement plan is to convert `SKILL.md` from a comprehensive manual into a concise execution guide. Keep the core status-report workflow inline; move detailed source references, examples, configuration, FAQ, and advanced integrations to `references/`; and add clear conditional pointers so each reference is loaded only when relevant.
