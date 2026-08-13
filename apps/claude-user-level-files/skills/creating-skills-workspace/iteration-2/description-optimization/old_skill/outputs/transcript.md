# Description Optimization Plan

Target skill: `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md`

I would optimize only the YAML `description` field, because that field is the primary trigger-routing mechanism. I would not run the optimization loop or edit the skill until the trigger eval set has been reviewed.

## Plan

1. Inspect the current skill description and body to understand the intended routing boundary.
   - Current description: `Helps with log analysis tasks. Use when the user wants to look at logs.`
   - The skill appears intended for substantive log analysis: reading log files, identifying errors/fatal messages, stack traces, repeated warnings, timestamp gaps, and reporting likely causes in plain language.

2. Generate a trigger eval set with 20 realistic queries.
   - I would generate 10 should-trigger queries.
   - I would generate 10 should-not-trigger queries.
   - The should-trigger cases would cover concrete log-analysis requests with paths, snippets, deployment context, incident debugging, timestamp sequencing, repeated warnings, stack traces, and requests that do not explicitly say “use the log skill” but clearly need log analysis.
   - The should-not-trigger cases would be near misses: logging library setup, writing logs, changing log levels, dashboard/observability setup, parsing non-log data, generic debugging without logs, documentation about logging policy, and simple one-step questions where loading a skill would not help.

3. Review the generated evals with the user before running the loop.
   - Yes, I would use `assets/eval_review.html` before running optimization.
   - I would replace `__EVAL_DATA_PLACEHOLDER__`, `__SKILL_NAME_PLACEHOLDER__`, and `__SKILL_DESCRIPTION_PLACEHOLDER__`, write the rendered page to `/tmp/eval_review_test-skill.html`, open it, and ask the user to edit/toggle the queries.
   - I would use the exported file from `~/Downloads/eval_set.json` or the latest `eval_set (N).json` as the reviewed eval set.

4. Run the description optimization loop only after review.
   - Command I would run from `/home/neal/.claude/skills/creating-skills`:

```bash
python -m scripts.run_loop \
  --eval-set ~/Downloads/eval_set.json \
  --skill-path /home/neal/.claude/skills/creating-skills/evals/files/test-skill \
  --model claude-opus-4-8[1m] \
  --max-iterations 5 \
  --verbose
```

   - I would use model ID `claude-opus-4-8[1m]`, matching the model powering this session.
   - If the reviewed export had a numbered filename, I would substitute that exact path for `~/Downloads/eval_set.json`.

5. After the loop completes, inspect `best_description`.
   - I would not blindly apply it.
   - I would compare it against the current description for correctness, length, trigger coverage, negative cases, and whether it stays within the skill’s intended boundary.
   - If acceptable, I would update only the SKILL.md frontmatter `description` with `best_description`.
   - Then I would run `python -m scripts.quick_validate /home/neal/.claude/skills/creating-skills/evals/files/test-skill` and manually verify the frontmatter constraints.

6. Report results to the user.
   - Yes, I would show the before/after descriptions.
   - Yes, I would report the optimization scores, including current-description baseline score, best-description score, and train/test scores if provided by the loop.
   - I would call out any remaining failure patterns or tradeoffs, especially if the best description improves recall at the cost of false positives.
