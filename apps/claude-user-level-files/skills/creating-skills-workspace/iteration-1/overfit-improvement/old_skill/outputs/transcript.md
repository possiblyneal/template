# Skill Improvement Plan

## What specific change would I make to the skill?

I would add an audience-calibration instruction to the Reporting section so the log analysis output defaults to a non-technical, PM-readable summary before any implementation-level details. The current skill already says to explain errors in plain language, but it does not explicitly require adjusting detail level to the reader or separating business impact from technical evidence. That leaves room for outputs that are technically correct but hard for PMs to follow.

I would not edit the skill file directly for this task; this is the exact change I would propose.

## Scope

This change applies broadly to all outputs, not only to eval-1 specifically.

The feedback from eval-1 indicates a general output-quality issue: the skill needs to calibrate explanations to the user's likely audience and avoid leading with jargon. A broad instruction will help future log-analysis tasks where the reader is a PM, support lead, incident commander, customer-facing stakeholder, or other non-specialist.

## Audience calibration or special case?

This addresses audience calibration in general. It is not a special case for technical language.

The goal is not simply to ban technical terms. Technical evidence can still be included when useful, but the skill should first explain what happened, who or what was affected, and why it matters in terms a non-specialist can understand. Technical details should support the conclusion rather than dominate the report.

## Exact instruction to add or modify in SKILL.md

I would modify the existing Reporting section by replacing this paragraph:

> Tell the user what you found. Explain any errors in plain language. If there are a lot of errors, summarize the main themes rather than listing every single one.

With this:

> Tell the user what you found in language appropriate for their likely audience. Start with the user-visible impact and plain-language meaning before naming technical mechanisms. If the audience is not explicitly technical, assume a PM or support lead is reading: avoid unexplained jargon, define necessary technical terms briefly, and keep stack traces, class names, and low-level implementation details as supporting evidence rather than the main story. If there are a lot of errors, summarize the main themes rather than listing every single one.
