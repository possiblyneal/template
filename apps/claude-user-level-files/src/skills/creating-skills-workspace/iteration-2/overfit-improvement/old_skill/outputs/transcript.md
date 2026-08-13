# Proposed skill improvement

## What specific change would I make?

I would strengthen the existing `## Reporting` guidance so the skill explicitly calibrates log-analysis explanations to the reader before deciding how much technical detail to include. The current skill says to explain errors in plain language, but that is not quite enough: an output can use simpler words and still be organized around stack traces, internal components, and implementation details that PMs cannot easily map to user impact.

The change should make the default report PM-readable when the audience is non-technical or unspecified: start with what happened, user/business impact, and confidence; then include technical evidence only as supporting detail.

## Is it scoped to eval-1 or general?

General. I would not mention eval-1 in the skill or add an instruction that only works for that test case. The eval-1 feedback reveals a broader weakness in the skill: it does not reliably adapt the explanation to the audience.

## Does it address audience calibration generally or add a technical-language special case?

It addresses audience calibration generally. I would not add a narrow special case like “avoid technical language.” Technical terms are sometimes necessary for log analysis, especially when the user needs engineering follow-up. The improvement is to choose the right level of detail for the reader, define necessary terms briefly, and keep low-level evidence separate from the main PM-readable summary.

## Exact instruction I would add/modify

I would modify the first paragraph under `## Reporting`.

Current instruction:

> Tell the user what you found. Explain any errors in plain language. If there are a lot of errors, summarize the main themes rather than listing every single one.

Replace it with:

> Tell the user what you found at the level of detail appropriate for their likely audience. If the audience is non-technical or unspecified, assume a PM or support lead is reading: start with user-visible impact, what happened, and why it matters in plain language before naming technical mechanisms. Avoid unexplained jargon; define necessary technical terms briefly. Keep stack traces, class names, internal component names, and low-level implementation details as supporting evidence rather than the main story, and include them in a separate technical-details section only when they are needed for follow-up or the user asks for engineering-level troubleshooting. If there are a lot of errors, summarize the main themes rather than listing every single one.
