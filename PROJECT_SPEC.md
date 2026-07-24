# Project Specification — OS Devin Evaluation Harness

## Problem statement

Most agentic coding demos report a demo, not a benchmark. They show a video of an agent passing a single test, then make sweeping claims about the value of debug loops, AST guards, or sandboxing. There is no rigorous measurement framework that lets you compare configurations head-to-head, with the same task set, the same oracle, and the same scoring rubric.

This project asks a specific, answerable question:

> How much does a self-healing debug loop, AST-based pre-edit guardrails, and per-task sandbox isolation actually move the needle on task success rate — measured, not asserted — and does that hold across different LLM backends?

The product is the measurement instrument. The agent code is the subject, not the deliverable.

---

## Goals

### G1. Reproducible evaluation
A reviewer can clone the repo, run the harness, and produce the same comparison table (modulo model updates). Reproducibility is enforced by:
- Versioned task set with stable IDs and deterministic oracle
- Versioned agent prompts with content hashes
- Fixed temperature (0.0) and explicit model parameters in every trace
- Bounded retry budgets and timeouts
- JSONL traces that are replayable

### G2. Component-level ablation
The harness can isolate the marginal contribution of three architectural components:
- Self-healing debug loop (with vs. without)
- AST pre-edit guard (with vs. without)
- Per-task Docker isolation (vs. local-safe execution)

Each component is toggled independently via config. The headline result is the incremental stack: `baseline → +debug → +ast → full`.

### G3. Cross-model comparison
The same harness runs identically across multiple LLM backends:
- Anthropic Sonnet 4.5
- OpenAI GPT-5.x
- An open-weight coder model (e.g., Qwen-3-Coder-30B via OpenRouter)

This produces a 4×3 matrix with replicates, suitable for a comparison table with confidence intervals.

### G4. Defensible scoring
Success is defined strictly and mechanically:
- Oracle test suite passes
- All deterministic rubric checks pass (no unused imports, no new dependencies, minimal diff, no forbidden file edits)
- No LLM in the scoring loop

Failure classification uses a fixed enum with author-declared ground truth, so `failure_class_correct` is a real metric, not a vibe.

### G5. Safe to run on a developer's laptop
Safety is a baseline, not an experimental variable. Even the `baseline` config runs in a disposable checkout with no network access. The experimental question is purely about degree of isolation, not about whether the host is at risk.

### G6. Defensible as a portfolio artifact
The README, RESULT table, and 3–5 representative traces are sufficient to be defended in an interview. The reader can independently rerun every line of the headline table.

---

## Non-goals

### NG1. Be a coding agent
The agent code is the subject, not the product. We are not competing with OpenHands, Devin, or Aider on agent capability. SWE-bench scores are not the goal.

### NG2. Multi-language support in v1
Python only. Adding more languages is straightforward (the harness is built for it) but debugging the eval framework is harder than debugging the agent. Single language until the eval story is solid.

### NG3. Live WebSocket dashboard
A static HTML viewer that reads `results/raw/` is enough for v1. Real-time streaming is a v2 feature.

### NG4. Production-grade agent tooling
The agent code is research-grade. No need for enterprise patterns (auth, multi-tenant, rate limiting). A single research user is the target.

### NG5. Real Devin replication
The agent is not meant to be Devin. Devin is a product; this is a measurement instrument. The agent exists to be the subject of an ablation.

### NG6. Public leaderboard
The scope is this repo, this evaluator, this task set. We are not running a public benchmark or accepting submissions.

---

## Functional requirements

### FR1. Task loader
- Reads `evals/tasks/<id>/task.json`
- Loads `repo_before` (the broken state) into a fresh workspace
- Loads `oracle.py` (the test suite that must pass)
- Loads `rubric.json` (deterministic checks)
- Validates all required fields are present

### FR2. Config loader
- Reads `configs/<name>.yaml`
- Resolves prompt versions per agent
- Resolves isolation level
- Validates schema

### FR3. Runner
- For each `(task, config, model, replicate)` quadruple:
  - Spin up isolation
  - Execute the agent pipeline
  - Capture structured events to JSONL
  - Run the oracle
  - Run the rubric
  - Compute and emit the score
  - Tear down isolation

