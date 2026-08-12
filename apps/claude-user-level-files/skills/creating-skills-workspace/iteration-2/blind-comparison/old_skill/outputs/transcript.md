# Blind A/B Comparison Plan

I would not run the comparison yet. I would set up a rigorous blind A/B process that compares the old and new skill versions only through their produced outputs, then unblinds after the quality judgment is complete.

## Skill versions

- New skill: `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md`
- Old skill snapshot: `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot`

## Reference files I would read

I would use the old snapshot's own process docs as the authority for this comparison:

1. `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/SKILL.md`
   - Guides the overall evaluation workflow.
   - Its Advanced: Blind comparison section explicitly says to read `agents/comparator.md` and `agents/analyzer.md`, give outputs to an independent agent without revealing which skill produced which, and use the result to understand quality differences.

2. `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/agents/comparator.md`
   - Defines the blind comparator role, inputs, scoring process, rubric construction, and output JSON format.
   - This is the key file for preserving blinding and preventing version bias.

3. `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/agents/analyzer.md`
   - Defines the post-hoc analyzer role after unblinding.
   - This is where I would identify why the winning version won, what the losing version lacked, and which changes would likely improve the loser.

4. `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/references/schemas.md`
   - Defines `comparison.json`, `analysis.json`, `metrics.json`, `grading.json`, and benchmark-related schemas.
   - I would use it to keep output files machine-readable and compatible with the existing evaluation workflow.

If the comparison depended on existing eval prompts, expectations, or prior outputs, I would also read the relevant `evals/evals.json`, `eval_metadata.json`, prior `grading.json`, run outputs, and transcripts for the test cases being compared. I would not read the new and old `SKILL.md` bodies before judging output quality, except in the later post-hoc analyzer phase, because the comparator should judge outputs rather than skill prose.

## Whether I would spawn an independent comparator agent

I would spawn an independent comparator agent rather than judge the outputs myself.

Reason: the comparison is specifically meant to be blind. If I both know which paths correspond to old/new and perform the quality judgment, the result is vulnerable to expectation bias. The comparator agent should receive only anonymized labels, the original eval prompt, optional expectations, and the two output paths. It should not receive either skill path, version names, branch names, directory names like `old_skill` or `with_skill`, or any metadata that reveals provenance.

I would reserve my own judgment for orchestration and the post-hoc synthesis after the comparator has saved its blinded decision.

## Planned execution flow

1. Select the eval cases to compare.
   - Use the same task prompts and input files for both versions.
   - Prefer multiple eval cases if the goal is rigorous comparison, because a single case may overfit to one strength or weakness.

2. Run both versions under equivalent conditions.
   - Old version uses `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot`.
   - New version uses `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/SKILL.md` or its containing skill directory, depending on the runner's expected input.
   - Spawn paired runs in the same turn where possible so model/server conditions are as similar as practical.
   - Save outputs, transcripts, metrics, and timing separately.

3. Create blinded copies or aliases of the outputs.
   - For each eval, randomly assign the two versions to `A` and `B`.
   - Copy or symlink only the user-visible outputs into neutral directories such as:
     - `comparison/eval-name/A/outputs/`
     - `comparison/eval-name/B/outputs/`
   - Do not include paths or filenames containing `old`, `new`, `with_skill`, `old_skill`, `skill-snapshot`, or the skill directory names.
   - Do not include transcripts in the blind comparator packet if they mention the skill path or reveal which version ran. If transcripts are needed for quality assessment, redact provenance first.

4. Record the hidden mapping separately.
   - Store an orchestrator-only mapping such as:
     - `A = old`, `B = new`, or vice versa.
   - Keep that mapping out of the comparator prompt and out of files the comparator can read.
   - Use a fresh randomization per eval to avoid side bias.

5. Spawn the blind comparator.
   - Prompt it according to `agents/comparator.md` with:
     - `output_a_path`
     - `output_b_path`
     - `eval_prompt`
     - `expectations` if available
     - `output_path` for `comparison.json`
   - Tell it explicitly not to infer provenance and to judge only task completion and output quality.

6. Collect comparator results.
   - Save one `comparison.json` per eval, following the schema in `references/schemas.md`.
   - If multiple evals are used, aggregate wins, ties, rubric scores, expectation pass rates, and common strengths/weaknesses.

7. Unblind only after comparison files are complete.
   - Apply the hidden mapping to identify whether old or new won each eval.
   - Then run or perform the post-hoc analyzer phase using `agents/analyzer.md`.
   - The analyzer may read both skills and transcripts because its job is no longer blind; its job is causal explanation and improvement suggestions.

## How I would ensure the comparator does not know which output came from which version

I would enforce blinding at the filesystem, prompt, and metadata levels:

- Use neutral labels only: `A` and `B`.
- Randomize assignment independently for each eval.
- Provide anonymized output paths, not original run directories.
- Avoid directory names that reveal provenance, including `old_skill`, `new_skill`, `with_skill`, `without_skill`, `skill-snapshot`, or `test-skill`.
- Exclude or redact transcripts before the blind comparison if they contain skill paths, tool prompts, or other identifying traces.
- Do not include timing, token counts, or tool-call metrics in the comparator prompt unless the task explicitly values efficiency; those can leak behavior patterns and should usually be analyzed after quality judgment.
- Do not include either `SKILL.md` in the comparator context.
- Keep the A/B mapping in a separate orchestrator-only file or note that is not available to the comparator.
- Ask the comparator to save only `winner`, reasoning, rubric scores, output-quality strengths/weaknesses, and expectation results.

## What I would report to the user

I would report both the blinded result and the unblinded interpretation:

1. Comparison setup
   - Number of evals compared.
   - Whether A/B assignment was randomized per eval.
   - What outputs were compared.
   - Whether expectations were used.

2. Blind results
   - For each eval: whether A, B, or tie won.
   - Rubric scores for content and structure.
   - Expectation pass rates if expectations were provided.
   - Comparator's short reasoning with concrete evidence from the outputs.

3. Unblinded summary
   - Which version won overall: old, new, or inconclusive.
   - Per-eval old/new mapping after unblinding.
   - Whether the result is strong, mixed, or too close to call.

4. Quality tradeoffs
   - Where the winning version was better.
   - Where the losing version was still stronger.
   - Any recurring failure modes.
   - Any evidence that assertions were non-discriminating or that outputs were too subjective for a confident automatic judgment.

5. Actionable follow-up
   - Specific improvements to the weaker skill version, prioritized by expected impact.
   - Whether more evals or repeated runs are needed to reduce variance.
   - Whether to keep the new skill, revise it, or roll back based on the comparison.

I would be careful not to overstate the result. If only one prompt was compared, I would report it as a case study, not a statistically reliable benchmark. If multiple prompts and repeated runs agreed, I would present the conclusion with higher confidence.
