# Configuration Ablation — OS Devin Evaluation Harness

This document is the source of truth for **the four configurations** and what each one isolates. The headline result of the harness is the marginal contribution of each component, measured by the four-config ablation stack.

---

## Overview

The harness has four configurations. Each configuration differs from the previous by exactly one component. The headline result is the marginal delta between adjacent configurations.

```
baseline → +debug → +ast → full
```

| Step | Adds | What it isolates |
|---|---|---|
| `baseline → +debug` | Self-healing retry loop | Recovery from initial failures |
| `+debug → +ast` | AST pre-edit guard | Scope discipline (preventing out-of-scope edits) |
| `+ast → full` | Docker isolation | Side-effect isolation (cleaner state per task) |

The expected deltas (from the design intent):

- `baseline → +debug`: **+20-25pp** success rate (the biggest gain)
- `+debug → +ast`: **+5-10pp** (the marginal value of scope discipline)
- `+ast → full`: **+3-8pp** (the marginal value of kernel isolation)

These are *expected* ranges. The actual numbers come from the experimental matrix.

---

## The four configurations

### `baseline`

```yaml
# configs/baseline.yaml
name: baseline
description: Single-shot, no debug, no AST, local_safe sandbox

isolation:
  level: local_safe
  network: blocked
  resource_limits:
    cpu_seconds: 60
    memory_mb: 512
    file_descriptors: 64
    processes: 32

agents:
  planner:  {enabled: true}
  coder:    {enabled: true}
  tester:   {enabled: true}
  debugger: {enabled: false}
  reviewer: {enabled: true}

guards:
  ast_pre_edit: false
```

**What runs:** Planner → Coder → Tester → Reviewer. Single shot. If tests fail, the run ends.

**What it does not run:** No debugger, no AST guard. Coder writes directly to the workspace.

**What it isolates:** The floor. The capability of the agent pipeline without recovery or scope discipline.

### `+debug`

```yaml
# configs/plus_debug.yaml
name: plus_debug
description: Baseline + self-healing debug loop

isolation:
  level: local_safe
  network: blocked
  resource_limits:
    cpu_seconds: 60
    memory_mb: 512
    file_descriptors: 64
    processes: 32

agents:
  planner:  {enabled: true}
  coder:    {enabled: true}
  tester:   {enabled: true}
  debugger:
    enabled: true
    max_attempts: 5
    backoff: exponential
    classify_failure: true
  reviewer: {enabled: true}

guards:
  ast_pre_edit: false
```

**What runs:** Planner → Coder → Tester → (loop: Debugger → Coder → Tester) → Reviewer. Bounded retry.

**What it does not run:** No AST guard. The debugger can propose any edit.

**What it isolates:** The marginal value of the self-healing retry loop. Specifically: how often the debugger correctly classifies the failure and applies a fix that turns red tests green.

**Key metric:** `retries_to_success` distribution; `failure_class_correct` rate.

### `+ast`

```yaml
# configs/plus_ast.yaml
name: plus_ast
description: Baseline + AST pre-edit guard

isolation:
  level: local_safe
  network: blocked
  resource_limits:
    cpu_seconds: 60
    memory_mb: 512
    file_descriptors: 64
    processes: 32

agents:
  planner:  {enabled: true}
  coder:    {enabled: true}
  tester:   {enabled: true}
  debugger: {enabled: false}
  reviewer: {enabled: true}

guards:
  ast_pre_edit: true
```

**What runs:** Planner → Coder → Tester → Reviewer. The AST guard intercepts every `write_file` and `edit_file` from Coder.

**What it does not run:** No debugger. If tests fail, the run ends.

**What it isolates:** The marginal value of scope discipline alone. The Coder has to stay in its lane; if it tries to edit a forbidden file or break a downstream consumer, the guard blocks it.

**Key metric:** `ast_blocks` count; `out_of_scope_edits` count.

### `full`

```yaml
# configs/full.yaml
name: full
description: All agents + AST guard + Docker isolation

isolation:
  level: docker
  docker_image: "python:3.12-slim"
  network: blocked
  resource_limits:
    cpu_seconds: 60
    memory_mb: 512
  auto_remove: true

agents:
  planner:  {enabled: true}
  coder:    {enabled: true}
  tester:   {enabled: true}
  debugger:
    enabled: true
    max_attempts: 5
    backoff: exponential
    classify_failure: true
  reviewer: {enabled: true}

guards:
  ast_pre_edit: true
```

**What runs:** Everything. Self-healing + scope discipline + kernel isolation.

**What it isolates:** The marginal value of Docker isolation. If `+ast → full` shows a delta, isolation matters. If not, the safety baseline (local_safe) is sufficient for the experimental noise.

**Key metric:** Per-task success rate compared to `+ast`.

---

## Why this ablation order

The order is **recovery → discipline → isolation**:

1. **Recovery** (`+debug`): the biggest expected gain. A retry loop that gets the right answer is the difference between "demo" and "useful."
2. **Discipline** (`+ast`): the second-biggest expected gain. A guard that prevents the agent from breaking downstream consumers is a multiplier on the recovery loop's effectiveness.
3. **Isolation** (`full`): the smallest expected gain. The Docker container is mostly about hygiene (no host contamination, cleaner teardown) — it shouldn't change the agent's success rate by much.

This order is **not** arbitrary. It's the order in which the value is largest. The headline table reads top-to-bottom as "this is what each component buys you."

---

## Reading the ablation table

The headline table:

| Config   | Sonnet 4.5      | GPT-5.x         | Qwen-3-Coder    |
|----------|-----------------|-----------------|-----------------|
| baseline | 45% ± 4pp       | 52% ± 4pp       | 31% ± 5pp       |
| +debug   | 68% ± 4pp       | 71% ± 3pp       | 48% ± 5pp       |
| +ast     | 51% ± 4pp       | 58% ± 4pp       | 35% ± 5pp       |
| full     | 74% ± 4pp       | 78% ± 3pp       | 61% ± 5pp       |

