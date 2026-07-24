# Architecture — OS Devin Evaluation Harness

This document is the canonical reference for the harness's component structure, data flow, and module responsibilities. It is the source of truth that other docs reference.

---

## Overview

The harness is a **measurement instrument** layered over an agent runtime. The agent runtime (Planner → Coder → Tester → Debugger → Reviewer) is the *subject* of the measurement; the harness is what measures it.

Three layers:

1. **Orchestration layer** — loads configs, runs cells of the matrix, captures traces, aggregates results
2. **Agent layer** — the agent pipeline + tools + LLM client + prompt registry
3. **Safety layer** — isolation, guardrails, and resource limits (always on)

The layers do not leak. The agent layer does not know it's being measured; the safety layer does not know which agents are enabled.

---

## Component diagram

```
                  ┌──────────────────────────────────────────────────────┐
                  │                  CLI / Scripts                        │
                  │  run_eval.py · run_matrix.py · generate_report.py    │
                  │  compare_runs.py · check_docs.py                     │
                  └──────────────────────┬───────────────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────────────┐
                  │                    Runner                            │
                  │  - Load (task, config, model, replicate)             │
                  │  - Spawn isolation                                   │
                  │  - Drive agent pipeline                              │
                  │  - Capture events → JSONL                            │
                  │  - Run scorer → scored result                        │
                  │  - Tear down isolation                               │
                  └────────┬───────────────────┬────────────────────────┘
                           │                   │
              ┌────────────▼──────┐    ┌────────▼────────────┐
              │  Agent pipeline   │    │  Isolation layer    │
              │  (per config)     │    │  (always on)        │
              │                   │    │                     │
              │  Planner          │    │  LocalSafeExecutor  │
              │  Coder ───────┐   │    │  DockerExecutor     │
              │  Tester      │   │    │  ResourceLimits     │
              │  Debugger ───┘   │    │  NetworkBlock       │
              │  Reviewer        │    │                     │
              │                  │    │  SafetyBaseline =   │
              │  (AST guard ──┐  │    │  always-on          │
              │   wraps Coder) │  │    └─────────┬───────────┘
              └────────┬───────┘  │              │
                       │          │              │
                       └──────────┴──────────────┘
                                  │
                                  ▼
                  ┌──────────────────────────────────────────────────────┐
                  │                    Tool layer                        │
                  │                                                      │
                  │   read_file · write_file · edit_file                 │
                  │   list_files · search_text · run_command             │
                  │   run_tests                                          │
                  │                                                      │
                  │   (wraps filesystem access through AST guard)        │
                  └──────────────────────┬───────────────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────────────┐
                  │                    LLM client                        │
                  │                                                      │
                  │   LiteLLM wrapper                                    │
                  │   Prompt registry + hashing                          │
                  │   Token counting · cost estimation                   │
                  │   Retry on transient errors                          │
                  └──────────────────────┬───────────────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────────────┐
                  │                Scorer + Result                       │
                  │                                                      │
                  │   Scorer: oracle + rubric + scoring rules            │
                  │   Result: per-run scored JSON + JSONL trace         │
                  └──────────────────────────────────────────────────────┘
```

---

## Data flow

A single run, end-to-end:

```
CLI args
  → config loader reads YAML → prompt registry resolves versions
  → task loader reads task.json → repo_before copied to workspace
  → isolation factory spawns executor (local_safe or docker)
  → agent pipeline runs:
      Planner(state) → events
      Coder(state) → events (AST guard intercepts writes)
      Tester(state) → events
      if debugger.enabled:
        loop until pass or max_attempts:
          Debugger(state) → classify failure → Coder → Tester
      Reviewer(state) → events
  → events stream to JSONL (atomic append)
  → on pipeline end:
      scorer runs oracle in workspace
      scorer runs each rubric check
      scorer computes failure_class_match vs ground truth
  → scored result written to results/raw/<run_id>.json
  → isolation executor tears down (always)
```

A full matrix:

```
matrix spec (configs × models × tasks × replicates)
  → for each cell, spawn a run
  → aggregate per-run JSON into scored results
  → group by (config, model) → summary statistics
  → write comparison.md to results/reports/
  → update docs/RESULTS.md
```

---

## Module breakdown

### `harness/runner.py`

