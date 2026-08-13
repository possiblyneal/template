# Simulated eval execution plan

I would not run the eval loop in this task, because the instruction is to describe the plan only and avoid spawning real subagents.

## Spawn strategy

I would spawn the `with_skill` and baseline runs simultaneously in the same turn, not sequentially.

For each eval case in `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/evals/evals.json`, I would launch two independent runs in the same tool turn:

1. `with_skill`: points at `/home/neal/.claude/skills/creating-skills/evals/files/test-skill` and saves outputs under the eval-specific `with_skill/outputs/` directory.
2. Baseline: because this is an existing skill being tested/improved, I would first snapshot the current skill into the workspace, then run baseline against that snapshot and save outputs under the eval-specific `old_skill/outputs/` directory.

This same-turn simultaneous spawn is important because it reduces ordering effects and makes timing/token comparisons more comparable. I would not wait for the `with_skill` run to finish before starting baseline, and I would not use the results of one run to influence the other.

## Before spawning

I would prepare the workspace for iteration 1, organized by eval name:

```text
/home/neal/.claude/skills/creating-skills-workspace/iteration-1/<eval-name>/with_skill/outputs/
/home/neal/.claude/skills/creating-skills-workspace/iteration-1/<eval-name>/old_skill/outputs/
```

For each eval, I would write `eval_metadata.json` containing:

- eval id
- eval name
- prompt
- initially empty assertions

I would also snapshot the existing skill before baseline runs, for example:

```text
/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot/
```

## While runs are in progress

While the simultaneous runs are in progress, I would not sit idle and I would not inspect partial outputs in a way that changes the running prompts. I would use that time to draft quantitative assertions for each eval and explain them to the user.

The in-progress work would include:

1. Read the eval prompts and expected outputs from `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/evals/evals.json`.
2. Draft objective assertions with descriptive names.
3. Separate assertions that can be checked programmatically from criteria that require human judgment.
4. Avoid forcing numeric assertions onto subjective outputs.
5. Update each eval's `eval_metadata.json` with drafted assertions.
6. Update the source `evals.json` with the same assertions once they are ready.
7. Prepare grading instructions so completed outputs can be evaluated consistently.
8. Prepare the benchmark aggregation command and review-viewer command, but not run them until outputs, grading, and timing files exist.

I would tell the user what assertions I drafted and why they are objective enough to compare `with_skill` against baseline.

## When a run completes

When each individual run completes, I would immediately save the completion notification timing data to that run's directory.

Timing data capture is immediate and unrecoverable: the completion notification's `total_tokens` and `duration_ms` are only available at completion time. If I fail to record them immediately, I cannot reconstruct them later from the output files.

For a completed `with_skill` run, I would save:

```text
/home/neal/.claude/skills/creating-skills-workspace/iteration-1/<eval-name>/with_skill/timing.json
```

For a completed baseline run, I would save:

```text
/home/neal/.claude/skills/creating-skills-workspace/iteration-1/<eval-name>/old_skill/timing.json
```

Each `timing.json` would include at least:

```json
{
  "total_tokens": "value from completion notification",
  "duration_ms": "value from completion notification"
}
```

I would also preserve each run's task-relevant output files in its `outputs/` directory, using the exact paths given to the subagent prompt.

## After all runs complete

After all simultaneous runs complete and timing data has been captured, I would:

1. Grade each run's outputs against the assertions.
2. Save grading results as `grading.json` in each run directory, using fields `text`, `passed`, and `evidence`.
3. Run benchmark aggregation from `/home/neal/.claude/skills/creating-skills`:

   ```bash
   python -m scripts.aggregate_benchmark /home/neal/.claude/skills/creating-skills-workspace/iteration-1 --skill-name test-skill
   ```

4. Save or verify the generated benchmark at:

   ```text
   /home/neal/.claude/skills/creating-skills-workspace/iteration-1/benchmark.json
   ```

5. Run an analyst pass over the benchmark data to identify patterns, such as:
   - assertions that do not discriminate between runs
   - high variance in timing or tokens
   - cases where the skill improves quality but costs too much
   - cases where baseline performs equally well, suggesting the skill adds little value

6. Launch the eval viewer with:

   ```bash
   nohup python /home/neal/.claude/skills/creating-skills/eval-viewer/generate_review.py \
     /home/neal/.claude/skills/creating-skills-workspace/iteration-1 \
     --skill-name "test-skill" \
     --benchmark /home/neal/.claude/skills/creating-skills-workspace/iteration-1/benchmark.json \
     > /dev/null 2>&1 &
   ```

7. Tell the user to review the Outputs and Benchmark tabs and return when done.

## Summary

- Spawn strategy: simultaneous, same-turn `with_skill` and baseline runs for each eval.
- While runs are in progress: draft and explain objective quantitative assertions, update metadata, and prepare grading/aggregation.
- On completion: immediately save unrecoverable `total_tokens` and `duration_ms` timing data to each run's `timing.json`.
- Outputs: save run outputs in each run's `outputs/` directory, grading in `grading.json`, aggregate benchmark in `iteration-1/benchmark.json`, and human feedback in the iteration workspace after viewer review.
