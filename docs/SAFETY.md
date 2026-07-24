# Safety — OS Devin Evaluation Harness

This document defines the safety baseline and the experimental isolation levels. **Safety is a baseline, not an experimental variable.** Even the `baseline` config runs in a disposable checkout with no network access. The experimental question is purely about the *degree* of isolation, not whether the host is at risk.

---

## Overview

The harness runs LLM-driven code that may:
- Make arbitrary tool calls
- Generate and execute arbitrary shell commands
- Pull in dependencies
- Write to files

Without isolation, this would be a security nightmare on a developer's laptop. The architecture separates two concerns:

1. **Safety baseline** — always-on, protects the host from the agent
2. **Experimental isolation** — the toggle, varies the *degree* of isolation as part of the experimental matrix

The local-safe executor and the Docker executor both satisfy the safety baseline; they differ in the experimental isolation level.

---

## The safety baseline

The following protections are **always on**, regardless of config:

### Disposable workspace

Every run executes in a fresh temporary directory. The worker's CWD is the temp directory; the user's CWD is never touched.

```python
# LocalSafeExecutor
workdir = Path(tempfile.mkdtemp(prefix="os_devin_"))

# DockerExecutor
volume_name = f"os_devin_{run_id}"
docker_client.volumes.create(volume_name)
```

