  There is no defensible universal ranking such as “AI is best at Python, then JavaScript, then Rust.” The evidence is too Python-heavy and

  task-dependent.

  The most useful practical answer is:

  ┌────────────────────────────────────────┬───────────────────────────────────────────────────────────────┬─────────────────────────────────────────┐

  │               Situation                │               Languages with strongest evidence               │               Confidence                │

  ├────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤

  │ Typical repository work—scripts, APIs, │ Python, then JavaScript/TypeScript                            │ Moderate–high for Python; moderate for  │

  │  tests, bug fixes                      │                                                               │ JS/TS                                   │

  ├────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤

  │ Algorithmic/function-level generation  │ Python, JavaScript, TypeScript, C++, and in one multilingual  │ Moderate                                │

  │                                        │ study Scala                                                   │                                         │

  ├────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤

  │ Large real-world repair tasks          │ Python                                                        │ High—but only because the leading       │

  │                                        │                                                               │ benchmark corpus is principally Python  │

  ├────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤

  │ Systems / performance /                │ Rust, Go, C/C++ can be generated effectively, but no evidence │ Low–moderate                            │

  │ memory-sensitive work                  │  supports a general ordering against Python or JS/TS          │                                         │

  ├────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤

  │ Niche / lower-resource ecosystems      │ Capability is substantially less well measured; assume more   │ Low                                     │

  │                                        │ verification is needed                                        │                                         │

  └────────────────────────────────────────┴───────────────────────────────────────────────────────────────┴─────────────────────────────────────────┘

  What the research supports

  1. Python has the deepest evidence base, not necessarily uniquely higher intrinsic model capability.

  HumanEval and MBPP are Python-only function-synthesis benchmarks; SWE-bench Verified also overwhelmingly evaluates Python repositories. Thus, modern

  coding models have been tested most thoroughly on Python tasks. High scores there establish strong Python competence, but cannot rank Python above other

  languages.

  2. Comparable multilingual evidence does not show Python universally winning.

  MultiPL-E translates HumanEval/MBPP-style tasks into 18 languages. Its authors found that Codex matched or exceeded its Python performance in

  JavaScript, C++, Scala, and TypeScript on their translated tasks. That means a “Python is always best” rule is contradicted by the available

  cross-language experiment.

  3. Python/JavaScript/TypeScript are usually the safest default for ordinary application work.

  This is an inference from their large public code ecosystems, broad library exposure, and extensive benchmark coverage—not a demonstrated

  across-the-board ranking. For new scripts, automation, web integrations, and tests, models generally have abundant examples to imitate in these

  ecosystems.

  4. Models may choose Python too often.

  An ACL Findings study of eight LLMs found a preference for familiar/popular languages and libraries rather than task-fit; in its test setup, models

  frequently selected Python where a systems-oriented alternative could better satisfy performance or safety requirements. Treat the model’s default

  language choice as a prior, not an architecture decision.

  5. Task and ecosystem matter more than language syntax alone.

  A model can be very good at solving a small Rust or C++ algorithm while being weaker at a production Rust workspace with ownership-heavy interfaces,

  build scripts, macros, framework conventions, and sparse tests. The same applies to Java enterprise frameworks, C/C++ build systems, and niche

  functional-language stacks.

  Practical guidance

  - Choose Python for automation, data work, glue code, internal tools, and many agent-driven tasks—unless runtime, deployment, or safety requirements

  point elsewhere.

  - Choose TypeScript/JavaScript for browser and Node/Bun ecosystems. Ask the model to use the project’s existing framework and type-checker rather than

  generating generic JavaScript.

  - Choose Go for simple deployable services and concurrent systems tools; the language’s standard-library conventions make generated code relatively easy

  to inspect.

  - Choose Rust when memory safety or predictable performance materially matters, but require cargo test, cargo clippy, and ideally focused

  ownership/error-path review.

  - Choose Java/C#/Kotlin when integrating with their existing mature ecosystems; models can work well here, but should be constrained to your framework,

  build tool, and repository conventions.

  - For C/C++ or niche languages, use AI as an accelerator, not an authority: compile with strict warnings, run sanitizers or static analysis, and retain

  human review.

  How to evaluate for your own project

  The best language for your AI-assisted workflow is empirical:

  1. Select 10–20 representative tasks: a bug fix, a feature, tests, a refactor, an integration, and error handling.

  2. Give each language’s implementation the same repository context and acceptance tests.

  3. Compare:

    - first-pass test success,

    - number of repair turns,

    - introduced defects,

    - review effort,

    - runtime/resource behavior,

    - maintainability in the target ecosystem.

  4. Prefer the language that minimizes total validated delivery cost, not merely generated tokens or first-draft speed.

  Primary research sources

  - Cassano et al., MultiPL-E: A Scalable and Extensible Approach to Benchmarking Neural Code Generation — multilingual translation/evaluation across 18

  languages; the clearest direct evidence against a universal Python-first ranking.

  - Chen et al., Evaluating Large Language Models Trained on Code — original HumanEval paper; establishes that HumanEval measures Python, not

  cross-language competence.

  - Jain et al., LiveCodeBench (ICLR 2025) — contamination-aware, continuously refreshed coding evaluation; useful for current model quality, but not a

  cross-language ranking.

  - Jimenez et al., SWE-bench — repository-level software-engineering evaluation; its language distribution limits language-to-language comparisons.

  - Twist et al., A Study of LLMs’ Preferences for Libraries and Programming Languages — evidence that language selection can reflect

  familiarity/popularity rather than suitability.

  The research draft was completed in an isolated worktree at docs/intelligence/[research-llm-language-competency.md](http://research-llm-language-competency.md); I have not copied it into the main

  repository because the project instructions require confirmation before documentation edits, and it needs the above caveats to avoid turning narrow

  benchmark results into a misleading universal hierarchy.
