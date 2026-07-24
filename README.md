# OS Devin — Evaluation Harness for Autonomous Coding Agents

> Most agentic coding demos report a demo, not a benchmark. This project is a **measurement instrument**: a harness that runs autonomously-coded solutions against 18 hand-curated tasks with oracle-based scoring, across 4 agent configurations and 3 LLM backends, and isolates the marginal contribution of each architectural component on task success rate.
>
> The product is the table, not the agent.

---

## Headline result (placeholder)

The final evaluation matrix will be reproduced here once the harness is run end-to-end. See [`docs/RESULTS.md`](docs/RESULTS.md) for the auto-generated full report.

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

This is the **foundation slice**. The eval framework, task schema, scorer, and configuration scaffolding are in place. The agents, sandbox, AST guard, and full experimental matrix are planned. See [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) for the verified build status and [`docs/`](docs/) for design references.

---

## What this is, and what it isn't

**This is** a research artifact that produces a defensible measurement of agentic-coding components. The headline deliverable is a comparison table with confidence intervals, reproducible from this repo.

**This is not** a coding agent. We are not building the next Devin clone. The agent code in this repo exists to be *measured*, not used as a product. Anyone who runs this harness and disagrees with the methodology is welcome to fork it, modify the configs, and rerun.

---

## Quick start

### Prerequisites

- Python 3.12+
- Docker (optional, only for `full` config)
- API keys for the LLM backends you want to evaluate (set in `.env`)

### Install

```bash
git clone <repo-url>
cd os-devin-multi-agent-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in your keys
```

### Run a single task

```bash
python scripts/run_eval.py \
  --task evals/tasks/001_remove_dead_import \
  --config configs/baseline.yaml \
  --model sonnet-4.5
```

This writes a JSONL trace to `results/raw/` and a scored result to `results/`.

### Run the full matrix

```bash
python scripts/run_matrix.py --config-matrix all --models sonnet-4.5,gpt-5,qwen-3-coder-30b --replicates 3
```

See [`docs/FLOW.md`](docs/FLOW.md) for the end-to-end execution flow.

### Generate the report

```bash
python scripts/generate_report.py --results results/raw/ --output results/reports/
```

This produces [`docs/RESULTS.md`](docs/RESULTS.md) with the comparison table.

### Validate this repository

```bash
python scripts/check_docs.py
```

This is the doc-validation loop. It checks that every required document exists, has the required sections, and that cross-references resolve. See [`scripts/check_docs.py`](scripts/check_docs.py) for the contract.

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

| Layer | Choice | Reason |
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

A reviewer who wants to reproduce the headline numbers should:

1. Clone the repo
2. `pip install -r requirements.txt`
3. Set API keys in `.env`
4. `python scripts/run_matrix.py --config-matrix all --models sonnet-4.5,gpt-5,qwen-3-coder-30b --replicates 3`
5. `python scripts/generate_report.py`
6. Compare your `results/reports/comparison.md` to the headline table in [`README.md`](README.md)

The runs are reproducible modulo model updates. If OpenAI/Anthropic/Alibaba update their model weights, expect drift. Document the model version in your run header — the harness does this automatically.

---

## License

See [`LICENSE`](LICENSE).

---

## Status

This project is in the **foundation slice**. The doc set is complete. The eval framework, task schema, agent scaffolding, scorer, and configuration layer are next. See [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) for the granular task list.