The temp directory is removed on `__exit__`, even on exception. See [Teardown guarantees](#teardown-guarantees).

### Network blocked

The agent's subprocess has no network access. This is enforced by:

- **Local-safe:** the subprocess inherits no proxy environment, and the harness does not pass any `http_proxy`/`https_proxy`/credentials. The agent can still attempt `curl https://example.com` — it just fails.
- **Docker:** the container is started with `--network=none`. The agent's `curl` fails immediately.

In both cases, the agent cannot exfiltrate data, cannot pull packages from PyPI, and cannot reach external services.

### Resource limits

Per-subprocess limits, enforced before the agent's code runs:

| Resource | Limit | How |
|---|---|---|
| CPU time | 60 seconds | `resource.RLIMIT_CPU` |
| Memory | 512 MB | `resource.RLIMIT_AS` |
| File descriptors | 64 | `resource.RLIMIT_NOFILE` |
| Processes | 32 | `resource.RLIMIT_NPROC` |

These limits are set via `preexec_fn` (local-safe) or Docker `--ulimit` (docker). They prevent:
- Fork bombs
- Memory exhaustion
- Disk fill (via fd exhaustion)
- Runaway loops

### Stripped environment

The subprocess gets a minimal environment:

```python
env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp/null",
    "TMPDIR": str(workdir / ".tmp"),
    "PYTHONDONTWRITEBYTECODE": "1",
    # No AWS_*, no GITHUB_TOKEN, no SSH agent, no anything else
}
```

No API keys, no SSH keys, no git credentials, no cloud SDK state. The agent runs with nothing from the host user environment.

### Process group kill

The subprocess is started in a new process group (`os.setpgrp()`). On teardown, the harness kills the entire group, not just the parent. This prevents orphaned children.

### Filesystem scope

The agent can read/write only inside its workspace. The harness:

- Starts the subprocess with `cwd=workdir`
- Does not bind-mount any host paths
- Does not pass any host file paths as arguments

### Teardown guarantees

The executor's `__exit__` always runs (Python guarantees `try/finally` semantics). On exit:

- Local-safe: `shutil.rmtree(workdir, ignore_errors=True)`
- Docker: `container.stop(timeout=2)` + `container.remove()`

The cleanup is idempotent; running it twice is safe.

---

## Experimental isolation levels

The experimental variable is the **degree** of isolation. Two levels in v1.

### `local_safe`

A Python subprocess with all the baseline protections above. No Docker.

**What's protected:**
- Host filesystem (out of the workspace)
- Host environment (no keys, no creds)
- Host network (no proxy, no inherited creds)
- Host resources (RLIMIT_*)

**What it does NOT protect against:**
- A kernel-level exploit in the agent's code (no kernel isolation)
- Side effects on the host process (file handles, signal handlers, etc.)
- A malicious package installed via pip into the workspace's `.venv` (which is dropped on teardown)

For the purposes of this research, `local_safe` is sufficient. The agent is a research subject, not an adversary. The biggest realistic risk is the agent making a mess that the operator has to clean up — and the disposable workspace handles that.

### `docker`

A full ephemeral container with all the baseline protections plus kernel isolation.

**Adds on top of `local_safe`:**
- Kernel-level filesystem isolation (no syscall escapes to the host)
- User namespace remapping (no root in the container)
- Network namespace isolation (no network stack at all)
- Process namespace isolation (no PID 1 visibility)
- Volume-only file access (no host mounts)

**Docker run command (excerpt):**

```python
container = docker_client.containers.run(
    image="python:3.12-slim",
    command="sleep infinity",  # harness execs into it
    user="1000:1000",
    network_mode="none",
    read_only=True,            # root filesystem is read-only
    tmpfs={"/tmp": "size=64M,uid=1000"},
    volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
    ulimits=[
        docker.types.Ulimit(name="cpu", soft=60, hard=60),
        docker.types.Ulimit(name="memlock", soft=512*1024*1024, hard=512*1024*1024),
        docker.types.Ulimit(name="nofile", soft=64, hard=64),
        docker.types.Ulimit(name="nproc", soft=32, hard=32),
    ],
    cap_drop=["ALL"],          # no Linux capabilities
    security_opt=["no-new-privileges"],
    detach=True,
    auto_remove=False,         # we remove explicitly
)
```

**Trade-off:** ~1–2 seconds of setup overhead per run. Worth it for the 18 × 3 × 4 × 3 = 648-run matrix? Marginal. The expected marginal contribution of `+ast → full` is small (~4pp); some of that may be cost rather than capability.

---

## Why safety is not an experimental variable

It's tempting to compare "Docker isolation" vs "no isolation" to measure how much isolation matters. **We explicitly do not do this.** Reasons:

1. **Risk to the host.** Running an unrestricted agent on a developer's laptop is a real risk. The host could be compromised, the home directory could be wiped, or SSH keys could be exfiltrated. The harness is a research instrument, not a security test.

2. **Confounding.** Without the safety baseline, "no isolation" runs are at risk of being killed by the host environment (resource exhaustion, OOM, etc.) in ways that have nothing to do with the agent's capability. The agent's success rate would be a mixture of agent skill and host luck.

3. **Reproducibility.** The host environment is uncontrolled. Two runs on two laptops produce different results. Docker and even `local_safe` produce a controlled environment.

The experimental question is: **does extra isolation (kernel-level, on top of process-level) improve agent success rate?** The answer is expected to be small. The control is the `local_safe` baseline.

---

## What the harness does NOT protect against

The harness is a research tool. It does not implement every protection an enterprise sandbox would. Specifically:

- **No GPU isolation.** If the agent attempts to use CUDA, it can. (Not relevant for v1.)
- **No side-channel protection.** Timing attacks, cache attacks, etc. are out of scope.
- **No supply-chain protection.** The agent can `pip install` arbitrary packages. The packages run with the same restrictions as the agent.
- **No multi-tenant isolation.** The harness assumes a single user on a single laptop.
- **No audit logging** beyond the JSONL trace. If you need to investigate a security incident, the trace is the artifact.

These are deliberate trade-offs. The harness is a research instrument, not a production sandbox.

---

## Threat model

The agent is **research-grade code** that may be unreliable but is not malicious. The threat model is:

- **Accidental damage:** the agent writes to the wrong file, runs the wrong command, or loops forever. The sandbox prevents host damage and bounds resource use.
- **Prompt injection:** the task description or repo contains instructions that try to subvert the agent. The sandbox limits the blast radius; the agent's responsibility is to be robust.
- **Bugs in the harness:** the harness itself has bugs. The teardown guarantees minimize the blast radius.

The threat model is **not**:

- A malicious agent deliberately trying to escape the sandbox. The harness is not designed for this.
- Adversarial task descriptions. The task set is curated by the author.

---

## Audit

The trace is the audit log. Every run produces a JSONL file that records:

- The exact subprocess invocations (argv, env, cwd)
- The exact files written
- The exact network attempts (and their failures)
- The exact resource limits in effect

If a run behaves unexpectedly, the trace is the first place to look.

---

## Future safety work (v2)

- **gVisor or Kata containers** for stronger kernel isolation. Currently out of scope.
- **Seccomp profiles** beyond the default. Currently out of scope.
- **Network egress allow-list** instead of blanket block. Currently blanket block.
- **Per-prompt token bucket** to bound API costs. Currently per-task token budget.

---

## Cross-references

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the `Executor` protocol and the factory
- [`FLOW.md`](FLOW.md) — when the executor is spawned and torn down
- [`CONFIG_ABLATION.md`](CONFIG_ABLATION.md) — the `full` config uses Docker isolation
- [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) — non-functional requirements (NFR4: safety)
