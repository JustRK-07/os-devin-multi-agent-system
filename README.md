# OS Devin — Executable Multi-Agent Coding Harness

> **Status:** runnable six-role MVP with unit tests, deterministic demo and a live-model adapter. The scripted demo is not evidence of general autonomous coding ability. Optional Docker and LangGraph modes passed their combined end-to-end smoke test in GitHub Actions CI. Large-scale evaluation results are **not available**.

## Headline result

The local scripted calculator smoke test passes after one deliberate failed attempt and one Debugger repair (`python -m harness.cli demo --sandbox local --allow-unsafe-local`). This demonstrates the retry wiring, not a meaningful LLM success rate. There are **no 18-task / 50-task / 648-run benchmark results**; see [results methodology](docs/EVAL_METHODOLOGY.md).

## Project status

**Implemented and locally tested:** six concrete workflow roles (Planner, Coder, Reviewer, Security, Tester, Debugger), bounded retries, Python AST import/call indexing, file scope and path guards, basic AST change checks, structured JSONL traces, diff patch output, unit tests, and a deterministic failing-then-passing sample. A standard-library graph runner is the default.

**CI-verified:** the Docker sandbox and LangGraph integration passed the combined end-to-end smoke test in GitHub Actions (using the scripted demo model). A live OpenAI-compatible chat-completions client accepts API keys and remote models, but end-to-end external model outcomes have **not** been tested or measured. Docker and LangGraph require installed dependencies. The Docker policy is defense-in-depth, not a guarantee against hostile containers.

**Not implemented:** general multi-language AST dependency graphs, fully fledged GitHub PR automation, arbitrary build system install, browser dashboard, production-grade adversarial security audit, or published cross-model benchmarks. The design documents in `docs/` describe future work; they are not all live features.

## Quick start

Requires Python 3.11+ (3.12 recommended). Core demo and unit tests have **no third-party dependencies**. Clone the repository:

```bash
git clone https://github.com/JustRK-07/os-devin-multi-agent-system.git
cd os-devin-multi-agent-system
python -m unittest discover -s tests -v
```

Run the intentionally scripted sample, **only for trusted bundled fixture code**:

```bash
python -m harness.cli demo --sandbox local --allow-unsafe-local --output /tmp/osdevin-demo
```

The demo creates a disposable copy of `evals/tasks/demo_calculator/repo_before`, attempts a deliberately incorrect patch, runs its two failing tests, repairs the patch, and re-runs tests. Output includes a `.patch` file, a machine-readable `.json` summary, and a `.jsonl` event trace. **The input folder is unchanged**. This sample uses scripted `DemoModel` responses; it does not call an LLM.

### Run a real coding task

Install/start Docker and have an available `python:3.12-slim` image (pull the image before running if needed). Set `OPENAI_API_KEY` in your shell, not in tracked source files. The default provider uses `https://api.openai.com/v1`; optionally set `OPENAI_BASE_URL` for a compatible hosted endpoint.

```bash
export OPENAI_API_KEY='your-key-from-a-secret-manager'
docker pull python:3.12-slim
python -m harness.cli run \
  --repo /path/to/trusted-python-project \
  --task 'Fix the pagination off-by-one error and preserve the API' \
  --model gpt-4o-mini \
  --test-command 'python -m unittest discover -s tests -v' \
  --sandbox docker --max-retries 2 --output /tmp/osdevin-runs
```

The model proposes complete-file edits; the Reviewer and Security gate must approve them before testing. `run` does **not** apply edits to your input repository. Review the generated patch before applying manually with `git apply`. The sample Docker runner is intentionally restrictive: no network, no privileges, read-only checkout, limited CPU, memory and processes. It supports tests needing only the Python standard library or dependencies already included in the image. For dependency-heavy repositories, customize a trusted local Docker image in the executor code rather than relaxing the security policy.

### LangGraph execution

```bash
pip install -e '.[graph]'
python -m harness.cli demo --graph langgraph --sandbox docker
```

This uses real `StateGraph` nodes and conditional edges for review, security and test retries. Without the optional package the default `--graph native` runs the exact same roles in a standard-library state-machine. GitHub Actions installs LangGraph and exercises this route with Docker; local use still requires installing the extra.

## Project structure

```text
harness/
  cli.py                 CLI and demo/run modes
  engine.py              workflow state, agents, retry routing, patch export
  ast_guard.py           path/scope, Python AST and credential heuristics
  intelligence.py        module import and function-call indexing
  llm/client.py          OpenAI-compatible JSON protocol + scripted demo provider
  sandbox/runner.py      Docker or explicitly opted-in unsafe local test execution
  events/trace.py        structured JSONL event records
evals/tasks/demo_calculator/  trusted failing-first sample
scripts/run_eval.py       compatibility command for real model runs
tests/test_harness.py     unit tests and end-to-end scripted regression
.github/workflows/ci.yml unit tests, doc checker, demo
```

## Technology stack

Python 3.11+ standard library for the default runner; optional **LangGraph** for graph orchestration; OpenAI-compatible Chat Completions JSON adapter for live inference; **Docker** for resource-limited, offline tests; `ast` for Python source indexing/guards; `unittest` and GitHub Actions for repeatable checks. There is no Next.js dashboard or LiteLLM integration in this MVP.

## Documentation index

The design specifications are retained as future targets, not all implemented code: [overview](PROJECT_OVERVIEW.md), [spec](PROJECT_SPEC.md), [architecture](docs/ARCHITECTURE.md), [execution flow](docs/FLOW.md), [safety](docs/SAFETY.md), [evaluation methodology](docs/EVAL_METHODOLOGY.md), and [results](docs/RESULTS.md).

## Reproduction

1. Run the unit tests as shown above; the test suite includes an end-to-end scripted recovery scenario and a zero-retry failure case.
2. Run the demo; inspect `.jsonl`, `.json`, and `.patch` in the chosen output folder.
3. To test Docker isolation, run `python -m harness.cli demo --sandbox docker` on a host with Docker and the image installed.
4. To test live LLMs, supply a valid key and run the `run` command against a separate test repository; real results vary with the model and task and must be measured.

## Safety and limitations

**Do not run untrusted repository test code with `--sandbox local`.** Its resource limits are not a security boundary. Docker provides isolation controls but is not a hardened production sandbox and should not run on a privileged or sensitive host without further review. Code can contain prompt injections: the LLM is instructed to treat source files as untrusted, and all generated edits must pass deterministic gates, but those gates are incomplete and can be bypassed. Never expose secrets in source sent to a model. The input repository remains unmodified; patch application is a separate human review step.

## License

[MIT](LICENSE).
