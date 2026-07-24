# Evaluation Methodology — OS Devin Evaluation Harness

This document is the source of truth for **how the harness scores runs**. It defines the four metric families, the failure-class taxonomy, the rubric scoring system, and the statistical protocol for cross-model comparison.

If a number appears in [`docs/RESULTS.md`](RESULTS.md), it was produced by the rules described here.

---

## Overview

The harness measures four things:

1. **Outcome** — did the agent solve the task?
2. **Tool trace** — how did the agent work?
3. **Retry behavior** — how did the debugger loop behave?
4. **Scope discipline** — did the agent stay in its lane?

The headline number is `success_rate` per `(config, model)`. The headline deltas are the marginal contributions of `+debug`, `+ast`, and `full` over `baseline`.

---

## The four metric families

### Family 1: Outcome

The most important family. Three metrics.

#### `success` (bool)

A run is `success = true` if and only if:
- The oracle test suite passes (all expected tests pass, no unexpected failures)
- Every deterministic rubric check passes

```python
def score(task, agent_outcome, repo_before, repo_after) -> bool:
    oracle_passed = run_oracle(task, repo_after).passed
    rubric_passed = all(
        run_check(spec, repo_before, repo_after)
        for spec in task.rubric
    )
    return oracle_passed and rubric_passed
```

#### `failure_class_agent` (string | null)

The agent's classification of why the test failed. Computed by the Tester (after the first failure) or by the Debugger (on each retry). One of the `FailureClass` enum values, or `null` if the run succeeded.

#### `failure_class_match` (enum: exact | family | wrong | n/a)

