# Task Design — OS Devin Evaluation Harness

This document is the source of truth for **what makes a valid task**. Tasks are the unit of comparison; their quality determines the value of the headline table.

---

## Overview

A task is a small, self-contained Python coding problem with:
- A real bug (or feature to add, or refactor to perform)
- A pre-baked broken state (`repo_before/`)
- A canonical fix (the author writes this; it's `repo_after/`)
- An oracle that passes on the fix and fails on the broken state
- A rubric of deterministic checks
- A ground-truth failure class

18 tasks are curated by hand. They are not scraped from GitHub. Each task is auditable in 5–10 minutes by a reviewer.

---

## Task schema

```json
{
  "id": "008_fix_off_by_one_pagination",
  "title": "Fix off-by-one in pagination cursor",
  "description": "In src/pagination.py, get_next_page() returns page 0 even when the cursor is past the end. The cursor math underflows when offset > total_count.",
  "category": "bug_fix",
  "difficulty": "medium",
  "language": "python",

  "repo_root": "repo_before",
  "expected_files": ["src/pagination.py"],
  "forbidden_files": ["tests/test_pagination.py"],

  "ground_truth_failure_class": "off_by_one",
  "failure_class_family": "logic_error",
  "failure_class_notes": "Cursor math underflows when offset exceeds page count. Test test_page_overflow_returns_empty sees an empty list instead of the expected out-of-range sentinel.",

  "oracle": {
    "type": "pytest",
    "command": "pytest tests/test_pagination.py -v --tb=short",
    "expected_pass": 7,
    "expected_fail": 0,
    "expected_test_count": 7
  },

  "rubric": [
    {
      "name": "no_unused_imports",
      "kind": "deterministic",
      "tool": "ruff",
      "args": {"select": ["F401"]},
      "description": "No unused imports introduced"
    },
    {
      "name": "no_new_dependencies",
      "kind": "deterministic",
      "tool": "dep_diff",
      "args": {"manifests": ["requirements.txt", "pyproject.toml"]},
      "description": "No new external dependencies"
    },
    {
      "name": "minimal_diff",
      "kind": "deterministic",
      "tool": "diff_stat",
      "args": {"max_lines_changed": 10, "max_files_changed": 1},
      "description": "Diff under 10 lines, 1 file"
    },
    {
      "name": "no_forbidden_file_edits",
      "kind": "deterministic",
      "tool": "file_set_check",
      "args": {"mode": "forbidden"},
      "description": "Tests file untouched"
    },
    {
      "name": "tests_still_pass",
      "kind": "deterministic",
      "tool": "pytest",
      "args": {"command": "pytest tests/ -v"},
      "description": "Full test suite passes"
    }
  ],

  "tags": ["bug_fix", "logic", "single_file"],
  "time_limit_seconds": 300,
  "token_budget": 50000
}
```

### Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier. Format: `<NNN>_<short_slug>`. |
| `title` | string | yes | Human-readable title. |
| `description` | string | yes | Natural-language description of the bug/task. |
| `category` | enum | yes | `bug_fix`, `feature_add`, `refactor`, `dep_upgrade`. |
| `difficulty` | enum | yes | `easy`, `medium`, `hard`. |
| `language` | string | yes | `python` (v1 only). |
| `repo_root` | string | yes | Subdirectory inside the task directory; typically `repo_before`. |
| `expected_files` | list[str] | yes | Files the agent should modify. |
| `forbidden_files` | list[str] | yes | Files the agent must NOT modify. |
| `ground_truth_failure_class` | string | yes | The `FailureClass` value that correctly describes the bug. |
| `failure_class_family` | string | no | The `FAILURE_FAMILIES` key. |
| `failure_class_notes` | string | no | Human-readable explanation of the failure. |
| `oracle` | object | yes | See [Oracle](#oracle). |
| `rubric` | list[object] | yes | See [Rubric](#rubric). |
| `tags` | list[string] | no | Free-form tags for filtering. |
| `time_limit_seconds` | int | yes | Wall-clock limit per run. Default 300. |
| `token_budget` | int | yes | Token limit per run. Default 50000. |

---

## Oracle

The oracle is the ground-truth test suite. It must:
- Pass on the canonical fix (`repo_after/`)
- Fail on the broken state (`repo_before/`)
- Run in ≤ 30 seconds
- Use no external services (no Docker, no network)

```json
"oracle": {
  "type": "pytest",
  "command": "pytest tests/test_pagination.py -v --tb=short",
  "expected_pass": 7,
  "expected_fail": 0,
  "expected_test_count": 7
}
```

Fields:
- `type`: `pytest` (v1 only)
- `command`: the command to run
- `expected_pass`: number of tests that should pass on the canonical fix
- `expected_fail`: number of tests that should fail on the canonical fix (typically 0)
- `expected_test_count`: total test count (pass + fail + skip)

The validation step (`evals/validate.py`) runs the oracle on both `repo_before` and `repo_after` and asserts:
- `repo_before`: at least one test fails
- `repo_after`: all expected tests pass

If validation fails, the task is rejected.

---

## Rubric

The rubric is a list of deterministic checks. Each check must be:
- Mechanical (no LLM in the scoring loop)
- Reproducible (same input → same output)
- Fast (≤ 5 seconds per check)

Available checks are registered in `harness/rubric/registry.py`. See [`EVAL_METHODOLOGY.md`](EVAL_METHODOLOGY.md) for the full list.

### Per-task rubric selection

Not every task needs every check. Authoring guide:

- **Easy bug_fix tasks**: `no_unused_imports`, `minimal_diff`, `no_forbidden_file_edits`, `tests_still_pass`
- **Medium tasks**: above + `no_new_lint_errors`
- **Hard tasks**: above + `no_new_dependencies`, `type_annotations_complete` (if applicable)
- **Refactor tasks**: `minimal_diff`, `no_new_dependencies`, `no_forbidden_file_edits`, `tests_still_pass`
- **Feature add tasks**: `no_new_lint_errors`, `no_new_dependencies`, `type_annotations_complete`

---

## Difficulty mix

18 tasks distributed across difficulty levels:

| Difficulty | Count | Description |
|---|---|---|
| easy | 6 | Single-line bug, well-described, target file obvious |
| medium | 7 | Requires investigation, may span 2-3 files |
| hard | 5 | Cross-file refactor, ambiguous description, edge cases |

### Easy (~6 tasks)

- `001_remove_dead_import` — strip an unused import
- `006_modernize_string_formatting` — `%` to f-string
- `013_remove_debug_print_statements` — strip stray `print()` calls
- More TBD via curation

### Medium (~7 tasks)

- `002_fix_off_by_one_in_pagination` — cursor math
- `004_add_type_hints_to_public_api` — type annotation pass
- `007_add_input_validation_to_parser` — defensive parsing
- More TBD via curation

### Hard (~5 tasks)

- `005_fix_recursive_callsite_off_by_one` — recursive function with subtle bug
- `011_fix_async_await_misuse` — async/await misordering
- `015_extract_repeated_logic_to_helper` — refactor across modules
- More TBD via curation

---

## Category mix

| Category | Count | Description |
|---|---|---|
| bug_fix | 8 | Broken behavior, tests fail until fixed |
| feature_add | 4 | New function + new tests |
| refactor | 4 | Restructure without changing behavior |
| dep_upgrade | 2 | Modernize without breaking callers |

---

## Ground truth failure class

The author declares the correct classification of the failure. This is the source of truth for `failure_class_correct` and `failure_class_match`.

### Selection rule

1. Run the oracle on `repo_before`. Identify the first failing test.
2. Read the failure trace. Identify the root cause.
3. Pick the `FailureClass` value that best describes the root cause, not the symptom.

For example, if the test fails with `AssertionError` because the function returns an empty list when it should return an out-of-range sentinel, the root cause is `off_by_one` (cursor math), not `assertion_mismatch` (the test assertion).

### When to use `other`

Use `other` only when no enum value fits. Add a `failure_class_notes` string explaining why.

### Author sanity check

After choosing, run the agent's Tester prompt manually on the broken state and verify that:
- A reasonable LLM would classify the failure similarly
- The classification is distinguishable from a near-neighbor (e.g., `off_by_one` vs `index_error`)

If the classification is ambiguous, the task author should pick the more specific one and explain in `failure_class_notes`.

---

## Task authoring workflow

### Step 1: Pick a candidate bug

Source options:
- A bug you found in your own code
- A bug from a popular open-source project (small, isolated)
- A synthetic bug you construct deliberately

Avoid:
- Bugs that require external services
- Bugs that require multi-language context
- Bugs with no clear ground truth (race conditions, performance)

### Step 2: Build the repo

A typical task repo:
- 200–500 lines of Python
- 1–3 source files
- 1 test file
- 1 `requirements.txt` or `pyproject.toml`
- Maybe a `README.md`

Example structure:
```
evals/tasks/008_fix_off_by_one_pagination/
├── task.json
├── repo_before/
│   ├── src/
│   │   ├── __init__.py
│   │   └── pagination.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_pagination.py
│   ├── requirements.txt
│   └── README.md
├── repo_after/
│   └── ... (same structure, with the bug fixed)
├── oracle.py
└── rubric.json
```

### Step 3: Write the bug

Edit `repo_before/` to introduce the bug. Then write the canonical fix in `repo_after/`.

### Step 4: Write the tests

Write tests that:
- Pass on `repo_after`
- Fail on `repo_before`
- Are not over-specified (don't test implementation details)

### Step 5: Define the oracle

The oracle is the test command. Make sure it runs in isolation:

```bash
cd repo_after && pip install -r requirements.txt && pytest tests/ -v
```

### Step 6: Define the rubric

Pick the deterministic checks relevant to this task. See [Per-task rubric selection](#per-task-rubric-selection).

### Step 7: Set the ground truth failure class

See [Ground truth failure class](#ground-truth-failure-class).

### Step 8: Validate

```bash
python evals/validate.py --task evals/tasks/008_fix_off_by_one_pagination
```

Validation runs:
- Schema check on `task.json`
- Oracle on `repo_before` (must fail)
- Oracle on `repo_after` (must pass)
- All rubric checks on `repo_after` (must pass)
- Manifest presence (`requirements.txt`, `pyproject.toml`, etc.)

### Step 9: Smoke test

Run the agent on the task with `baseline` config to verify the harness works end-to-end:

```bash
python scripts/run_eval.py \
  --task evals/tasks/008_fix_off_by_one_pagination \
  --config configs/baseline.yaml \
  --model sonnet-4.5
```

Inspect the trace. Confirm:
- The agent saw the task description
- The agent made reasonable tool calls
- The scorer ran correctly
- The output JSONL is well-formed

### Step 10: Commit

Commit the task directory as a single atomic unit. Tasks are immutable once added to the matrix.

---

## Immutability

Tasks are **immutable** once they enter the experimental matrix. If you need to update a task:

1. Create a new task with a new ID (e.g., `008_fix_off_by_one_pagination_v2`)
2. Re-run the matrix on the new task set
3. Document the change in `docs/RESULTS.md`

This is the same rule as SWE-bench: scores are pinned to the task set version.

---

## Example tasks (sample)

These are the planned tasks. The actual IDs are placeholders; IDs are assigned at curation time.

### Easy

- `001_remove_dead_import` — strip an unused import (bug_fix)
- `006_modernize_string_formatting` — `%` to f-string (refactor)
- `013_remove_debug_print_statements` — strip stray `print()` (refactor)
- ... (3 more)

### Medium

- `002_fix_off_by_one_in_pagination` — cursor math (bug_fix)
- `004_add_type_hints_to_public_api` — type annotations (refactor)
- `007_add_input_validation_to_parser` — defensive parsing (feature_add)
- `009_replace_stdlib_with_stdlib_v2` — modernize urllib usage (dep_upgrade)
- `010_implement_missing_method` — missing interface method (feature_add)
- `012_add_tests_for_uncovered_branch` — backfill tests (feature_add)
- `014_fix_regex_greedy_match` — greedy regex (bug_fix)

### Hard

- `005_fix_recursive_callsite_off_by_one` — recursive function (bug_fix)
- `011_fix_async_await_misuse` — async/await (bug_fix)
- `015_extract_repeated_logic_to_helper` — cross-module refactor (refactor)
- `017_fix_decorator_order_bug` — decorator ordering (bug_fix)
- `018_add_property_based_test` — Hypothesis test (feature_add)

(Mix to be finalized during M1 curation.)

---

## Cross-references

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the `Task` data model
- [`EVAL_METHODOLOGY.md`](EVAL_METHODOLOGY.md) — how tasks are scored
- [`FLOW.md`](FLOW.md) — how tasks are loaded and executed
- [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) — non-functional requirements (reproducibility, defensibility)
