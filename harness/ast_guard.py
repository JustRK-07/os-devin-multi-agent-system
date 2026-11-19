"""Conservative validation of proposed edits. Defense in depth, not a sandbox."""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
import re

ALLOWED_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', '.txt', '.yml', '.yaml'}
DENIED_NAMES = {'.env', '.git', 'id_rsa', 'id_ed25519', 'credentials.json'}
SENSITIVE_PATTERNS = [re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
                      re.compile(r'(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*["\'][A-Za-z0-9_-]{16,}["\']')]
DANGEROUS_CALLS = {('os', 'system'), ('subprocess', 'run'), ('subprocess', 'Popen'),
                   ('subprocess', 'call'), ('subprocess', 'check_output'),
                   ('shutil', 'rmtree'), ('pickle', 'loads')}


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('invalid relative path')
    p = PurePosixPath(relative)
    if p.is_absolute() or any(part in ('..', '.', '') or part.startswith('.') for part in p.parts):
        raise ValueError('absolute, hidden, or traversal path denied')
    if any(part in DENIED_NAMES for part in p.parts) or p.suffix not in ALLOWED_SUFFIXES:
        raise ValueError('sensitive or unsupported file path')
    target = root / str(p)
    if any((root.joinpath(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts) + 1)):
        raise ValueError('symlink paths not allowed')
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('path escapes workspace')
    return target


def definition_names(tree: ast.AST) -> set[str]:
    return {node.name for node in getattr(tree, 'body', [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def validate_edit(root: Path, relative: str, content: str, *, scope: set[str] | None = None) -> None:
    target = safe_path(root, relative)
    if scope is not None and relative not in scope:
        raise ValueError('edit outside planner approved file scope')
    if not isinstance(content, str) or len(content.encode()) > 256_000:
        raise ValueError('nontext or oversized change')
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            raise ValueError('suspected private key or credential')
    if target.suffix == '.py':
        new = ast.parse(content, filename=relative)
        if target.exists():
            old = ast.parse(target.read_text(encoding='utf-8'), filename=relative)
            missing = definition_names(old) - definition_names(new)
            if missing:
                raise ValueError(f'public definitions removed: {sorted(missing)}')
        for node in ast.walk(new):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {'eval', 'exec', '__import__'}:
                    raise ValueError('dynamic code execution detected')
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if (node.func.value.id, node.func.attr) in DANGEROUS_CALLS:
                        raise ValueError('potentially unsafe process or deserialization call')
