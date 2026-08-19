# Prose Checks

Writing-quality checks for SKILL.md. These catch skills that are spec-compliant
but written in a way that makes them trigger badly, waste context, or promise
knowledge they don't deliver. `skill-validator` reads structure — files,
frontmatter, tokens, links. It never reads the English for meaning. This does.

Distilled from [SkillCheck-Free](https://github.com/olgasafonova/SkillCheck-Free)
by olgasafonova (MIT). Only the checks that `skill-validator` does not already
cover are kept; its frontmatter and structure rules are dropped as redundant.

Severity: **Error** blocks, **Warning** needs a decision, **Suggestion** is a
judgment call. Nothing here is mechanical — every one of these can fire on
writing that is correct in context. Report what fired and why; don't auto-fix.

## Report format

One row per finding, most severe first. No prose, no praise, no summary.

```
check-id | severity | line | problem | fix
```

Empty table if clean.

---

## R1 — Routing content in the body

**Severity:** Warning

Fires on a body heading matching `## When to Use`, `## When to Use This Skill`,
`## When This Triggers`, or body text like "Activate when user", "Trigger this
skill when", "Use this skill when".

The body loads *after* the routing decision. Trigger conditions written here
never influenced whether the skill loaded — they're inert. Claude reads only
`description` when deciding.

**Fix:** Merge the unique trigger content into `description`, delete the body
section.

**Does not fire when:** the section documents *scope boundaries* for a skill
already loaded ("this covers X, for Y see Z") rather than trigger conditions.

## R2 — Description reads as summary, not trigger

**Severity:** Suggestion

Fires when `description` opens with "This skill", "A tool that", "Provides",
"Offers", "Handles", "Manages", "Enables".

Claude scans descriptions asking "is there a skill for this request?" A
capability summary doesn't answer that question; a trigger condition does.

**Fix:** Lead with an action verb, include a "Use when" clause.

**Does not fire when:** a summary opener is followed by a WHEN clause later
("Handles X. Use when the user says Y" is fine), or the description already
opens with an action verb.

## R3 — Railroading

**Severity:** Suggestion

Fires on 5+ prescriptive phrases outside code blocks and anti-pattern sections:
"you must always", "always do exactly", "never deviate", "follow these exact
steps", "do not change this", "this is the only way", "you are required to".

Rigid sequences stop the model adapting to the situation actually in front of
it. Explaining the reasoning generalizes better than issuing a mandate — given
the why, the model handles cases the rule didn't anticipate.

**Fix:** Replace the mandate with the reason behind it.

**Does not fire when:** inside code blocks, blockquotes, or example tags; in
anti-pattern sections describing what *not* to do; or in genuinely
safety-critical steps (destructive operations, security, compliance) where
precision is the point. Match specificity to fragility — prescriptive language
around an irreversible step is correct, not a smell.

## R4 — Wisdom and platitudes

**Severity:** Suggestion

Three patterns:
1. Openers: "Remember that", "It's important to", "Keep in mind that", "Never
   forget that", "Always keep in mind", "Consider the importance of"
2. Mid-line "[noun] is essential/crucial/important to [noun]"
3. Vague imperatives: "Ensure quality", "maintain standards", "strive for best
   practices"

Generic advice costs real tokens and tells a capable model nothing it doesn't
have. The default assumption is that the agent is already competent — only add
what it doesn't already know.

**Fix:** Cut it, or replace with the concrete thing it gestures at.

**Does not fire when:** inside code blocks or blockquotes; in example sections;
in before/after comparison lines.

## R5 — Hollow gotchas

**Severity:** Suggestion

Fires in a `## Gotchas` / `## Troubleshooting` / `## Tips` / `## Caveats` /
`## Pitfalls` section when 3+ lines are generic filler ("follow team standards",
"ensure proper handling", "handle appropriately", "consider relevant factors",
"use appropriate methods", "maintain quality") **and** no line carries a
concrete signal.

Concrete signals: a specific threshold or number with units, a stated
consequence ("X fails because Y"), a numbered debugging step, or a
file/function reference.

The section promises hard-won knowledge and delivers none. Worse than absent —
it looks like the question was answered.

**Fix:** Replace with real failure cases, or delete the section.

**Does not fire when:** at least one concrete threshold, consequence, or
debugging step is present.

## R6 — Restraint without a safety carve-out

**Severity:** Warning

Fires when a restraint directive is present (YAGNI, "keep it minimal", "don't
over-engineer", "simplest thing that works", "resist the urge to add", "prefer
the stdlib") **and** no line pairs a keep cue ("never cut", "always keep",
"still required", "non-negotiable") with a safety noun (validation, security,
accessibility, a11y).

"Be minimal" without an exemption reads as license to skip non-negotiables, not
just to avoid gold-plating. Lazy, not negligent, is the line.

**Fix:** Add an explicit carve-out naming what minimalism never applies to.

**Does not fire when:** no restraint directive exists, or a carve-out clause is
already present. An incidental mention of "security" without a keep cue does
not count.

## R7 — Contradictions

**Severity:** Error

Fires when two instructions require and forbid the same action, and no scoping
condition separates them.

**Fix:** Scope each instruction to its condition, or drop one.

**Does not fire when:** the instructions are conditioned on different situations
("use X for local runs, never in CI").

## R8 — Ambiguous quantities

**Severity:** Suggestion

Fires on vague quantifiers where a number would work: "multiple items", "several
files", "correct settings", "appropriate values", "a few retries".

**Fix:** Give the exact count or the criterion that determines it.

**Does not fire when:** inside code blocks, blockquotes, or inline backticks —
a backticked literal is a quoted example, not vague writing; in example or
pattern sections; in before/after comparison lines; or when followed by a
qualifier ("several files — everything under `src/`").

## R9 — Unspecified output format

**Severity:** Warning

Fires when the skill says it outputs, returns, or produces something, but no
section shows the shape — no code block, no JSON, no table.

The model will invent a format, and it will vary run to run.

**Fix:** Add one concrete example of the output.

**Does not fire when:** the output is prose whose shape genuinely doesn't
matter, or a format example already appears anywhere in the body.

## R10 — Unstructured anti-patterns

**Severity:** Suggestion

Fires when a section headed "anti-pattern", "what not to do", "avoid", "common
mistakes", "bad practices", or "pitfalls" is wall-of-text prose: a 100+ char
line containing don't/avoid/never, or 3+ prose lines carrying 3+ avoidance
directives.

Lists of things to avoid are scanned, not read. Prose buries them.

**Fix:** Convert to a table or bullet list.

**Does not fire when:** the section already uses tables or bullet lists.
