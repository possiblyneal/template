# Improvement Plan for verbose-skill

Skill read: `/home/neal/.claude/skills/creating-skills/evals/files/verbose-skill/SKILL.md`

## Size

- Current line count: 548 lines
- Exceeds 500 lines: yes

## Approach

Use both approaches:

1. Compress the inline `SKILL.md` to keep only the routing-critical workflow, default report format, core writing rules, and essential fallback behavior.
2. Move detailed reference material into `references/` so it is loaded only when needed.

This skill is only modestly over the 500-line limit, but the excess is not just formatting bloat. Large sections are reference-like: command catalogs, API details, configuration tables, Slack export schema, examples, FAQ, and advanced integrations. Those belong in bundled references rather than always-loaded skill instructions.

## Move to `references/`

I would move these sections out of `SKILL.md`:

- `API Reference`
  - Move to `references/api-reference.md`
  - Includes detailed Git command reference, Jira API/JQL reference, Slack export format, and timestamp conversion notes.

- `Configuration`
  - Move to `references/configuration.md`
  - Includes environment variables, config-file schema, override behavior, and any setup details.

- Most of `Examples`
  - Move to `references/examples.md`
  - Keep at most one tiny inline example or before/after phrasing pair in `SKILL.md`; full report examples can live in the reference.

- `Advanced Usage`
  - Move to `references/advanced-usage.md`
  - Includes calendar integration, automated weekly runs, and PR review API details.

- `Frequently Asked Questions`
  - Move to `references/faq.md`
  - These are situational answers, not always-needed operating instructions.

## Trim or compress inline

I would keep but compress these sections inline:

- `Background and Context`
  - Trim from two explanatory paragraphs to one short purpose statement.
  - The agent already understands status reports; only the skill-specific goal needs to remain.

- `Data Sources`
  - Keep the source hierarchy and extraction priorities inline.
  - Compress detailed Git/Jira/Slack commands into short defaults plus pointers to references.
  - Keep the source-combination rule: Jira as backbone, match commits by ticket number, add Slack context, include unmatched commits.

- `Report Format`
  - Keep the default template inline because it directly controls output.
  - Consider removing emoji if the user has not asked for a friendly format, or keep them only as the default template style.
  - Keep the good/bad abstraction example because it is high-value and compact.

- `Writing Guidelines`
  - Compress tone, audience, blockers, and confidentiality into a short checklist.
  - Keep the rules that prevent poor reports: audience-appropriate detail, actionable blockers, no negative colleague callouts, flag sensitive data.

- `Customization`
  - Keep short inline instructions for custom templates and team reports.
  - Move recurring-report storage/diff suggestions to advanced usage unless the user explicitly asks for recurring reports.

- `Error Handling` and `Troubleshooting`
  - Merge into one concise `Fallbacks and edge cases` section.
  - Keep the essential cases inline: no git history, no Jira access, ambiguous commits, empty weeks, duplicate items, wrong date range.
  - Trim verbose suggested wording where not necessary.

## Expected resulting structure

Proposed inline `SKILL.md` structure:

1. Frontmatter
2. Purpose and default behavior
3. Quick workflow
4. Data source priority and collection defaults
5. Default report format
6. Writing rules
7. Fallbacks and edge cases
8. Conditional reference pointers

Proposed bundled references:

- `references/api-reference.md`
- `references/configuration.md`
- `references/examples.md`
- `references/advanced-usage.md`
- `references/faq.md`

## Will result be under 500 lines?

Yes. The revised `SKILL.md` should comfortably fit under 500 lines. A reasonable target is 150-220 lines inline, with the moved detail preserved in reference files.

## Conditional pointers

Yes. I would add conditional pointers in `SKILL.md` to each reference file, for example:

- Read `references/api-reference.md` when you need exact Git commands, Jira API/JQL syntax, Slack export parsing details, or GitHub/GitLab review-query endpoints.
- Read `references/configuration.md` when the user asks about environment variables, config files, credentials, defaults, or setup.
- Read `references/examples.md` when the user asks for examples, when drafting a report from sparse data, or when calibrating level of detail.
- Read `references/advanced-usage.md` when the user asks about calendar input, weekly automation, recurring report history, or PR-review activity.
- Read `references/faq.md` when the user asks a situational question not covered by the inline workflow, such as multiple repositories, colleague reports, exclusions, or nonstandard date windows.

These pointers should be conditional, not a blanket instruction to read all references at startup, so the skill preserves context-window efficiency.