The orchestrator. One entry point: `run(task, config, model, replicate) → RunResult`.

Responsibilities:
- Load and validate task, config, model
- Resolve prompt versions via the registry
- Spawn the isolation executor
- Drive the agent pipeline
- Capture events to JSONL
- Run the scorer
- Tear down isolation
- Return the scored result

### `harness/agents/`

One module per agent. Each agent is a function `state → events → state` with a system prompt and tool set.

| Module | Role | When disabled |
|---|---|---|
| `planner.py` | Decomposes task into DAG of subtasks | Always enabled |
| `coder.py` | Applies edits via tools (AST-gated when enabled) | Always enabled |
| `tester.py` | Runs oracle, parses results, returns structured pass/fail | Always enabled |
| `debugger.py` | Loops on Tester failures, classifies, re-patches | `config.agents.debugger.enabled = false` |
| `reviewer.py` | Writes PR-style summary | Always enabled |

`base.py` defines the agent protocol and shared utilities (message construction, scratchpad, etc.).

### `harness/failure_class.py`

The failure-classification enum, family groupings, and the matcher that compares agent-classified vs ground-truth.

```python
class FailureClass(str, Enum): ...
FAILURE_FAMILIES: dict[str, set[FailureClass]] = ...
def classify_match(agent: str, ground_truth: str) -> Literal["exact", "family", "wrong", "n/a"]
```

### `harness/scorer.py`

Runs the oracle and rubric, computes the metric families, returns the scored result.

```python
@dataclass
class ScoredResult:
    success: bool
    metrics: dict[str, Any]

def score(task: Task, agent_outcome: AgentOutcome,
          repo_before: Path, repo_after: Path) -> ScoredResult: ...
```

### `harness/rubric/`

Pluggable deterministic checks. Each check is a class implementing `RubricCheck.check(repo_before, repo_after, task) → RubricResult`.

Modules:
- `lint_checks.py` — `NoUnusedImportsCheck`, `NoNewLintErrorsCheck`, `NoPrintStatementsCheck`
- `diff_checks.py` — `MinimalDiffCheck`, `NoForbiddenFileEditsCheck`
- `test_checks.py` — `TestsStillPassCheck`, `OraclePassCheck`
- `dep_checks.py` — `NoNewDependenciesCheck`, `StdlibOnlyCheck`
- `registry.py` — `RUBRIC_REGISTRY: dict[str, type[RubricCheck]]`

### `harness/ast_guard.py`

Wraps the `write_file` and `edit_file` tools. Parses the proposed file with `tree-sitter-python`, computes the import graph, and verifies that no consumers of removed/renamed symbols will break.

```python
@dataclass
class AstCheckResult:
    allow: bool
    reason: str
    affected_files: list[str]

class AstGuard:
    def check(self, path: str, content: str, repo: Path) -> AstCheckResult: ...
```

### `harness/sandbox/`

Executor abstraction. Two implementations.

- `base.py` — `Executor` protocol with `run()` and `__enter__`/`__exit__`
- `local_safe.py` — `LocalSafeExecutor` (temp dir, no network, `preexec_fn` resource limits)
- `docker.py` — `DockerExecutor` (ephemeral container, no host mounts, network blocked, auto-removed)
- `factory.py` — `make_executor(isolation_level) → Executor`

### `harness/tools/`

The tool interface available to agents.

