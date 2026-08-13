# Description optimization plan for test-skill

Target skill: `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md`

Current description:

> Helps with log analysis tasks. Use when the user wants to look at logs.

I would optimize the description for routing accuracy without changing the skill body unless the optimizer result made a frontmatter-only update appropriate.

## Plan I would execute

1. Generate a trigger eval set with 20 total queries.
   - 10 should-trigger queries.
   - 10 should-not-trigger queries.

   I would use an even split because this description is broad and keyword-heavy. It needs both better recall for real log-analysis requests and better precision against near-misses that mention logs but ask for something else.

   The should-trigger queries would cover realistic log-analysis tasks such as diagnosing stack traces, summarizing production errors, comparing timestamps, finding root causes in service logs, triaging repeated warnings, and explaining failure sequences from attached log files.

   The should-not-trigger queries would be tricky near-misses such as configuring log rotation, writing a logging library, adding instrumentation, changing log levels in code, building dashboards, explaining general observability concepts, or searching git history for files named `logs`.

2. Review the generated eval queries with the user before running the optimization loop.

   Yes, I would review them via `eval_review.html` first. I would load `/home/neal/.claude/skills/creating-skills/assets/eval_review.html`, inject the eval data, skill name, and current description, write the review page to `/tmp/eval_review_test-skill.html`, and open it for the user. The user could edit prompts, toggle should-trigger flags, and export the final set to `~/Downloads/eval_set.json`.

3. Run the description optimization loop only after the reviewed eval set is available.

   The command I would run from `/home/neal/.claude/skills/creating-skills` is:

   ```bash
   python -m scripts.run_loop \
     --eval-set /home/neal/Downloads/eval_set.json \
     --skill-path /home/neal/.claude/skills/creating-skills/evals/files/test-skill \
     --model claude-opus-4-8[1m] \
     --max-iterations 5 \
     --verbose
   ```

   I would use model ID `claude-opus-4-8[1m]`, matching the model powering this session so routing measurements reflect the user's actual experience.

4. After the loop, handle `best_description` conservatively.

   I would inspect the optimizer output, especially train/test scores and the failure cases. If `best_description` improves held-out test score without obvious overfitting, I would update only the `description` field in the SKILL.md frontmatter with `best_description`. I would not alter the skill body for a description-only optimization unless the results revealed a separate instruction problem.

5. Report the result.

   Yes, I would show before/after descriptions and report scores. The report would include:
   - Original description.
   - Optimized `best_description`.
   - Baseline score and final/best score.
   - Train/test split results if available.
   - Any remaining false positives or false negatives.
   - Whether I applied the description to SKILL.md.

6. Validate after applying, if application were allowed.

   If file edits were allowed, I would run:

   ```bash
   python -m scripts.quick_validate /home/neal/.claude/skills/creating-skills/evals/files/test-skill
   ```

   I would also verify the frontmatter manually: directory/name consistency, description length under 1024 characters, and clear positive/negative routing language.

## Important constraint for this run

Per the task instruction, I would not actually run the optimization loop and would not edit `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md` in this run. This transcript is only the execution plan.
