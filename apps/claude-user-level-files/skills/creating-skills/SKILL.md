---
name: creating-skills
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy.
---

# Creating Skills

The process:

- Decide what the skill should do
- Write a draft
- Create test prompts and run claude-with-access-to-the-skill on them
- Evaluate results qualitatively and quantitatively
  - While runs are in progress, draft quantitative assertions and explain them to the user
  - Use `scripts/generate_review.py` to show results
- Rewrite based on feedback and benchmark findings
- Repeat until satisfied
- Expand the test set and try again at larger scale

Figure out where the user is and jump in. If they say "I want to make a skill for X", help narrow it down, write a draft, set up test cases, run them, and iterate. If they already have a draft, go straight to eval/iterate. If they say "just vibe with me", skip the formal evals.

This says where to start, not what to skip. The interview and EDD decision below still gate the first edit to SKILL.md on every path — including an existing draft, where they're the only thing establishing what the skill is for and whether evals apply.

After the skill is done, offer to run the description optimizer (`scripts/run_loop.py`) to improve triggering accuracy.

---

## Creating a skill

### Interview

Before any SKILL.md creation or edits, confirm:
1. What should this skill enable Claude to do?
2. When should it trigger, and when should it not?
3. What's the expected output format?
4. Should we set up evals? (yes for objectively verifiable outputs; often no for subjective ones)

Ask these questions, wait for the user's answers, then post a short "Interview complete" summary with these 4 fields. Do not fill in answers yourself.

Proactively ask about edge cases, input/output formats, example files, success criteria, and dependencies. Check available MCPs — if useful for research, use subagents in parallel.

Hard stop: if you're about to draft or modify SKILL.md without the interview-complete summary, stop and run the interview first.

### Ground in Real Source Material

Don't invent skills from generic knowledge. Ground the skill in:
- a successful hands-on task (steps that worked, corrections made)
- internal docs, slash commands, prompts, style guides, API specs, config files
- code review comments, issue history, version control patches
- real failure cases and their resolutions

### Conciseness Principle

The context window is shared. Once SKILL.md loads, every token competes with the system prompt, conversation history, and the user's request.

**Default assumption:** The agent is already very capable. Only add context it doesn't already have. For every piece of content ask:
- Does the agent really need this explanation?
- Can I assume the agent knows this?
- Does this paragraph justify its token cost?

### Search for Existing Skills

Before creating, check the existing skills directory.
- Exact match: reuse it
- Strong overlap: refactor or extend it
- No match: proceed

One concept, one skill. Don't create parallel skills that differ only in wording.

### Evaluation-Driven Development

Decide this before drafting — whether evals are in scope shapes what you write.
When they are, the body is written to pass them rather than retrofitted to fit.

Post an EDD decision:
- `evals_in_scope: yes|no`
- Rationale
- Initial eval prompts (if yes)

When evals are in scope:
1. **Identify gaps:** Run the agent without the skill. Document failures.
2. **Create evaluations:** Build 3 scenarios targeting those gaps.
3. **Establish baseline:** Measure without the skill.
4. **Write minimal instructions:** Just enough to pass evaluations.
5. **Iterate:** Compare against baseline and refine.

Hard stop: don't write any SKILL.md body content without the EDD decision summary.

### Write the SKILL.md

Start from `assets/SKILL_template.md`. Fill in:

- **name**: Skill identifier (kebab-case, matches directory name exactly)
- **description**: The only thing Claude sees when deciding whether to load a skill. Write as routing logic, not marketing copy — answer: when to use, when not to use, outputs. Write in third person. Front-load trigger words. Claude tends to undertrigger, so lean slightly pushy. Include explicit negative cases ("Don't use when...") to reduce misfires.
- **compatibility**: Required tools/dependencies (optional, omit if not needed)

**Content rules:**
- Provide defaults, not menus of equal options
- Favor reusable procedures over one-off declarations
- Match specificity to fragility: prescriptive for risky steps, flexible where variation is fine
- Avoid time-sensitive information; use a collapsible "Old patterns" section for legacy context
- If the agent handles the task well without the skill, the skill may not be adding value

**Degrees of freedom:**
- **High freedom** (prose): Multiple valid approaches, context-dependent. E.g. code review, research synthesis.
- **Medium freedom** (pseudocode/params): Preferred pattern, some variation OK. E.g. configurable report.
- **Low freedom** (exact script/sequence): Fragile or consistency-critical operations. E.g. DB migrations.

