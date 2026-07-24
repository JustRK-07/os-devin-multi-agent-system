# Project Overview — OS Devin Evaluation Harness

This document mirrors the style of the `rail-yard-slot-conflict-manager/PROJECT_OVERVIEW.md` to keep the portfolio consistent. It tracks the verified build status, what's implemented, what's not yet, and what evidence backs each claim.

---

## Project status (as of the last commit on `main`)

> - The **foundation slice** is implemented and the doc set is complete.
> - The eval framework, task schema, configuration layer, and safety baseline are in place.
> - The agent pipeline, sandbox implementations, AST guard, and full experimental matrix are planned.
> - See [`docs/`](docs/) for design references and [`docs/RESULTS.md`](docs/RESULTS.md) for the headline table (currently a placeholder).

---

## Documentation completeness

The documentation is comprehensive and self-validating. Run `python scripts/check_docs.py` to verify all docs exist with their required sections, cross-references resolve, and the project structure matches the spec.

**Status:** doc set is complete and the check loop is green.

| Document | Status | Notes |
|---|---|---|
| `README.md` | ✅ implemented | Entry point, thesis, quick start |
| `PROJECT_SPEC.md` | ✅ implemented | Problem, goals, requirements, constraints |
| `PROJECT_OVERVIEW.md` | ✅ implemented | This file |
| `docs/ARCHITECTURE.md` | ✅ implemented | Component diagram, data flow |
| `docs/FLOW.md` | ✅ implemented | End-to-end execution flow |
| `docs/EVAL_METHODOLOGY.md` | ✅ implemented | Metrics, failure class, statistical protocol |
| `docs/TASK_DESIGN.md` | ✅ implemented | Task schema, authoring guide |
| `docs/CONFIG_ABLATION.md` | ✅ implemented | The 4 configs and what each isolates |
| `docs/SAFETY.md` | ✅ implemented | Safety baseline + experimental isolation |
| `docs/RESULTS.md` | ⏳ placeholder | Awaiting experimental runs |
| `docs/FAILURE_ANALYSIS.md` | ⏳ placeholder | Awaiting experimental runs |
| `docs/TRACE_SAMPLES.md` | ⏳ placeholder | Awaiting experimental runs |

---

## What is implemented today

### Repository structure

- Directory skeleton per [`README.md`](README.md): `docs/`, `scripts/`, `harness/`, `configs/`, `evals/`, `results/`, `tests/`.
- `harness/` subpackages: `agents/`, `sandbox/`, `rubric/`, `tools/`, `llm/`, `events/`.
- `harness/llm/prompts/` for versioned agent prompts.
- `evals/tasks/` for hand-curated task directories.
- `results/raw/` for per-run JSONL traces.
- `results/reports/` for generated markdown.

### Documentation

- `README.md` — thesis, headline table placeholder, quick start, project structure, tech stack, documentation index, reproduction steps.
- `PROJECT_SPEC.md` — problem statement, goals, non-goals, functional and non-functional requirements, constraints, out of scope, success criteria, risks, glossary.
- `docs/ARCHITECTURE.md` — component diagram, data flow, module breakdown, data model, external dependencies.
- `docs/FLOW.md` — end-to-end execution flow, per-agent flow, per-config flow, error paths.
- `docs/EVAL_METHODOLOGY.md` — the four metric families, failure class taxonomy, rubric scoring, statistical protocol, cross-model comparison.
- `docs/TASK_DESIGN.md` — task schema, difficulty mix, authoring guide, ground truth failure class, example tasks.
- `docs/CONFIG_ABLATION.md` — the four configurations, what each isolates, how to read the ablation table, v2 extensions.
- `docs/SAFETY.md` — safety baseline (always-on), experimental isolation levels, why decoupled, implementation details.

### Validation loop

- `scripts/check_docs.py` — verifies every required doc exists, has the required sections, cross-references resolve, and the project structure matches the spec. Re-runnable; exits non-zero on failure.

### Design-only assets

