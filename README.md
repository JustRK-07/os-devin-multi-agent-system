# OS Devin — Evaluation Harness for Autonomous Coding Agents

> **Status: design and documentation foundation, not a functioning autonomous coding agent.** This repository specifies a planned evaluation harness for multi-agent coding systems, with a documented 18-task benchmark design, four experimental configurations, and three proposed LLM backends. The agent implementations, executable evaluations, and outcome measurements have **not yet been committed**.
>
> The goal is to evaluate how debugging loops, AST-based safeguards, and execution isolation affect coding-task outcomes—not to present unverified benchmark results.

---

## Headline result (placeholder)

**No experimental success rates or benchmark results are available yet.** The following matrix describes the planned comparison; `TBD` means the experiment has not been executed. See [`docs/RESULTS.md`](docs/RESULTS.md) for the results placeholder and [`docs/EVAL_METHODOLOGY.md`](docs/EVAL_METHODOLOGY.md) for the proposed scoring methodology.

| Config          | Sonnet 4.5 | GPT-5.x | Qwen-3-Coder-30B |
|-----------------|------------|---------|------------------|
| baseline        | _TBD_      | _TBD_   | _TBD_            |
| +debug          | _TBD_      | _TBD_   | _TBD_            |
| +ast            | _TBD_      | _TBD_   | _TBD_            |
| full            | _TBD_      | _TBD_   | _TBD_            |

Marginal contributions (incremental stack, expected):
- `baseline → +debug`: self-healing retry loop
- `+debug → +ast`: AST pre-edit guard (scope discipline)
- `+ast → full`: Docker-managed per-task isolation

---

## Project status

The **documentation foundation** is committed, including architecture, evaluation methodology, planned task schema, safety considerations, and ablation design. The executable runner, agents, scoring implementation, AST guard, Docker executor, test suite, and benchmark matrix are **not present in the current default branch**.

The repository contains a documentation-validation script at [`scripts/check_docs.py`](scripts/check_docs.py). It verifies documentation structure and references; it does **not** test autonomous coding capabilities. See [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) for the code-versus-roadmap breakdown.

---

## What this is, and what it isn't

**This is currently:** a documented engineering and experimental design for measuring agentic-coding components, with a repository structure prepared for future implementation.

**This is not yet:** an executable four-agent LangGraph system, a working Docker-backed agent sandbox, or a completed benchmark. Descriptions of those components in the specifications are design targets, not claims of working functionality.

**Intended evaluation:** compare a baseline with debugging, AST guardrails, and Docker isolation using oracle-based scoring and repeatable runs. Results should be published only after the components and experiments are actually implemented and verified.

---

## Quick start

### Inspect the documented design

Start with [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) for the verified implementation status, [`PROJECT_SPEC.md`](PROJECT_SPEC.md) for requirements, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the proposed architecture.

### Validate documentation

Requires Python 3.12+ for the planned project; the documentation checker itself uses the standard library.

```bash
git clone https://github.com/JustRK-07/os-devin-multi-agent-system.git
cd os-devin-multi-agent-system
python scripts/check_docs.py
```

This validates documentation presence, sections, local references, and directory layout. **It does not run coding agents or benchmark tasks.**

### Planned execution commands — not available yet

The intended `scripts/run_eval.py`, `scripts/run_matrix.py`, and `scripts/generate_report.py` commands are specified in the design documents but are **not committed as runnable files**. Do not use them as evidence of working evaluations. See [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) and [`docs/FLOW.md`](docs/FLOW.md) for the proposed execution flow.

---

## Project structure