Once the draft exists, run checks R1 and R2 from `references/prose-checks.md`
against it by hand — routing content stranded in the body, and a description
that reads as a summary instead of a trigger. Both are cheap to check and both
cause a skill to not load at all, which no eval will explain: the runs just come
back looking like the baseline. Catching them here saves a full iteration. The
remaining checks run at validation time.

### Skill Structure

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/    - Executable code for deterministic/repetitive tasks
    ├── references/ - Docs loaded into context as needed
    └── assets/     - Files used in output (templates, icons, fonts)
```

No `README.md` inside the skill folder — all docs go in `SKILL.md` or `references/`.

**Three-level loading:**
1. **Metadata** (name + description) — Always in context
2. **SKILL.md body** — In context when skill triggers (<500 lines)
3. **Bundled resources** — Loaded on demand

If SKILL.md approaches 500 lines, move detail into `references/`. For multi-domain skills, organize references by variant (e.g. `references/aws.md`, `references/gcp.md`) so Claude loads only the relevant file.

**Writing patterns:** Use imperative form. Define output formats explicitly when they matter. Include input/output examples for non-obvious transformations.

### Bundling Scripts

Use one-off package commands directly in SKILL.md for short commands:
- `uvx`, `pipx run`, `npx`, `bunx`, `deno run`, `go run`
- Pin versions for reproducibility (e.g. `npx eslint@9`)

Bundle a script in `scripts/` when:
- Logic is reused across runs
- The command is too complex to get right ad hoc
- Validation or parsing should be tested once and reused
- Agents keep reinventing the same helper across test runs

Scripts save tokens and improve reliability over code regenerated from scratch each run.

Use self-contained dependency declarations: PEP 723 for Python (`uv run`), `npm:`/`jsr:` for Deno, auto-install for Bun.

Read `references/script-design.md` when writing scripts or designing a plan-validate-execute workflow.

### Reference File Conventions

- Use relative paths from the skill root
- Keep references one level deep from `SKILL.md`
- Tell the agent when to load each file (e.g. "Read `references/api-errors.md` if the API returns non-200")
- For files >100 lines, include a table of contents at the top
- List available scripts explicitly in `SKILL.md`

### Test Cases

After drafting, propose 2-3 realistic test prompts. Share them: "Here are a few test cases — do these look right, or do you want to add more?"

Save to `evals/evals.json` (prompts only, no assertions yet):

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

See `references/schemas.md` for the full schema including the `assertions` field.

---

## Running and evaluating test cases

One continuous sequence — don't stop partway. Do NOT use `/skill-test` or any other testing skill.

Put results in `<skill-name>-workspace/` as a sibling to the skill directory, organized by `iteration-<N>/` and within that by eval name.

### Step 1: Spawn all runs in the same turn

For each test case, spawn two subagents simultaneously — one with the skill, one baseline. Don't do with-skill first and baseline later.

**With-skill run:**
```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/<eval-name>/with_skill/outputs/
- Outputs to save: <what the user cares about>
```

**Baseline run:**
- **New skill**: no skill at all, save to `without_skill/outputs/`
- **Improving existing**: snapshot first (`cp -r <skill-path> <workspace>/skill-snapshot/`), point baseline at snapshot, save to `old_skill/outputs/`

Write `eval_metadata.json` for each eval (assertions empty for now):
```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

### Step 2: While runs are in progress, draft assertions

Draft quantitative assertions and explain them to the user. Good assertions are objectively verifiable with descriptive names. Don't force assertions onto subjective outputs — those need human judgment.

Update `eval_metadata.json` and `evals/evals.json` with assertions once drafted.

### Step 3: Capture timing data as runs complete

When each subagent completes, save the notification's `total_tokens` and `duration_ms` immediately to `timing.json` in the run directory. This data exists only in the completion notification — it is not recoverable afterward. See `references/schemas.md` for the full schema.

### Step 4: Grade, aggregate, and launch the viewer

1. **Grade** — spawn a grader subagent using `agents/grader.md`. Save to `grading.json`. Use fields `text`, `passed`, `evidence` (not `name`/`met`/`details`). Use scripts for programmatic checks rather than eyeballing.

