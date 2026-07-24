# Trace Samples — OS Devin Evaluation Harness

> **Status:** placeholder. This document is populated by `scripts/generate_report.py` once the experimental matrix has been run.

This document will hold 3–5 representative full traces that illustrate how the agent pipeline works in practice. Each trace will include:

- The task description
- The agent's full event sequence (planner output, tool calls, test runs, debugger iterations)
- The scored result
- A short narrative explaining what the agent did well or poorly

---

## Planned sample traces

1. **Easy success** — `001_remove_dead_import` on `baseline` config. A clean single-shot pass.
2. **Hard recovery** — a `bug_fix` task on `+debug` config where the debugger loop is exercised.
3. **AST guard blocks** — a task where the agent tried to edit a forbidden file and the guard caught it.
4. **Cross-model contrast** — the same task on two models, one succeeds, one fails, with traces side-by-side.
5. **Unrecoverable failure** — a task where the debugger exhausts retries. What did it try?

---

## Why these traces

A reviewer who reads the headline table will want to verify the methodology. The traces are the proof. They show:

- The agent is doing real work (not just a stub)
- The scorer is reading real artifacts (not fudging)
- The metrics are computed from real events (not hand-edited)

The traces are picked to span the difficulty and outcome spectrum, not to cherry-pick successes.

---

## Reproduction

To regenerate this document:

```bash
python scripts/generate_report.py --results results/raw/ --output results/reports/
```

The trace samples are selected automatically from the highest-signal traces in `results/raw/`.

---

## Cross-references

- [`README.md`](../README.md) — entry point
- [`docs/EVAL_METHODOLOGY.md`](EVAL_METHODOLOGY.md) — what the events mean
- [`docs/FLOW.md`](FLOW.md) — the runtime flow that produces these traces
- [`docs/RESULTS.md`](RESULTS.md) — the headline table
- [`docs/FAILURE_ANALYSIS.md`](FAILURE_ANALYSIS.md) — categorized failure modes
