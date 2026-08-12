# Simulated eval execution plan for `test-skill`

Task context:
- Skill under test: `/home/neal/.claude/skills/creating-skills/evals/files/test-skill`
- Evals file: `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/evals/evals.json`
- Baseline skill snapshot: `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot`
- Workspace iteration: `/home/neal/.claude/skills/creating-skills-workspace/iteration-1`

Important constraint for this run: I would not actually spawn real subagents or run the full eval loop. This transcript describes the plan I would execute.

## Spawn strategy

I would spawn the `with_skill` and baseline runs simultaneously in the same turn, not sequentially.

Reasoning: the skill instructions explicitly say to spawn all runs in the same turn and not run `with_skill` first and baseline later. For each eval case, I would dispatch two runs at once:

1. `with_skill`: points at the current skill under test at `/home/neal/.claude/skills/creating-skills/evals/files/test-skill` and saves outputs under the eval's `with_skill/outputs/` directory.
2. `old_skill`: because this is improving/testing an existing skill, the baseline points at the snapshot at `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot` and saves outputs under the eval's `old_skill/outputs/` directory.

For these two evals, the simultaneous dispatch set would be four subagent runs total:

- Eval 1 with current skill
- Eval 1 with old skill snapshot baseline
- Eval 2 with current skill
- Eval 2 with old skill snapshot baseline

I would not wait for Eval 1 to finish before starting Eval 2, and I would not wait for any `with_skill` run before starting its baseline. Same-turn spawning keeps environmental variance lower and follows the skill's evaluation contract.

## Per-eval setup before spawning

For each eval from `evals.json`, I would create a descriptive eval directory under the iteration workspace, for example:

- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/analyze-sample-log/`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/api-500-root-cause/`

Inside each eval directory, I would write `eval_metadata.json` before or immediately alongside dispatch, initially with empty assertions:

```json
{
  "eval_id": 1,
  "eval_name": "analyze-sample-log",
  "prompt": "Analyze this log file and tell me what went wrong: evals/files/test-skill/evals/sample.log",
  "assertions": []
}
```

and:

```json
{
  "eval_id": 2,
  "eval_name": "api-500-root-cause",
  "prompt": "I have a log from our API server that's been throwing 500s since 3pm. Can you find the root cause?",
  "assertions": []
}
```

Each run would get an explicit save location:

- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/analyze-sample-log/with_skill/outputs/`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/analyze-sample-log/old_skill/outputs/`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/api-500-root-cause/with_skill/outputs/`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/api-500-root-cause/old_skill/outputs/`

## What I would do while runs are in progress

While the four runs are in progress, I would not sit idle and I would not inspect partial outputs to steer the runs. I would draft quantitative assertions that can be applied objectively after completion, then explain those assertions to the user.

For Eval 1, likely assertions would include:

- `has_short_summary`: output begins with or clearly includes a concise summary section.
- `mentions_error_timestamps`: output cites timestamps from the log rather than only describing symptoms generically.
- `identifies_error_events`: output names the concrete errors found in the log.
- `explains_probable_cause`: output gives a likely cause supported by evidence.
- `uses_plain_language`: output explains the issue in terms understandable to a non-specialist.

For Eval 2, likely assertions would include:

- `identifies_first_failure`: output identifies the first relevant 500/error event, especially around the reported 3pm window.
- `traces_event_sequence`: output describes the sequence leading from first symptom to later failures.
- `states_root_cause`: output proposes a specific root cause rather than only listing errors.
- `cites_log_evidence`: output includes concrete evidence from the log.
- `separates_confidence_from_guess`: output distinguishes observed facts from inference when evidence is incomplete.

After drafting them, I would update each eval's `eval_metadata.json` and also update `/home/neal/.claude/skills/creating-skills/evals/files/test-skill/evals/evals.json` with the assertion definitions if this were a real loop. Since this task asks only for the simulated plan, I would not mutate the evals file here.

I would also prepare the grading and aggregation plan while waiting:

1. Identify what output files each run is expected to produce.
2. Prepare grader prompts using `agents/grader.md` from the creating-skills skill.
3. Decide which assertions can be checked programmatically versus by grader judgment.
4. Prepare the benchmark aggregation command for once all `grading.json` files exist.
5. Prepare the eval viewer command, using static output if a browser cannot be launched in the environment.

## What I would save when each run completes

When each subagent run completes, I would immediately save the completion notification's timing data into that run's directory as `timing.json`.

Timing capture is immediate and unrecoverable: the completion notification contains `total_tokens` and `duration_ms`, and those values are not recoverable later if I fail to write them down at completion time. Therefore, the first action after receiving each run-complete notification would be to write `timing.json` before doing grading, aggregation, or analysis.

For example, for the Eval 1 current-skill run, I would save:

```json
{
  "total_tokens": 12345,
  "duration_ms": 67890
}
```

to:

`/home/neal/.claude/skills/creating-skills-workspace/iteration-1/analyze-sample-log/with_skill/timing.json`

Equivalent timing files would be saved for:

- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/analyze-sample-log/old_skill/timing.json`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/api-500-root-cause/with_skill/timing.json`
- `/home/neal/.claude/skills/creating-skills-workspace/iteration-1/api-500-root-cause/old_skill/timing.json`

I would also ensure each run's user-facing output was saved in its `outputs/` directory. For these log-analysis evals, the main artifact would likely be a concise analysis report, for example `analysis.md`, containing the summary, timestamped evidence, root-cause hypothesis, and confidence/uncertainty notes.

## Post-completion plan

After all runs complete and timing data is captured:

1. Spawn grader runs against each output using the drafted assertions.
2. Save each grader result as `grading.json` in the corresponding run directory, using the required fields `text`, `passed`, and `evidence`.
3. Aggregate benchmark data from `/home/neal/.claude/skills/creating-skills-workspace/iteration-1` with `scripts.aggregate_benchmark`, putting each `with_skill` version before its `old_skill` baseline.
4. Run an analyst pass over benchmark data to look for non-discriminating assertions, skill regressions, timing/token tradeoffs, and repeated failure modes.
5. Launch `eval-viewer/generate_review.py` for human review, or generate a static HTML review file if browser launch is unavailable.
6. Report to the user that the results are ready and direct them to review the Outputs and Benchmark tabs.

## Summary answer to the requested questions

- Spawn strategy: simultaneous, same turn. I would launch all `with_skill` and `old_skill` baseline runs together, not sequentially.
- While runs are in progress: draft objective quantitative assertions, explain them to the user, prepare grading/aggregation/viewer steps, and avoid steering runs from partial output.
- On run completion: immediately save `total_tokens` and `duration_ms` from the completion notification to that run's `timing.json`; this timing data is immediate/unrecoverable if not captured then. Also preserve the run's actual output under its `outputs/` directory, then grade and aggregate after all runs complete.