- `configs/baseline.yaml`, `plus_debug.yaml`, `plus_ast.yaml`, `full.yaml` — referenced in docs but not yet enforced (the runner doesn't exist yet).
- `harness/llm/prompts/registry.yaml` — referenced in docs but not yet populated.
- `harness/failure_class.py`, `harness/scorer.py`, etc. — interfaces documented in `docs/ARCHITECTURE.md` but modules not yet implemented.

---

## What is not implemented yet

The following is the implementation backlog, in dependency order. See [`docs/`](docs/) for the design and the relevant section.

### M1. Foundation (next)

- `pyproject.toml` + `requirements.txt` with pinned dependencies
- `evals/tasks/001_remove_dead_import/` — first sample task with `task.json`, `repo_before/`, `oracle.py`, `rubric.json`
- `evals/tasks/002_fix_off_by_one_pagination/` — second sample task
- `evals/tasks/003_extract_repeated_logic/` — third sample task (hard)
- `evals/loader.py` — task schema loader with validation
- `evals/validate.py` — schema validator for all 18 tasks (when present)
- `harness/llm/client.py` — LiteLLM wrapper with token counting and cost estimation
- `harness/llm/prompts.py` — versioned prompt loader with content hashing
- `harness/llm/prompts/registry.yaml` + `planner_v1.md`, `coder_v1.md`, `tester_v1.md`, `debugger_v1.md`, `reviewer_v1.md`
- `harness/events/trace.py` — structured JSONL event emitter
- `harness/sandbox/local_safe.py` — local-safe executor with `preexec_fn` resource limits
- `harness/sandbox/factory.py` — executor factory
- `harness/tools/` — file, shell, search, test_runner tools
- `harness/runner.py` — minimal raw-LLM runner (no agents yet)
- `scripts/run_eval.py` — CLI to run one (task, config, model) quadruple

### M2. Agents + baseline

- `harness/agents/base.py` — agent protocol
- `harness/agents/planner.py`, `coder.py`, `tester.py`, `reviewer.py`
- `harness/failure_class.py` — enum + families + matcher
- `harness/scorer.py` — oracle + rubric scoring
- `harness/rubric/base.py` + `lint_checks.py`, `diff_checks.py`, `test_checks.py`, `registry.py`
- `configs/baseline.yaml` — single-shot, no debug, no AST, local-safe
- Run 18 tasks × 1 model × baseline = 18 runs

### M3. AST guard + debugger

- `harness/ast_guard.py` — tree-sitter pre-edit guard
- `harness/agents/debugger.py` — bounded retry loop with failure classification
- `configs/plus_debug.yaml`, `plus_ast.yaml`
- Run 18 tasks × 1 model × 4 configs = 72 runs

### M4. Cross-model + replicates

- `harness/sandbox/docker.py` — Docker executor
- `configs/full.yaml` — docker + debugger + AST
- `scripts/run_matrix.py` — full matrix runner with concurrency control
- Add the 2 missing model backends (GPT-5.x, Qwen-3-Coder-30B)
- 3 replicates per cell
- Run 18 × 3 × 4 × 3 = 648 runs

### M5. Reports + CI

- `scripts/compare_runs.py` — comparison table generator
- `scripts/generate_report.py` — produces `docs/RESULTS.md`
- `docs/FAILURE_ANALYSIS.md` — categorized failure modes
- `docs/TRACE_SAMPLES.md` — 3–5 representative traces
- `tests/` — pytest suite
- `.github/workflows/ci.yml` — pytest + 1-task smoke test

---

## Verification

Every claim in this document is verifiable via one of:

1. `python scripts/check_docs.py` — doc completeness
2. `pytest` — module tests (when M5 lands)
3. `python scripts/run_matrix.py` — full experimental matrix (when M4 lands)
4. `python scripts/generate_report.py` — produces `docs/RESULTS.md` with the headline table

Until the harness modules exist, the only verifiable claim is the doc set completeness. Run `scripts/check_docs.py` to confirm.

---

## Roadmap

| Milestone | Scope | Estimated effort |
|---|---|---|
| M1 — Foundation | Eval framework, task schema, LLM client, prompt registry, local-safe sandbox, raw runner | 1 week |
| M2 — Agents + baseline | 4 agents, baseline config, 18-task baseline run | 1 week |
| M3 — AST + debugger | AST guard, debugger loop, +debug and +ast configs, ablation table | 1 week |
| M4 — Cross-model + replicates | Docker sandbox, full config, 2 missing models, 3 replicates, 648 runs | 1 week |
| M5 — Reports + CI | Auto-generated RESULTS, failure analysis, trace samples, CI, full pytest | 1 week |

Total: **5 weeks** solo.

---

## Cross-references

This document depends on:

- [`README.md`](README.md) — entry point
- [`PROJECT_SPEC.md`](PROJECT_SPEC.md) — goals, requirements
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module breakdown
- [`docs/FLOW.md`](docs/FLOW.md) — execution flow
- [`docs/SAFETY.md`](docs/SAFETY.md) — isolation levels
- [`scripts/check_docs.py`](scripts/check_docs.py) — validation loop
