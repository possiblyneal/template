# Skill improvement recommendation

## What specific change would I make?

I would modify the existing reporting guidance to make audience calibration explicit before writing the answer. The current skill already says to explain errors in plain language, but it does not tell the agent to infer or honor the reader's role. For PM-facing outputs, the agent should lead with product/user impact, severity, and next steps, then keep implementation details secondary.

## Is it scoped to eval-1 or general?

General. The feedback came from eval-1, but the underlying issue is not specific to that eval. Any log-analysis response can miss the mark if it does not match the user's audience and decision-making needs.

## Does it address audience calibration generally or add a technical-language special case?

It addresses audience calibration generally. I would not add a special case like "if eval-1" or "if PMs complain." Instead, I would add a reusable instruction: infer the audience from the prompt, calibrate the summary to that audience, and avoid unnecessary implementation detail unless the user asks for it.

## Exact instruction I would add/modify

I would replace the current Reporting section:

> Tell the user what you found. Explain any errors in plain language. If there are a lot of errors, summarize the main themes rather than listing every single one.
>
> Try to explain what might have caused the problem if you can figure it out from the log context.

with:

> Tell the user what you found in language calibrated to their audience and purpose. Infer the audience from the prompt: for non-technical readers such as PMs, lead with user/product impact, severity, confidence, and recommended next steps; keep technical details brief and explain jargon in plain language. For technical readers, include the relevant error names, timestamps, stack traces, and likely implementation causes. If there are many errors, summarize the main themes rather than listing every single one.
>
> Explain what might have caused the problem when the log context supports it, and separate evidence from speculation.
