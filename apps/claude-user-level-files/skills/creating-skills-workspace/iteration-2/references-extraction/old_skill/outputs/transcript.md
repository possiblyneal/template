# Improvement plan for verbose-skill

Target skill: `/home/neal/.claude/skills/creating-skills/evals/files/verbose-skill/SKILL.md`

I read the skill and did not edit it.

## Required answers

- Line count: 548 lines.
- Exceeds 500 lines: Yes. It is 48 lines over the recommended SKILL.md body limit.
- Approach: Both compress inline and move detail to `references/`.
- Will result be under 500 lines: Yes. The proposed split should reduce `SKILL.md` substantially, likely to roughly 180-230 lines depending on how much example material remains inline.
- Will I add conditional pointers in `SKILL.md` to each reference file: Yes. Each moved reference should have an explicit conditional pointer telling the agent when to read it.

## Improvement plan

The skill is currently useful but too verbose for always-loaded skill context. The main issue is not that the content is bad; it is that operational references, examples, API details, configuration notes, and FAQs are all loaded every time the skill triggers. I would keep the core workflow and report-writing guidance inline, then move source-specific and edge-case details into on-demand reference files.

## Keep and compress inline in SKILL.md

Keep these sections inline, but rewrite them more tightly:

1. Frontmatter and title
   - Keep the existing name.
   - Tighten the description if desired, but the current trigger intent is clear.

2. Purpose / operating principle
   - Replace the long background with 2-3 sentences: gather evidence from git/Jira/Slack, reconcile it, produce a stakeholder-ready weekly update, and avoid inventing missing context.

3. Core workflow
   - Add a concise step-by-step procedure:
     1. Identify date range and audience.
     2. Gather available sources.
     3. Reconcile items by ticket/feature/workstream.
     4. Draft the report in the requested or default format.
     5. Flag missing access, unclear commits, sensitive details, or manual-review items.

4. Default report format
   - Keep the status report template inline because it is central to the skill output.
   - Trim explanatory prose around the template.
   - Consider removing emoji from headings if the target user prefers plain professional reports, or mention that headings can be adapted to the user's style.

5. Writing guidance
   - Keep compact guidance on audience level, tone, blockers, confidentiality, and abstraction level.
   - Keep one good/bad example for abstraction level and one good/bad blocker example.
   - Remove repeated general status-report explanation.

6. Source reconciliation rule
   - Keep a short inline rule: Jira is the structured backbone when available; enrich with commits; use Slack for blockers/decisions; unmatched commits become unlabeled work items.

7. Essential error handling
   - Keep concise inline defaults for no git history, no Jira access, ambiguous commits, duplicate work items, and empty weeks.
   - Trim exact user-facing scripts and long explanations where possible.

8. Reference index
   - Add a short `References` section listing each reference file and when to read it.

## Move to references/

Move detailed material that is useful only in specific circumstances:

1. `references/git.md`
   - Move most of `Git History` and all of `API Reference > Git Commands Reference`.
   - Include command patterns for date ranges, author filtering, stats, branches, and unclear commit investigation.
   - Conditional pointer: read when gathering or interpreting git history, especially for multi-repo, author-filtered, or ambiguous commit cases.

2. `references/jira.md`
   - Move most of `Jira Tickets` and all of `API Reference > Jira API Reference`.
   - Include auth expectations, JQL examples, fields to extract, pagination, and fallback behavior.
   - Conditional pointer: read when the user provides Jira access, Jira URLs/tickets, or asks to include ticket/sprint context.

3. `references/slack.md`
   - Move `Slack Summaries` and `API Reference > Slack Export Format`.
   - Include JSON export shape, user lookup, timestamp conversion, and blocker/decision/action-item extraction patterns.
   - Conditional pointer: read when the user provides Slack exports, pasted Slack messages, or asks to include blockers/decisions from Slack.

4. `references/customization.md`
   - Move `Customization`, `Advanced Usage`, `Configuration`, and relevant FAQ entries.
   - Include custom templates, recurring reports, team reports, calendar notes, PR review inclusion, automation, env vars/config file, multiple repositories, colleague reports, exclusions, and custom date windows.
   - Conditional pointer: read when the user asks for non-default templates, recurring automation, team/colleague reports, config-driven reports, PR-review work, calendar notes, exclusions, or multi-repo handling.

5. `references/examples.md`
   - Move the two full examples.
   - Keep perhaps one tiny inline example in SKILL.md if needed, but full examples should be on demand.
   - Conditional pointer: read when the user asks for examples, when calibrating report style, or when the generated draft feels under-specified.

6. `references/troubleshooting.md`
   - Move detailed `Troubleshooting` and FAQ items that are not part of the common path.
   - Could be merged into `customization.md` if keeping fewer files is preferred, but a separate troubleshooting reference makes conditional loading clearer.
   - Conditional pointer: read when the user reports the generated report is too long, too vague, has wrong dates, duplicates work, or includes unwanted items.

## Trim rather than move

Trim or remove these inline passages instead of preserving them verbatim:

- The broad `Background and Context` explanation. Replace with a compact purpose statement.
- Repeated statements that raw data is verbose and reports need to be readable. Keep the principle once.
- Generic explanations before simple commands, where the command and a short note are enough.
- Overly detailed recurring-report suggestions unless the user asks for automation or history.
- FAQ answers that duplicate earlier guidance, especially terrible commit messages, custom date windows, and multiple repositories.
- Long prose around report length and vagueness. Convert to one-line troubleshooting rules or move to `references/troubleshooting.md`.

## Proposed SKILL.md shape after refactor

```markdown
---
name: verbose-skill
description: Generates weekly status reports from git history, Jira tickets, and Slack summaries. Use when a user wants to write a status report, weekly update, standup summary, or project progress report.
---

# Weekly Status Report Generator

## Goal
## Workflow
## Source precedence and reconciliation
## Default report format
## Writing guidelines
## Common fallbacks
## References
```

This shape keeps the always-loaded instructions focused on what the agent must do every time, while pushing source-specific mechanics and examples into conditional context.

## Conditional pointers to add in SKILL.md

Yes, I would add conditional pointers in `SKILL.md` to each reference file, for example:

- Read `references/git.md` when collecting git history, handling multiple repositories, filtering by author/date, or investigating unclear commits.
- Read `references/jira.md` when Jira tickets, sprint data, or Jira API access are available or requested.
- Read `references/slack.md` when Slack exports or pasted Slack messages are provided, especially for blockers, decisions, and action items.
- Read `references/examples.md` when the user asks for examples or when you need to calibrate report tone/detail.
- Read `references/customization.md` when the user asks for custom templates, recurring/team reports, calendar/PR-review inclusion, automation, configuration, exclusions, or non-default scope.
- Read `references/troubleshooting.md` when the draft is too long, too vague, has wrong dates, duplicates items, or includes unwanted work.

## Expected result

After moving detailed references and compressing inline guidance, `SKILL.md` should be comfortably under 500 lines while retaining the behavior-critical instructions in the always-loaded body. The reference files preserve useful detail without spending context on Jira API syntax, Slack export schemas, long examples, and configuration options when those are irrelevant to the user's immediate status-report request.
