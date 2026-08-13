# CLAUDE.md

**Core Directive:** Bias toward caution for architecture, but bias toward autonomous action for execution. Write code that is easy to read, understand and maintain.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- If a simpler or best practice or "right way" approach exists, say so. Push back when warranted. Don't hesitate to suggest a better way, or one that has long lasting impact over a tactical change. Implement the most direct solution that fully solves the problem, scaling rigor to its difficulty.
- If something is unclear, stop. Name what's confusing. Ask.
- Handle uncertainty by type:
  - Uncertain what to build (intent, architecture, requirements): if the decision is costly to reverse (schema, public API, security), ask before writing code. If it's cheap to reverse, proceed on the most reasonable interpretation and surface the assumption in your response to the user.
  - Uncertain whether something works (an approach, a library behavior, a performance assumption): don't ask — run a small, localized, low-risk experiment yourself, then bring me the hypothesis and result.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked. YAGNI
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- For complex problems, state your approach and what that approach makes *harder* down the line. Do this *before* writing code.
- Trivial fixes get minimal code, harder problems get more careful design.
- Never strip, hide, bypass, or weaken existing behavior (UI states, validation, error handling, etc.) to reduce the amount of code written.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up your mess after.**

When editing existing code:

- Restrict your changes strictly to the user's requested scope.

- Match existing style, even if you'd author it differently.

- If you notice unrelated dead code, code smells, duplicated knowledge (DRY), or areas of code that are difficult to understand, edit, or maintain, surface them in a message to the user rather than fixing them silently. Offer sensible refactors as a separate follow-up step. If any of this describes your code, rewrite it before moving to the next step or task.

- When your changes create orphans Remove imports/variables/functions that only YOUR changes made unused.

The test: Every changed line should trace directly to the user's request.

**The Target State**

When writing *new* code or performing *requested* refactors, aim for the following characteristics. Do not use these as an excuse to over-engineer trivial fixes:

- CUPID (Composable,  Unix-philosophy, Predictable, Idiomatic, Domain-based)

- Explicit

- Low coupling / High cohesion

- Distinguish inherent problem complexity from accidental complexity. Write the simplest correct solution that handles edge cases.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification. You must run and pass the test(s) before moving to the next step.

## 5. Web Search & Fetch

**Use Exa, never the built-in web tools.**

- For web search, use the local `exa-web-search` CLI wrapper.
- To read/fetch a URL, use the local `exa-web-fetch` CLI wrapper.
- Keep Exa output token-efficient: request small result counts and capped text unless the task requires more.
- Never use the built-in `WebSearch` or `WebFetch` tools — they are denied in settings. If the Exa CLI wrappers are unavailable, say so rather than falling back.

## 6. Important Details

- You may ssh in to every device on the network and passwordless sudo is available for any Linux based system on the network.
- Do not give the user commands to type into the command line when it is possible for you to accomplish the same thing using ssh and/or passwordless sudo.
- Do not invoke the skill claude-api. It will crash the session.