2. **Aggregate** — run from the skill-creator directory:
   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```
   Put each `with_skill` version before its baseline. See `references/schemas.md` if generating `benchmark.json` manually.

3. **Analyst pass** — read benchmark data and surface patterns. See `agents/analyzer.md` for what to look for: non-discriminating assertions, high-variance evals, time/token tradeoffs.

4. **Launch the viewer:**
   ```bash
   nohup python <skill-creator-path>/scripts/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json \
     > /dev/null 2>&1 &
   VIEWER_PID=$!
   ```
   For iteration 2+, add `--previous-workspace <workspace>/iteration-<N-1>`.

   **Headless environments:** use `--static <output_path>` to write a standalone HTML file. Feedback downloads as `feedback.json` when the user clicks "Submit All Reviews" — copy it into the workspace directory.

5. Tell the user: "I've opened the results in your browser. 'Outputs' tab for per-test feedback, 'Benchmark' tab for quantitative comparison. Come back when done."

### Step 5: Read the feedback

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "the chart is missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."}
  ],
  "status": "complete"
}
```

Empty feedback = looked fine. Focus improvements on evals with specific complaints.

Kill the viewer: `kill $VIEWER_PID 2>/dev/null`

---

## Improving the skill

This is the heart of the loop.

### How to think about improvements

1. **Generalize from the feedback.** Skills will be used across many prompts by many different people — not just the examples in front of you. When making improvements, generalize from the feedback rather than fitting to it. If a change would only work for the exact example being tested, it's the wrong change — that's overfitting. Ask: "Would this instruction help on a prompt I haven't seen yet?" If the answer is no, reframe it at a higher level of abstraction. When something is stubbornly hard to fix with tighter instructions, try a different framing or a different pattern of working — sometimes a metaphor or a structural shift lands better than more constraints.

2. **Keep the prompt lean.** Remove things that aren't pulling their weight. Read the transcripts, not just the final outputs — if the skill is causing the model to waste time on unproductive steps, cut the parts driving that behavior. If the skill has grown past 500 lines, move detail to `references/` rather than trimming — content worth keeping belongs there, not on the cutting room floor.

   Never trim validation, security, or guardrails around destructive and irreversible steps. Cut explanation, not safety. Leanness is about removing what the model already knows, and it doesn't know which operations in *your* domain are unrecoverable — that has to stay on the page. A skill that reads as terse because the warnings were cut is worse than one that reads as verbose.

3. **Explain the why.** Explain the reasoning behind instructions rather than issuing mandates. LLMs have good theory of mind — given the why, they generalize better than when given rigid rules. If you find yourself reaching for all-caps imperatives or rigid structures, that's a yellow flag. Try reframing: explain the reasoning so the model understands *why* rather than just following a rule.

4. **Look for repeated work across test cases.** If all 3 test runs independently wrote `create_docx.py` or `build_chart.py`, bundle that script. Write it once in `scripts/` and tell the skill to use it.

Take time with this. Write a draft revision, then read it with fresh eyes before applying it. Try to understand what the user is actually experiencing, not just what they wrote.

### The iteration loop

1. Apply improvements to the skill
2. Rerun all test cases into `iteration-<N+1>/`, including baseline runs
3. Launch the reviewer with `--previous-workspace` pointing at the previous iteration
4. Wait for the user to review
5. Read feedback, improve again, repeat

Keep going until the user is happy, feedback is empty, or you're not making meaningful progress.

---

## Advanced: Blind comparison

For rigorous A/B comparison between two skill versions, read `agents/comparator.md` and `agents/analyzer.md`. Give two outputs to an independent agent without revealing which is which; it judges quality and explains why the winner won. Optional — the human review loop is usually sufficient.

---

## Description Optimization

The description field is the primary triggering mechanism. After creating or improving a skill, offer to optimize it.

### Step 1: Generate trigger eval queries

Create 16-20 queries — a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

Queries must be realistic and concrete — include file paths, personal context, column names, URLs, backstory. Mix lengths; some lowercase/casual/abbreviated. Focus on edge cases, not clear-cut ones.

**Should-trigger (8-10):** Different phrasings of the same intent — formal and casual. Include cases where the user doesn't name the skill explicitly but clearly needs it. Include cases where this skill competes with another but should win.

**Should-not-trigger (8-10):** Near-misses — queries sharing keywords but needing something different. Naive keyword matching would trigger; correct routing doesn't. Make them genuinely tricky, not obviously irrelevant.

Skills only trigger for tasks where Claude would benefit from consulting one — simple one-step queries won't trigger regardless of description quality. Make eval queries substantive.

### Step 2: Review with user