- `file_tools.py` — `read_file`, `write_file`, `edit_file`, `list_files`
- `shell_tools.py` — `run_command` (wraps the executor's `run`)
- `search_tools.py` — `search_text`
- `test_runner.py` — `run_tests` (runs pytest in the workspace)

### `harness/llm/`

- `client.py` — LiteLLM wrapper. Per-call: model_id, temperature, max_tokens, prompt, messages. Returns response, token counts, cost.
- `prompts.py` — versioned prompt loader. `load_prompt(agent, version)`, `hash_prompt(agent, version)`, `resolve_version(agent, override)`.
- `prompts/` — Markdown files: `planner_v1.md`, `coder_v1.md`, `coder_v2.md`, etc. `registry.yaml` lists the default version per agent.

### `harness/events/trace.py`

Structured event emitter. Every agent emits events; the runner appends them to JSONL.

```python
class EventEmitter:
    def emit(self, event: dict) -> None: ...
    def close(self) -> None: ...

def make_run_header(task, config, model, replicate, prompt_versions, prompt_hashes) -> dict: ...
```

### `harness/scorer.py`

See above. The scorer reads the worker's outcome and the workspace state, runs the oracle and rubric, and produces the scored result.

---

## Data model

### Task

```python
@dataclass
class Task:
    id: str
    title: str
    description: str
    category: Literal["bug_fix", "feature_add", "refactor", "dep_upgrade"]
    difficulty: Literal["easy", "medium", "hard"]
    language: str
    repo_root: str
    expected_files: list[str]
    forbidden_files: list[str]
    ground_truth_failure_class: str
    oracle: OracleSpec
    rubric: list[RubricSpec]
    time_limit_seconds: int
    token_budget: int
```

### Config

```python
@dataclass
class Config:
    name: str
    isolation: IsolationSpec
    agents: dict[str, AgentSpec]
    guards: GuardSpec
    tools: ToolSpec
    trace: TraceSpec
```

### Run

```python
@dataclass
class Run:
    task_id: str
    config_id: str
    model_id: str
    replicate: int
    model_params: dict
    prompt_versions: dict[str, str]
    prompt_hashes: dict[str, str]
    config_hash: str
    task_hash: str
    started_at: datetime
    ended_at: datetime
    trace_path: Path
    scored_result: ScoredResult
```

### Scored Result

```python
@dataclass
class ScoredResult:
    success: bool
    metrics: Metrics
    failure_class_agent: str | None
    failure_class_ground_truth: str
    failure_class_match: Literal["exact", "family", "wrong", "n/a"]
    rubric_results: list[RubricResult]
    oracle_output: str
```

### Metrics

```python
@dataclass
class Metrics:
    tool_calls_total: int
    tool_calls_redundant: int
    retries: int
    in_scope_edits: int
    out_of_scope_edits: int
    ast_blocks: int
    latency_s: float
    tokens_input: int
    tokens_output: int
    cost_usd: float
```

---

## External dependencies

| Dependency | Purpose | Version |
|---|---|---|
| Python | Runtime | 3.12+ |
| LiteLLM | LLM provider access | latest |
| tree-sitter | AST parsing | latest |
| tree-sitter-python | Python grammar | latest |
| Docker SDK | Container management | latest |
| pytest | Test runner | latest |
| ruff | Lint check | latest |
| pyyaml | Config parsing | latest |
| pydantic | Schema validation | v2 |
| GitPython | Repo diff | latest |
| click | CLI | latest |

Models:

| Provider | Model | Purpose |
|---|---|---|
| Anthropic | `claude-sonnet-4-5` | Primary model |
| OpenAI | `gpt-5` (or current) | Cross-model comparison |
| OpenRouter / vLLM | `qwen-3-coder-30b` | Open-weight comparison |

Specific model versions are pinned at run time and logged in the run header.

---

## Design invariants

1. **The harness is the constant; the agent is the variable.** Every config change is a single-component delta. The model is pluggable. The tasks are stable.

2. **Safety is a baseline, not an experimental variable.** Even `baseline` runs in disposable checkout with no network.

3. **Scoring is deterministic, not LLM-judged.** Success is mechanical: oracle passes + all rubric checks pass. No LLM in the scoring loop.

4. **Reproducibility is enforced in the trace.** Every run logs prompt hashes, model params, config hash, task hash. A run from week 1 is comparable to a run from week 5 only if the hashes match.

5. **The scorer is replayable.** Re-running the scorer on a saved JSONL trace produces the same scored result. The trace is the source of truth.

---

## Cross-references

- [`docs/FLOW.md`](FLOW.md) — end-to-end execution flow (the "how" of this architecture)
- [`docs/EVAL_METHODOLOGY.md`](EVAL_METHODOLOGY.md) — the four metric families (the data model in detail)
- [`docs/TASK_DESIGN.md`](TASK_DESIGN.md) — the `Task` schema
- [`docs/CONFIG_ABLATION.md`](CONFIG_ABLATION.md) — the `Config` schema and the 4 configs
- [`docs/SAFETY.md`](SAFETY.md) — the isolation layer in detail
- [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) — non-functional requirements this architecture satisfies
