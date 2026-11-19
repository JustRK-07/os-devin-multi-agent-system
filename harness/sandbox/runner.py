"""Isolated Docker test execution; unsafe local runner only by explicit opt-in."""
from __future__ import annotations

import os
import re
import resource
import shlex
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    passed: bool
    exit_code: int
    output: str
    timed_out: bool = False


def test_command(command: str) -> list[str]:
    parts = shlex.split(command)
    if not parts or Path(parts[0]).name not in ('python', 'python3', 'pytest'):
        raise ValueError('test command must start with python, python3, or pytest')
    if any(re.search(r'[;&|`$<>]', part) for part in parts):
        raise ValueError('shell metacharacters are not allowed in test commands')
    return parts


def run_tests(workspace: Path, command: str, *, sandbox: str = 'docker',
              allow_unsafe_local: bool = False, timeout: int = 30) -> TestResult:
    argv = test_command(command)
    if sandbox == 'docker':
        if not shutil.which('docker'):
            raise RuntimeError('Docker not installed: install/start Docker or use explicit trusted local mode')
        # The workspace mount is read-only; no network or elevated privileges.
        run = ['docker','run','--rm','--network','none','--read-only',
               '--cap-drop','ALL','--security-opt','no-new-privileges',
               '--pids-limit','64','--memory','512m','--cpus','1',
               '--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
               '--user','65534:65534','-e','PYTHONDONTWRITEBYTECODE=1',
               '-v',f'{workspace.resolve()}:/workspace:ro','-w','/workspace',
               'python:3.12-slim', *argv]
    elif sandbox == 'local':
        if not allow_unsafe_local:
            raise RuntimeError('Local test execution is unsafe; pass --allow-unsafe-local for trusted code only')
        run = argv
    else:
        raise ValueError('sandbox must be docker or local')

    def limits() -> None:
        if sandbox == 'local' and os.name == 'posix':
            resource.setrlimit(resource.RLIMIT_CPU, (min(timeout + 2, 60), min(timeout + 2, 60)))
            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))

    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONPATH':str(workspace)}
    process = subprocess.Popen(run, cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True, env=env,
                               preexec_fn=limits if os.name == 'posix' else None)
    try:
        output, _ = process.communicate(timeout=timeout)
        return TestResult(process.returncode == 0, process.returncode, output[-12_000:])
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL) if os.name == 'posix' else process.kill()
        output, _ = process.communicate()
        return TestResult(False, -1, output[-12_000:] + '\nTIMEOUT', True)
