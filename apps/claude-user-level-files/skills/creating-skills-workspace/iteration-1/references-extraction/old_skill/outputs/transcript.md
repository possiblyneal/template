# Improvement Plan for `verbose-skill`

## Did I identify the line count problem (>500 lines)?

Yes. The current `SKILL.md` is 548 lines in the numbered read output, so it exceeds the recommended under-500-line limit for a skill body.

## Approach: compress inline, move to `references/`, or both?

Both.

The core skill should stay in `SKILL.md`: trigger framing, the default workflow, output format, writing guidance, source-reconciliation rules, and the most common failure-handling guidance. Long reference material, examples, API details, and optional advanced/integration content should move into `references/` so the model loads it only when needed.

This preserves useful detail without spending context on rarely needed material every time the skill triggers.

## Sections to move to `references/` vs trim inline

### Keep inline, but compress

- `# Weekly Status Report Generator` introduction: reduce to a short purpose statement.
- `Background and Context`: trim heavily or remove. The model does not need a general explanation of why status reports exist.
- `Data Sources`: keep a compact source-priority workflow:
  - default to last 7 days if unspecified
  - gather git history
  - optionally enrich with Jira
  - optionally use pasted Slack/export content for blockers, decisions, and action items
  - reconcile duplicate work across sources
- `Report Format`: keep the standard template inline because it is central to the output.
- `Writing Guidelines`: keep concise rules for audience, tone, abstraction level, blockers, and confidentiality.
- `Customization`: keep only essential instructions:
  - use a provided template if supplied
  - ask aggregation preference for team reports
- `Error Handling` and `Troubleshooting`: merge into a short inline “When data is missing or ambiguous” section.

### Move to `references/`

- `API Reference` → split by source:
  - `references/git-commands.md`: detailed git log/diff/branch command reference.
  - `references/jira-api.md`: Jira auth, JQL examples, fields, pagination.
  - `references/slack-export.md`: Slack export directory layout, message fields, user lookup, timestamp conversion.
- `Configuration` → `references/configuration.md`: environment variables and config-file schema.
- `Examples` → `references/examples.md`: full example inputs/outputs for git+Jira+Slack and git-only cases.
- `Advanced Usage` → `references/advanced-usage.md`: calendar notes, automated weekly runs, PR review accounting, GitHub/GitLab review API pointers.
- `Frequently Asked Questions` → either `references/faq.md` or folded into the relevant reference files:
  - multi-repo and bad commits into `git-commands.md`
  - GitLab/GitHub PR review questions into `advanced-usage.md`
  - colleague report and exclusion/window questions into `configuration.md` or `examples.md`

### Trim rather than move

- Generic background paragraphs about status reports and stakeholder communication.
- Repeated explanations of commands already covered by examples or reference files.
- Overly broad troubleshooting prose that can be expressed as one decision rule, e.g. “Do not invent missing context; mark unclear items for review or ask the user.”
- Automation instructions that imply scheduled Claude usage unless the user specifically asks for recurring automation.

## Would the resulting `SKILL.md` be under 500 lines?

Yes. With the detailed API references, configuration table, long examples, advanced integrations, and FAQ moved out, the remaining `SKILL.md` should be approximately 120–180 lines depending on formatting. That leaves enough room for clear instructions while staying comfortably under 500 lines.

## Would I add pointers in `SKILL.md` to each new reference file?

Yes. The compressed `SKILL.md` should include explicit, conditional pointers so the agent knows when to load each reference file:

- Read `references/git-commands.md` when the default git commands are insufficient, the user works across branches/repos, or commit messages need deeper investigation.
- Read `references/jira-api.md` when the user asks to pull Jira data or provides Jira credentials/configuration.
- Read `references/slack-export.md` when the user provides a Slack export or asks to mine Slack messages for blockers, decisions, or action items.
- Read `references/examples.md` when the user asks for examples or when the output shape is ambiguous.
- Read `references/configuration.md` when setting up environment variables, persistent config, author overrides, output directories, or exclusion rules.
- Read `references/advanced-usage.md` when the user asks about calendar notes, automated weekly runs, PR review work, GitHub/GitLab review activity, or team/recurring workflows.

I would keep these pointers short and task-oriented, not as a long table of contents. The goal is progressive disclosure: load the right detail only when the current request needs it.