### FR4. Agent pipeline
- Planner → Coder → Tester → (optionally) Debugger → Reviewer
- Each agent receives state, emits events, returns updated state
- Debugger loops on Tester failures, bounded by `max_attempts`

### FR5. Tools
- `read_file(path)` — read file contents
- `write_file(path, content)` — write file (AST-gated when enabled)
- `edit_file(path, find, replace)` — surgical edit (AST-gated when enabled)
- `list_files(path)` — list directory
- `search_text(pattern, path)` — grep
- `run_command(cmd, timeout)` — run shell command (in sandbox)
- `run_tests(path)` — run pytest

### FR6. AST guard
- Wraps `write_file` and `edit_file`
- Parses the proposed file with `tree-sitter-python`
- Computes the import graph
- Returns `{allow: bool, reason: str, affected_files: [...]}`

### FR7. Failure classification
- Classifies test failures into a fixed enum of `FailureClass`
- Compares to author-declared `ground_truth_failure_class` in the task
- Returns `exact | family | wrong | n/a`

### FR8. Scorer
- Runs oracle
- Runs all rubric checks
- Computes the four metric families
- Returns scored result JSON

### FR9. Matrix runner
- Reads a matrix specification (configs × models × tasks × replicates)
- Spawns runs (with concurrency control)
- Aggregates results
- Writes per-run JSONL and per-matrix summary

### FR10. Report generator
- Reads scored results
- Produces comparison tables
- Produces failure-mode distribution
- Updates `docs/RESULTS.md`

---

## Non-functional requirements

### NFR1. Performance
- A single task run completes in ≤ 5 minutes wall-clock
- A full matrix (4 configs × 3 models × 18 tasks × 3 replicates = 648 runs) completes in ≤ 24 hours on a single developer machine

### NFR2. Resource limits
- Per-subprocess: 60s CPU, 512MB RAM, 64 file descriptors, 32 processes
- Per-run: 300s wall-clock, 50,000 tokens
- Per-task-loader: validated against the schema before any LLM call

### NFR3. Reproducibility
- Temperature = 0.0 by default
- Seed = 42 when supported
- All model parameters logged in the run header
- Prompt content hashes logged in the run header
- Config hash logged in the run header

### NFR4. Safety
- Local-safe executor: temp dir, no network, `preexec_fn` resource limits, process group killed on exit
- Docker executor: ephemeral container, no host mounts, network blocked, auto-removed
- Both executors strip the environment to a minimal allow-list

### NFR5. Observability
- Every run emits a JSONL trace with one event per line
- Events have monotonic timestamps
- Each event includes `run_id`, `config_id`, `model_id`, `replicate`
- The trace is replayable: re-running the scorer on the trace produces the same scored result

### NFR6. Testability
- All harness modules have unit tests
- The 3 sample tasks (1 easy, 1 medium, 1 hard) are runnable as a smoke test
- `pytest` is green at every commit

### NFR7. Documentation
- Every doc listed in [`README.md`](README.md) exists
- Every doc has the required sections per the schema
- Cross-references between docs resolve
- `scripts/check_docs.py` is the single source of truth for doc completeness

---

## Constraints

### C1. Single-developer scope
This is a solo project. The build order is 5 weeks. Anything beyond that is v2.

### C2. Python-only
The harness is Python 3.12. The eval tasks are Python. The agent prompts are Python. No multi-language support in v1.

### C3. No external services
The only external dependencies are:
- LLM APIs (via LiteLLM)
- Docker daemon (for the `full` config)

No databases, no message queues, no cloud services. State lives on disk.

### C4. Local-first
The harness runs on a developer's laptop. No cloud deployment. No CI on real model backends (CI runs only the smoke test with no LLM calls).

### C5. Defensible numbers
The headline table is the resume. If the numbers are unflattering (e.g., the open-weight model beats the proprietary ones on a config), we publish them anyway. Reproducibility is the point.

---

## Out of scope

- Multi-language agent support (Java, Go, JS, etc.)
- WebSocket live trace streaming
- MCP server exposition
- Web UI for browsing results
- Public benchmark submission
- Production deployment
- Agent parallelization beyond what's needed for the matrix run
- Custom model fine-tuning
- Real-time prompt A/B testing

---

## Success criteria

