# Project Overview — OS Devin

## Project status

As of this implementation upgrade, the repository includes a tested six-role MVP. The underlying design documentation predates the working code and remains a roadmap unless independently verified. No large-scale benchmark results exist yet.

## Documentation completeness

The original specification, architecture, flow, evaluation design, and safety reference remain. `python scripts/check_docs.py` checks their links and headings; `python -m unittest discover -s tests -v` checks runtime behavior.

## What is implemented today

The native Python runner supports a Planner (structured file scope), Coder (full-file JSON edits), Reviewer (model approval), Security (AST/path/scope checks), Tester (Docker or explicit trusted local execution), and Debugger (test-feedback retry). It copies the repository to a disposable workspace, generates JSONL events, and exports a reviewable patch. It includes import/function-call AST indexing, an OpenAI-compatible API adapter, an intentionally scripted demo provider, and unit tests. A separate LangGraph adapter uses `StateGraph` when installed; both routes use the same agent methods. Unit tests and the scripted local demo have been executed. Docker and LangGraph integration have not been executed in the current environment.

## What is not implemented yet

A secure production-grade sandbox, robust multi-language build orchestration, comprehensive repository-wide AST dependency safety, separate LLM backends validated across models, GitHub PR automation, interactive Next.js dashboard, and statistically meaningful evaluation remain unimplemented. The existing 18-task / cross-model matrix in `docs/` is a plan, **not measured evidence**.

## Verification

```bash
python -m unittest discover -s tests -v
python -m harness.cli demo --sandbox local --allow-unsafe-local
python scripts/check_docs.py
```

The local demo provider is explicitly scripted to fail once and repair on retry; it is a wiring test and never a proxy for LLM task-solving success. CI runs the unit tests and this trusted demo.

## Roadmap

1. Exercise the Docker mode and optional LangGraph adapter on an appropriate host.
2. Add more independently authored benchmark tasks and test oracles.
3. Extend code intelligence and safe change policies for additional languages.
4. Build a real benchmark matrix with reproducible model settings and measured outcomes.
5. Add GitHub PR creation and a dashboard only after workflow reliability is demonstrated.

See [README](README.md), [architecture](docs/ARCHITECTURE.md), and [evaluation](docs/EVAL_METHODOLOGY.md).