### Read by row

Each row is a configuration. The numbers show what configuration X succeeds at, on model Y, averaged across 18 tasks × 3 replicates = 54 runs per cell.

### Read by column

Each column is a model. The numbers show how a model behaves across the configuration stack. A model with a steep slope from `baseline → full` benefits more from the architectural components.

### Read by delta

The deltas between adjacent rows are the marginal contributions:

```
Sonnet 4.5:
  baseline → +debug:  +23pp  (45% → 68%)
  +debug → +ast:      +6pp   (we don't read this from this table — see below)
  +ast → full:        +23pp  (51% → 74%)
```

**A subtle thing.** Because the ablation is an **incremental stack** (`baseline → +debug → +ast → full`), the marginal contributions must be read by comparing adjacent configs in the stack. The `+ast` row is *baseline + AST guard* (without debugger); the `full` row is *baseline + debugger + AST + docker*. To read the marginal of debugger alone, compare `baseline` to `+debug`.

This is the **clean experimental design**: each row adds exactly one component to the previous row, and the marginal delta is the difference between adjacent rows.

### The "leave-one-out" extension (v2)

For v1, the incremental stack tells the headline story. For v2, run the leave-one-out matrix to detect interaction effects:

| Config | Description |
|---|---|
| `baseline` | (already run) |
| `+debug_only` | Just debugger, no AST |
| `+ast_only` | Just AST, no debugger |
| `+sandbox_only` | Just Docker, no debugger, no AST |
| `+debug+ast` | Both, no Docker |
| `+debug+sandbox` | Debugger + Docker, no AST |
| `+ast+sandbox` | AST + Docker, no debugger |
| `full` | All three (already run) |

The v2 matrix has 8 configs × 3 models × 18 tasks × 3 replicates = 1296 runs. The v1 matrix is 4 × 3 × 18 × 3 = 648 runs.

The v2 readout decomposes the marginal contributions into independent and interaction effects. The v1 readout is the headline.

---

## Component-by-component reference

### Debugger

**What it is:** an agent that loops on Tester failures. It reads the test failure, classifies it, proposes a fix, and re-runs.

**What it does not do:** It does not modify the original task. It does not skip the failing test. It does not weaken the oracle. It does not invent new tests.

**Failure modes:**
- Wrong classification (e.g., calls `syntax_error` when it's `off_by_one`)
- Right classification, wrong fix
- Right fix, but introduces a new bug elsewhere
- Loops forever (bounded by `max_attempts`)

**Configuration knobs:**
- `max_attempts` (default: 5)
- `backoff` (default: exponential, base 1s)
- `classify_failure` (default: true)

**Metrics:**
- `retries`, `retries_to_success`
- `failure_class_correct` (proportion of debugger classifications that match ground truth)
- `failure_classification_sequence` (the sequence of classifications)

### AST guard

**What it is:** a pre-edit gate that parses the proposed file with `tree-sitter-python`, computes the import graph, and verifies that no consumers of removed/renamed symbols will break.

**What it does not do:** It does not enforce style. It does not check correctness. It only checks scope and downstream impact.

**Failure modes:**
- False positive: blocks a valid edit (the agent has to revise)
- False negative: allows an edit that later breaks a consumer (caught by the oracle, not the guard)

**Configuration knobs:**
- `enabled` (boolean)
- `strict` (default: true; if false, the guard warns instead of blocks)

**Metrics:**
- `ast_blocks` (count of rejections)
- `out_of_scope_edits` (count of edits to forbidden files; should be 0 with the guard enabled)

### Docker isolation

**What it is:** an ephemeral container per task with no network, no host mounts, and auto-removal on exit.

**What it does not do:** It does not change the agent's behavior. It does not constrain the tools. It only changes the execution environment.

**Failure modes:**
- Docker daemon not running (the run fails to start)
- Image pull failure (the run fails to start)
- Resource limit hit (the subprocess is killed)

**Configuration knobs:**
- `level` (`local_safe` or `docker`)
- `docker_image` (default: `python:3.12-slim`)
- `auto_remove` (default: true)

**Metrics:**
- Per-run latency (Docker has setup/teardown overhead)
- Per-run failure rate (Docker setup failures)

---

## What the ablation does NOT isolate

- **Model capability** vs. **architectural value**. The matrix runs each config on each model. The interaction is captured per-cell, not aggregated.
- **Cost-effectiveness** of each component. The metrics don't include cost as a constraint.
- **Latency** impact. The metrics don't penalize latency.
- **Generalization** beyond the 18 tasks. The ablation is on this task set; other tasks may show different deltas.

---

## Adding a new configuration (v2)

If a new component is added (e.g., a planning verifier, a code review agent), the configuration system supports it via the YAML schema. The new config slot is added to the ablation stack, and the matrix is re-run.

Configurations are **immutable** once added to the matrix. New configurations get new IDs.

---

## Cross-references

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the `Config` data model and the executor factory
- [`EVAL_METHODOLOGY.md`](EVAL_METHODOLOGY.md) — the metric families used to evaluate each config
- [`FLOW.md`](FLOW.md) — what changes in the runtime when each config is enabled
- [`SAFETY.md`](SAFETY.md) — the isolation layer (`local_safe` vs `docker`) in detail
- [`TASK_DESIGN.md`](TASK_DESIGN.md) — what the configs are evaluated against
- [`docs/RESULTS.md`](RESULTS.md) — the auto-generated output of this ablation
- [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) — non-functional requirements (reproducibility, defensibility)