1. Read `assets/eval_review.html`
2. Replace `__EVAL_DATA_PLACEHOLDER__`, `__SKILL_NAME_PLACEHOLDER__`, `__SKILL_DESCRIPTION_PLACEHOLDER__`
3. Write to `/tmp/eval_review_<skill-name>.html` and open it
4. User edits queries, toggles flags, clicks "Export Eval Set"
5. File downloads to `~/Downloads/eval_set.json` (check for `eval_set (1).json` if multiple)

### Step 3: Run the optimization loop

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from your system prompt so tests match what the user experiences. Periodically tail output to give the user iteration/score updates.

The loop splits evals 60/40 train/test, evaluates the current description (3 runs per query), proposes improvements based on failures, and re-evaluates up to 5 times. Returns `best_description` selected by test score to avoid overfitting.

### Step 4: Apply the result

Update SKILL.md frontmatter with `best_description`. Show before/after and report scores.

### Validate the skill

Two passes. The first checks the container — files, frontmatter, tokens, links.
The second checks the writing.

**1. Structural — `skill-validator`:**

```bash
bash scripts/ensure_validator.sh          # installs on first use; checks weekly after
skill-validator check <path/to/skill-folder>
```

Exit codes: `0` clean, `1` errors, `2` warnings, `3` usage error.

Fix every error. Read every warning and decide — don't suppress them wholesale
with `--allow-dirs` or `--skip-orphans`, because a warning you hid is a warning
you didn't evaluate. Two known-benign warnings on this skill in particular:

- `agents/`, `evals/` flagged as unknown directories — deliberate; both are
  Claude Code conventions the agentskills spec doesn't cover.
- Python module imports (`from scripts.utils import ...`) read as
  extension-less file references. Adding `.py` would break the import.

If `ensure_validator.sh` reports a newer release, it will not upgrade on its own
— new versions add new checks, and a clean skill shouldn't start failing without
you choosing that. Run `bash scripts/ensure_validator.sh --upgrade` when ready.

**2. Prose — `references/prose-checks.md`:**

Spawn a subagent using `agents/validator.md`. It applies the prose checks and
returns a findings table. These catch skills that are spec-clean but written in
a way that makes them trigger badly or waste context — `skill-validator` reads
structure, not meaning.

Then verify by hand:
- Run the skill against a real task and review the execution trace
- Confirm the directory name matches the `name` field exactly

**Common gotchas:**
- `name` must use hyphens, not underscores
- Don't leave optional frontmatter placeholder strings — omit unused fields entirely

---

## Reference files

- `agents/grader.md` — Evaluate assertions against outputs
- `agents/comparator.md` — Blind A/B comparison
- `agents/analyzer.md` — Analyze why one version beat another
- `agents/validator.md` — Apply prose checks, report findings table
- `references/schemas.md` — JSON schemas for evals.json, grading.json, benchmark.json, etc.
- `references/script-design.md` — Script design patterns and plan-validate-execute
- `references/prose-checks.md` — Writing-quality checks `skill-validator` can't make
- `assets/SKILL_template.md` — Starting template; copy to new skill directory as `SKILL.md`
- `assets/eval_review.html` — HTML template for trigger eval review
- `assets/viewer.html` — HTML template for the eval results viewer
- `scripts/ensure_validator.sh` — Install `skill-validator`, report new releases
- `scripts/generate_review.py` — Build and serve the eval results viewer
- `scripts/aggregate_benchmark.py` — Aggregate grading results into benchmark.json
- `scripts/run_loop.py` — Description optimization loop
- `scripts/run_eval.py` — Run a single trigger eval against a description
- `scripts/improve_description.py` — Propose description revisions from failures
- `scripts/generate_report.py` — Render the optimization loop's HTML report
- `scripts/utils.py` — Shared helpers (`parse_skill_md`)
- `scripts/package_skill.py` — Package skill directory into .skill file

---

Core loop:

- Figure out what the skill is about
- Draft or edit the skill
- Run claude-with-access-to-the-skill on test prompts
- Evaluate outputs (benchmark + viewer)
- Repeat until satisfied
- Package and return to user

Add steps to your todo list so you don't lose track.

**Final notes:**
- If the skill grows too large, move detail into `references/` rather than expanding `SKILL.md`.
- If several skills always activate together, reconsider whether the skill boundaries are wrong.
- Start with the minimum viable `SKILL.md` and add complexity only when it improves agent performance.