```
os-devin-multi-agent-system/
├── README.md                              # this file
├── PROJECT_SPEC.md                        # full project specification
├── PROJECT_OVERVIEW.md                    # status, what's built vs. planned
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md                    # component diagram, data flow
│   ├── FLOW.md                            # end-to-end execution flow
│   ├── EVAL_METHODOLOGY.md                # scoring, metrics, statistical protocol
│   ├── TASK_DESIGN.md                     # how to author a task
│   ├── CONFIG_ABLATION.md                 # the 4 configs and what each isolates
│   ├── SAFETY.md                          # safety baseline + experimental isolation
│   ├── RESULTS.md                         # auto-generated, the headline table
│   ├── FAILURE_ANALYSIS.md                # categorized failure modes
│   └── TRACE_SAMPLES.md                   # representative full traces
├── harness/
│   ├── runner.py
│   ├── scorer.py
│   ├── failure_class.py
│   ├── ast_guard.py
│   ├── sandbox/
│   ├── rubric/
│   ├── tools/
│   ├── agents/
│   ├── llm/
│   │   ├── client.py
│   │   ├── prompts.py
│   │   └── prompts/
│   └── events/
│       └── trace.py
├── configs/
│   ├── baseline.yaml
│   ├── plus_debug.yaml
│   ├── plus_ast.yaml
│   └── full.yaml
├── evals/
│   ├── tasks/
│   │   └── <task_id>/
│   │       ├── task.json
│   │       ├── repo_before/
│   │       ├── repo_after/
│   │       ├── oracle.py
│   │       └── rubric.json
│   ├── loader.py
│   └── validate.py
├── scripts/
│   ├── run_eval.py                        # run one (task, config, model)
│   ├── run_matrix.py                      # run the full matrix
│   ├── compare_runs.py                    # comparison tables
│   ├── generate_report.py                 # produce RESULTS.md
│   └── check_docs.py                      # doc-validation loop
├── results/
│   ├── raw/                               # JSONL traces
│   └── reports/                           # generated markdown
└── tests/
    ├── test_failure_class.py
    ├── test_rubric.py
    ├── test_prompt_registry.py
    ├── test_sandbox_local_safe.py
    ├── test_sandbox_docker.py
    ├── test_scorer.py
    ├── test_ast_guard.py
    ├── test_loader.py
    └── test_runner.py
```

---

## Technology stack

**Design targets, not a verified installed or executable stack.** The current default branch primarily contains specifications, empty package directories, and a Python documentation checker.

| Layer | Planned technology | Reason |
|---|---|---|
| Language | Python 3.12 | LLM ecosystem is Python-native |
| Agent runtime | LangGraph | Stateful graphs, clean retry/branching |
| LLM access | LiteLLM | Provider-agnostic, swap Sonnet/GPT/Qwen with one flag |
| Sandbox | Docker SDK + local-safe preexec | Safety baseline + experimental isolation |
| AST analysis | tree-sitter-python | Multi-language capable, fast |
| Scorer | pytest + ruff + custom checks | Deterministic, no LLM in the loop |
| Output | JSONL traces + markdown reports | Diffable, replayable, version-controllable |
| Tests | pytest | Standard |
| CI | GitHub Actions | Standard |

---

## Documentation index

| Document | Purpose |
|---|---|
| [`README.md`](README.md) | This file — entry point, thesis, quick start |
| [`PROJECT_SPEC.md`](PROJECT_SPEC.md) | Problem statement, goals, requirements, constraints |
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | What's built, what's not, verified status |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Component diagram, data flow, module breakdown |
| [`docs/FLOW.md`](docs/FLOW.md) | End-to-end execution: from CLI invocation to scored result |
| [`docs/EVAL_METHODOLOGY.md`](docs/EVAL_METHODOLOGY.md) | The four metric families, failure class taxonomy, statistical protocol |
| [`docs/TASK_DESIGN.md`](docs/TASK_DESIGN.md) | Task schema, difficulty mix, authoring guide |
| [`docs/CONFIG_ABLATION.md`](docs/CONFIG_ABLATION.md) | The four configs and what each isolates |
| [`docs/SAFETY.md`](docs/SAFETY.md) | Safety baseline + experimental isolation levels |
| [`docs/RESULTS.md`](docs/RESULTS.md) | Auto-generated experimental results |
| [`docs/FAILURE_ANALYSIS.md`](docs/FAILURE_ANALYSIS.md) | Categorized failure modes |
| [`docs/TRACE_SAMPLES.md`](docs/TRACE_SAMPLES.md) | Representative full traces |

---

## Reproduction

There is **no completed benchmark to reproduce** in this branch. To inspect the current artifact:

1. Clone this repository.
2. Run `python scripts/check_docs.py` to check documentation structure.
3. Read [`docs/EVAL_METHODOLOGY.md`](docs/EVAL_METHODOLOGY.md) and [`docs/CONFIG_ABLATION.md`](docs/CONFIG_ABLATION.md) for the planned experimental design.
4. Read [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) to distinguish completed work from backlog items.

Once the harness and experimental matrix are implemented, this section should be replaced with tested installation instructions, exact model identifiers and versions, executable commands, and links to measured results.

---

## License

See [`LICENSE`](LICENSE).

---

## Status

**Documentation and design foundation only (default branch).** The published repository does not yet substantiate claims that a four-agent pipeline executes code, that Docker sandboxes run tests, or that an AST safeguard prevents edits. Those features are planned for future milestones in [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md).

For a recruiter or reviewer, the strongest evidence currently available here is the architecture/evaluation design and its documentation-validation script. Any additional working implementation should be committed with tests and reproducible examples before being represented as complete.
