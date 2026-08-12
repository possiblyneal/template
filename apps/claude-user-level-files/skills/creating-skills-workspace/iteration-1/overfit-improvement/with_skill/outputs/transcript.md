# Proposed skill improvement

## What specific change would I make to the skill?

I would modify the existing `## Reporting` guidance so the skill calibrates explanations to the user's audience before choosing terminology. The current instruction says to explain errors in plain language, but it does not explicitly tell the agent to infer who the reader is or adjust the depth of technical detail. That leaves room for outputs that are still too technical for PMs.

I would replace the current first reporting sentence with an audience-calibration instruction that makes PM-friendly summaries the default when the audience is non-technical or unspecified, while still allowing technical detail when the user asks for it.

## Is the change scoped to "eval-1 specifically" or does it apply broadly to all outputs?

This applies broadly to all outputs. The feedback from eval-1 reveals a general weakness: the skill does not consistently calibrate log-analysis reporting to the reader's role and needs. The change should improve future prompts with PMs, executives, support teams, engineers, or unspecified audiences, rather than targeting eval-1 by name.

## Does the change address audience calibration in general, or add a special case for technical language?

It addresses audience calibration in general. I would not add a narrow special case like "avoid technical language for eval-1" or "don't be too technical." Instead, I would instruct the skill to infer the audience, lead with business/user impact, and keep jargon out of the main summary unless the user asks for engineering-level detail. This generalizes better than a one-off ban on technical terms.

## Exact instruction I would add or modify in SKILL.md

I would modify this existing instruction in `## Reporting`:

> Tell the user what you found. Explain any errors in plain language. If there are a lot of errors, summarize the main themes rather than listing every single one.

Replace it with:

> Tell the user what you found at the level of detail appropriate for their role. If the audience is non-technical or unspecified, lead with user/business impact, describe what happened in plain language, and avoid unexplained jargon, stack-trace details, internal component names, or low-level implementation terms unless they are necessary to understand the problem. Put technical details in a separate "Technical details" section only when the user asks for engineering-level troubleshooting or the details are needed for an engineer to act. If there are a lot of errors, summarize the main themes rather than listing every single one.