Comparison of the agent's classification vs the task's `ground_truth_failure_class`. See [Failure Class Taxonomy](#failure-class-taxonomy) below.

`n/a` if the run succeeded (no failure to classify).

### Family 2: Tool trace

Measures *how* the agent worked, not just whether it succeeded.

#### `tool_calls_total` (int)

Total number of tool calls made by the agent. Includes reads, writes, edits, searches, commands, test runs.

#### `tool_calls_redundant` (int)

A tool call is redundant if:
- `read_file(p)` and the same `p` was already read in the last 3 tool calls and the file hasn't changed
- `search_text(pattern, p)` and the same pattern was already searched in the same path
- `list_files(p)` and the same listing was already produced

Redundancy is a proxy for context management. A model that re-reads the same file 4 times is wasting budget.

#### `tool_call_sequence` (list[str], optional)

The sequence of tool calls. Useful for trace analysis, not for headline numbers. Stored in the JSONL trace, not in the scored result.

### Family 3: Retry behavior

Only relevant when `debugger.enabled = true`.

#### `retries` (int)

Number of debugger iterations. `0` if the Tester passed on the first run, or if the debugger is disabled.

#### `retries_to_success` (int)

Number of iterations until the first successful test run. `0` if the first run succeeded, or if the debugger never produced a success.

#### `failure_classification_sequence` (list[str])

The sequence of failure classes the debugger attributed to each failure. Useful for analyzing whether the debugger converged on the right diagnosis.

#### `failure_class_correct` (float)

Proportion of debugger classifications that match the ground truth (exact or family). Computed across all debugger iterations in a run.

```python
def classifier_correct(run):
    debugger_iters = run.debugger_classifications
    if not debugger_iters:
        return None
    matches = [
        classify_match(c, run.task.ground_truth_failure_class)
        for c in debugger_iters
    ]
    return sum(1 for m in matches if m in ("exact", "family")) / len(matches)
```

### Family 4: Scope discipline

Measures whether the agent edited only the files it was supposed to.

#### `in_scope_edits` (int)

Number of `write_file` / `edit_file` calls whose target path is in `task.expected_files`.

#### `out_of_scope_edits` (int)

Number of `write_file` / `edit_file` calls whose target path is in `task.forbidden_files`. The AST guard exists to drive this to 0.

#### `ast_blocks` (int)

Number of times the AST guard rejected an edit. A non-zero count means the agent tried to do something that would have broken downstream consumers.

#### `diff_size_lines` (int)

Total lines changed (additions + deletions) in the workspace vs. `repo_before`. Useful for the `minimal_diff` rubric check.

#### `diff_size_files` (int)

Number of files modified. Useful for the `minimal_diff` rubric check.

---

## Failure class taxonomy

A fixed enum. Author picks one at task creation time. Scorer compares agent-classified vs ground truth.

### The enum

```python
class FailureClass(str, Enum):
    SYNTAX_ERROR        = "syntax_error"
    IMPORT_ERROR        = "import_error"
    NAME_ERROR          = "name_error"
    TYPE_ERROR          = "type_error"
    ATTRIBUTE_ERROR     = "attribute_error"
    ASSERTION_MISMATCH  = "assertion_mismatch"
    OFF_BY_ONE          = "off_by_one"
    INDEX_ERROR         = "index_error"
    KEY_ERROR           = "key_error"
    VALUE_ERROR         = "value_error"
    INFINITE_LOOP       = "infinite_loop"
    TIMEOUT             = "timeout"
    RECURSION_ERROR     = "recursion_error"
    OUT_OF_SCOPE_EDIT   = "out_of_scope_edit"
    TEST_NOT_RUN        = "test_not_run"
    WRONG_API           = "wrong_api"
    INCOMPLETE_FIX      = "incomplete_fix"
    OTHER               = "other"
```

### The families

Related failure classes are grouped so an "off-by-one" classification on a task whose ground truth is "index_error" still counts as a near-match.

```python
FAILURE_FAMILIES = {
    "logic_error":    {OFF_BY_ONE, INDEX_ERROR, KEY_ERROR, VALUE_ERROR,
                        WRONG_API, INCOMPLETE_FIX},
    "type_error":     {TYPE_ERROR, ATTRIBUTE_ERROR, NAME_ERROR},
    "import_error":   {IMPORT_ERROR},
    "syntax_error":   {SYNTAX_ERROR},
    "runtime_kill":   {INFINITE_LOOP, TIMEOUT, RECURSION_ERROR},
    "scope_error":    {OUT_OF_SCOPE_EDIT},
    "infrastructure": {TEST_NOT_RUN, OTHER},
}
```

### The matcher

```python
def classify_match(agent_class: str, ground_truth: str) -> str:
    """Returns: 'exact', 'family', 'wrong', or 'n/a'."""
    if agent_class is None or ground_truth is None:
        return "n/a"
    if agent_class == ground_truth:
        return "exact"
    gt_family = family_of(ground_truth)
    agent_family = family_of(agent_class)
    if gt_family and gt_family == agent_family:
        return "family"
    return "wrong"
```

The normalized score:

```python
match_score = {
    "exact": 1.0,
    "family": 0.5,
    "wrong": 0.0,
    "n/a": None,  # not counted
}
```

### Why ground truth matters

Without `ground_truth_failure_class`, the metric `failure_class_correct` is meaningless — you can't know if the agent's classification was right. The author declares the truth at task creation time, by examining the bug and writing the simplest possible description of why the tests fail on `repo_before`.

For example, for `008_fix_off_by_one_pagination`:

```json
"ground_truth_failure_class": "off_by_one",
"failure_class_family": "logic_error",
"failure_class_notes": "Cursor math underflows when offset exceeds page count."
```

If the agent classifies this as `assertion_mismatch` (because the test that fails is an assertion), it's `exact` if it's `assertion_mismatch` (it's not), `family` if it's another `logic_error` (e.g., `index_error`), or `wrong` if it's `import_error`.

---

## Rubric scoring

The rubric is the set of *mechanical* checks beyond the oracle. It is computed by `harness/rubric/`. No LLM is involved.

### Why deterministic

LLM-judged rubric checks are not reproducible. Two runs of the same LLM can disagree on whether the diff is "minimal." A lint tool can.

### The check interface

```python
class RubricCheck(ABC):
    name: str
    description: str

    @abstractmethod
    def check(self, repo_before: Path, repo_after: Path,
              task: Task) -> RubricResult: ...
```

### Available checks

| Check name | Tool | Args |
|---|---|---|
| `no_unused_imports` | `ruff check --select F401` | `expected_files` |
| `no_new_lint_errors` | `ruff check` | `expected_files` |
| `no_new_dependencies` | manifest diff | `manifests: [requirements.txt, pyproject.toml]` |
| `minimal_diff` | `git diff --shortstat` | `max_lines_changed`, `max_files_changed` |
| `no_forbidden_file_edits` | `git diff --name-only` | `mode: forbidden` |
| `tests_still_pass` | `pytest` | `command` |
| `no_print_statements` | AST scan | `expected_files` |
| `stdlib_only` | AST import scan | `expected_files` |
| `type_annotations_complete` | `mypy` | `expected_files` |

### Adding a new check

1. Implement `RubricCheck` in `harness/rubric/<group>.py`
2. Register in `harness/rubric/registry.py`
3. Add it to the task's `rubric` list in `task.json`

### The result

```python
@dataclass
class RubricResult:
    name: str
    passed: bool
    detail: str
    evidence: dict
```

Each result is recorded in the scored result. The aggregate `success` is `True` only if **all** checks pass.

---

## Statistical protocol

### Replicates

Every `(task, config, model)` cell is run **3 times**. The replicate_id is logged in the trace. Variance is real — model APIs are non-deterministic even at `temperature = 0.0` (provider-side batching, integer quantization, etc.).

### Confidence intervals

For proportions (success rate), we use the **Wilson score interval** at 95% confidence. This is the standard for small samples and avoids the pathologies of the normal approximation.

```python
def wilson_interval(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for proportions."""
    if n == 0:
        return (0.0, 1.0)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))
```

### Per-cell summary

```python
@dataclass
class CellSummary:
    config_id: str
    model_id: str
    n_runs: int
    n_success: int
    success_rate: float
    success_ci: tuple[float, float]  # 95% Wilson
    mean_latency_s: float
    mean_tokens: float
    mean_cost_usd: float
    mean_tool_calls: float
    mean_retries: float
    mean_out_of_scope_edits: float
    mean_ast_blocks: float
    failure_classifier_accuracy: float | None  # across runs with at least one classification
```

### Per-task summary

```python
@dataclass
class TaskSummary:
    task_id: str
    per_config: dict[str, dict[str, CellSummary]]  # config_id -> model_id -> summary
```

### The headline table

The headline table is rendered from `CellSummary` per `(config, model)`, with CIs shown as ±pp.

```
| Config   | Sonnet 4.5      | GPT-5.x         | Qwen-3-Coder    |
|----------|-----------------|-----------------|-----------------|
| baseline | 45% ± 4pp       | 52% ± 4pp       | 31% ± 5pp       |
| +debug   | 68% ± 4pp       | 71% ± 3pp       | 48% ± 5pp       |
| +ast     | 51% ± 4pp       | 58% ± 4pp       | 35% ± 5pp       |
| full     | 74% ± 4pp       | 78% ± 3pp       | 61% ± 5pp       |
```

### Marginal contribution

For the incremental stack (`baseline → +debug → +ast → full`), the marginal contribution of each component is:

```python
def marginal_contribution(config_stack, model_id, task_summaries):
    contributions = []
    for prev, curr in zip(config_stack, config_stack[1:]):
        prev_rate = task_summaries[prev][model_id].success_rate
        curr_rate = task_summaries[curr][model_id].success_rate
        contributions.append((f"{prev} → {curr}", curr_rate - prev_rate))
    return contributions
```

The 95% CI on the marginal delta is computed via the variance of the difference of two proportions.

---

## Cross-model comparison

The same harness runs identically across model backends. The values that vary are:

- Model weights (the model's behavior)
- Model API surface (input/output format, token limits)

The values that are constant:

- Tasks
- Configs
- Isolation
- Prompt content (versions pinned per config)
- Scoring rules
- Resource limits

### Why this matters

A comparison table that holds the task set, the scoring rules, and the procedure constant is the only kind of comparison that says anything about model capability. A leaderboard that runs different tasks on different models with different scoring is noise.

### The protocol

For each model backend:

1. Run the full matrix (4 configs × 18 tasks × 3 replicates = 216 runs)
2. Aggregate per `(config, model)` cell
3. Compute the per-model summary
4. Render the comparison table

If a model backend is unavailable for a window, the run is paused and resumed; partial results are not used.

---

## What the harness does NOT measure

- **Agent capability** beyond the 18 tasks. The task set is not a representative sample of all coding work. Generalization is not assumed.
- **Cost-efficiency** in absolute terms. Cost is measured per-run, but the headline ranking is by success rate.
- **Speed** in absolute terms. Latency is recorded, but the headline is success rate.
- **Multi-language agent capability.** Python only in v1.
- **Robustness to adversarial inputs.** The task set is non-adversarial.
- **Multi-task composition.** Each task is run independently.

---

## Cross-references

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — where the metrics are computed in the pipeline
- [`FLOW.md`](FLOW.md) — the timing of metric computation
- [`TASK_DESIGN.md`](TASK_DESIGN.md) — how `ground_truth_failure_class` is set, how rubric is curated
- [`CONFIG_ABLATION.md`](CONFIG_ABLATION.md) — the 4 configs whose marginal contributions are the result
- [`docs/RESULTS.md`](RESULTS.md) — the auto-generated output of this methodology
- [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) — non-functional requirements (reproducibility, defensibility)
