# Blind A/B Comparison Plan

I would not run the comparison yet. I would set up a rigorous, blinded process that separates execution, judging, and post-hoc analysis.

## Reference files I would read

I would read these files from `/home/neal/.claude/skills/creating-skills` before executing the comparison:

1. `/home/neal/.claude/skills/creating-skills/agents/comparator.md`
   - Primary guide for blind judging.
   - Defines the A/B comparator role, required inputs, rubric generation, winner selection, and `comparison.json` output format.

2. `/home/neal/.claude/skills/creating-skills/agents/analyzer.md`
   - Guide for the unblinded post-hoc analysis after the blind comparison.
   - Explains how to connect comparator findings back to skill differences, execution transcripts, and actionable improvement suggestions.

3. `/home/neal/.claude/skills/creating-skills/references/schemas.md`
   - Schema reference for `metrics.json`, `comparison.json`, `analysis.json`, `grading.json`, `benchmark.json`, and related artifacts.
   - Needed to keep output artifacts compatible with the existing evaluation tooling.

If I were actually executing, I would also inspect:

4. `/home/neal/.claude/skills/creating-skills/evals/evals.json`, if present
   - To identify existing eval prompts, expected outputs, input files, and expectations.

5. `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md`
   - The new skill version under test.
   - I would read it only for setup and later unblinded analysis, not expose its identity to the blind comparator.

6. `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/SKILL.md`
   - The old skill snapshot.
   - Same constraint: useful for setup and post-hoc analysis, but not shown to the blind comparator as “old” or “new.”

## Whether I would spawn an independent comparator agent

Yes. I would spawn an independent comparator agent rather than judge the outputs myself.

Reasoning:

- The user asked for a rigorous blind A/B comparison.
- I know which path is the new skill and which path is the old snapshot, so self-judging would not be genuinely blind.
- `agents/comparator.md` is explicitly designed for this: it compares outputs labeled only as A and B, generates a rubric from the task, scores both outputs, and selects a winner based on output quality.
- I would reserve my own role for orchestration and post-hoc synthesis, not first-pass judgment.

## Execution plan I would use, without running it now

### 1. Select eval tasks

I would identify a small but representative set of eval prompts, preferably from an existing `evals/evals.json` if available. If no eval set exists, I would create or propose prompts that exercise the skill’s intended behavior, including:

- A straightforward expected-use case.
- A boundary or ambiguous case where skill guidance should matter.
- A case where overfitting or excessive process could hurt performance.

For each eval, I would record:

- Eval ID and name.
- Original prompt.
- Input files, if any.
- Expected output description.
- Objective expectations, if they can be fairly stated.

### 2. Run both skill versions independently

For each eval, I would run two executor agents in parallel:

- One using `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md`.
- One using `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot`.

I would save their outputs into version-neutral directories first, for example:

- `run_1/outputs/`
- `run_2/outputs/`

Internally I would keep a private mapping file outside the comparator’s context, such as:

```json
{
  "eval_id": "example-eval",
  "A": "new",
  "B": "old",
  "new_skill_path": "/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md",
  "old_skill_path": "/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot"
}
```

For rigor, I would randomize whether the new version is A or B per eval, rather than always assigning new to A.

### 3. Strip identity leaks before judging

Before sending outputs to the comparator, I would check for identity leaks such as:

- Directory names containing `new`, `old`, `with_skill`, `old_skill`, `skill-snapshot`, or `test-skill`.
- Transcript text that mentions the skill path.
- Generated filenames that encode the version.
- Metadata files that expose the skill path.

If needed, I would copy only the final user-facing outputs into neutral directories:

- `blind/eval-name/A/`
- `blind/eval-name/B/`

The comparator would receive only:

- `output_a_path`
- `output_b_path`
- `eval_prompt`
- `expectations`, if any
- `output_path` for `comparison.json`

It would not receive skill paths, transcript paths, workspace names, or the A/B mapping.