The project is shippable when:

1. **README** states the thesis and the headline table is real (not placeholder)
2. **`results/reports/comparison.md`** shows the 4×3 table with confidence intervals
3. **All 18 tasks** pass `evals/validate.py` (schema, oracle, rubric, ground truth)
4. **`scripts/run_matrix.py`** runs the full matrix end-to-end without manual intervention
5. **At least 3 traces** are documented in `docs/TRACE_SAMPLES.md`
6. **`pytest`** is green (scorer, AST guard, local-safe sandbox, docker sandbox, loader, runner, failure_class, rubric, prompt_registry)
7. **GitHub Actions** runs pytest + a 1-task smoke test on every PR
8. **`scripts/check_docs.py`** is green (all docs exist with required sections, cross-references resolve)
9. **The numbers are reproducible** — a reviewer can clone, run, and get the same table (modulo model updates)

---

## Risks

### R1. Task design is the bottleneck
A weak task set produces weak numbers. The 18 tasks are the hardest part of the project. Plan for 2 weeks of just task curation.

**Mitigation:** 3 sample tasks (1 easy, 1 medium, 1 hard) built in M1 to validate the schema before scaling.

### R2. Oracle subjectivity
"Tests pass" is mechanical. "Behavior matches rubric" is judgment. The deterministic rubric checks (no unused imports, no new deps, minimal diff, no forbidden file edits) are the answer — they're mechanical, not LLM-judged.

**Mitigation:** Rubric is implemented as pluggable deterministic checks in `harness/rubric/`. New checks can be added without LLM involvement.

### R3. Statistical noise
648 runs sounds like a lot, but variance per run is real. Single-run numbers are misleading.

**Mitigation:** 3 replicates per `(task, config, model)` cell. Report 95% confidence intervals via Wilson score interval for proportions.

### R4. Unflattering headline numbers
Possible that the debugger loop moves the needle less than expected, or that the open-weight model surprises us.

**Mitigation:** Publish the actual numbers anyway. This is the whole point.

### R5. Model API changes
Providers update models. A run from week 1 may not be reproducible against the same model_id in week 5.

**Mitigation:** Log model version (not just model_id) in the trace. Pin to specific dated snapshots where possible.

---

## Glossary

| Term | Definition |
|---|---|
| **Harness** | The experiment runner. Orchestrates (task, config, model, replicate) → result. |
| **Task** | A self-contained coding problem with a repo, oracle, and rubric. |
| **Oracle** | The ground-truth test suite that must pass for a task to count as solved. |
| **Rubric** | A set of deterministic checks beyond the oracle (lint, diff, deps). |
| **Config** | A YAML file specifying which agents are enabled, the isolation level, and prompt versions. |
| **Ablation** | The 4-config incremental stack that isolates marginal contribution per component. |
| **Isolation** | The execution environment (local-safe or Docker). Always safe; varies by degree. |
| **Reproducibility** | The property that a reviewer can rerun and get the same numbers. |
| **Failure class** | The categorized reason a test failed (assertion, import, type, etc.). |
| **Ground truth failure class** | The author-declared correct classification of the failure. |
| **Replicate** | A repeated run with the same (task, config, model) but a fresh seed/state. |

---

## References

- [`README.md`](README.md) — entry point
- [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) — status, what's built vs. planned
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component diagram, data flow
- [`docs/FLOW.md`](docs/FLOW.md) — end-to-end execution flow
- [`docs/EVAL_METHODOLOGY.md`](docs/EVAL_METHODOLOGY.md) — scoring, metrics, statistical protocol
- [`docs/TASK_DESIGN.md`](docs/TASK_DESIGN.md) — task schema, authoring guide
- [`docs/CONFIG_ABLATION.md`](docs/CONFIG_ABLATION.md) — the 4 configs and what each isolates
- [`docs/SAFETY.md`](docs/SAFETY.md) — safety baseline + experimental isolation
- [`docs/RESULTS.md`](docs/RESULTS.md) — auto-generated results
- [`docs/FAILURE_ANALYSIS.md`](docs/FAILURE_ANALYSIS.md) — categorized failure modes
- [`docs/TRACE_SAMPLES.md`](docs/TRACE_SAMPLES.md) — representative full traces