### 4. Have the independent comparator judge quality

For each eval, I would spawn a comparator agent using the instructions in:

`/home/neal/.claude/skills/creating-skills/agents/comparator.md`

The comparator would:

- Read both outputs.
- Understand the original eval prompt.
- Generate a task-specific content and structure rubric.
- Score A and B on a 1–5 criterion scale and 1–10 overall scale.
- Check optional expectations as secondary evidence.
- Save a `comparison.json` with:
  - `winner`: `A`, `B`, or `TIE`
  - `reasoning`
  - `rubric`
  - `output_quality`
  - optional `expectation_results`

### 5. Unblind only after comparison is saved

Only after each `comparison.json` is written would I use the private mapping file to determine whether the new or old skill won.

I would then compute summary results such as:

- New wins.
- Old wins.
- Ties.
- Mean quality score by version.
- Per-eval score deltas.
- Expectation pass-rate deltas, if expectations were provided.
- Cases where the comparator’s reasoning suggests a clear behavioral advantage.

### 6. Run post-hoc analysis

After unblinding, I would use the guidance in:

`/home/neal/.claude/skills/creating-skills/agents/analyzer.md`

For each meaningful win/loss, I would compare:

- Winning skill content.
- Losing skill content.
- Execution transcript from each run.
- Blind comparator reasoning.

The goal would be to explain causation, not just report scores. I would look for:

- Did one skill give clearer procedural guidance?
- Did one skill induce unnecessary work?
- Did one skill omit important constraints?
- Did either agent ignore or misapply its skill?
- Were output differences actually attributable to the skill, or likely noise?

### 7. Optional robustness checks

For a more rigorous comparison, I would add:

- Multiple runs per eval per version to reduce stochastic noise.
- Randomized A/B assignment per run.
- At least one second comparator for contentious or close cases.
- A rule that ties are acceptable when the score delta is small and reasoning is weak.
- Separate reporting of objective expectation pass rates versus subjective quality judgments.

## How I would ensure the comparator stays blind

I would enforce blinding with these controls:

1. Use neutral labels only: `A` and `B`.
2. Randomize which version maps to A/B for each eval.
3. Keep the A/B mapping in a private file not provided to the comparator.
4. Provide only final outputs, not skill paths or run directories containing identifying names.
5. Remove or avoid transcripts during the blind comparison phase if they contain skill paths.
6. If transcripts must be judged, redact path strings and version labels before comparator access.
7. Do not mention “new,” “old,” “snapshot,” “test-skill,” “with_skill,” or “old_skill” in the comparator prompt.
8. Save comparator results before any unblinding or analysis.

## What I would report to the user

I would report both the blind outcome and the interpretation after unblinding. The report would include:

1. Executive summary
   - Which version won overall: new, old, or inconclusive.
   - Number of wins/losses/ties.
   - Whether the result looks decisive or noisy.

2. Per-eval table
   - Eval name.
   - Blind winner, A/B.
   - Unblinded winner, new/old.
   - A and B quality scores.
   - Score delta.
   - Brief comparator rationale.

3. Objective metrics
   - Expectation pass rates, if expectations were available.
   - Tool calls, tokens, duration, and error counts, if captured.
   - Any cost/latency tradeoff introduced by the new skill.

4. Qualitative findings
   - Where the new skill helped.
   - Where the old skill was better or simpler.
   - Any outputs where both versions failed.
   - Any outputs where the comparator found only marginal differences.

5. Post-hoc skill analysis
   - Specific instructions or structures that likely caused better behavior.
   - Specific weaknesses in the losing version.
   - Whether the observed differences appear generalizable or overfit to the evals.

6. Recommendation
   - Keep the new version, revert to old, or revise and rerun.
   - Concrete changes to make before the next iteration.
   - Whether more eval coverage is needed before trusting the result.

I would be explicit that the blind comparator judges output quality, while the post-hoc analyzer explains why a version likely won after unblinding. That separation is the core rigor of the process.
