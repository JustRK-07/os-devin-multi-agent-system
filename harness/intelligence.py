"""Lightweight Python module import and per-function call graph for planner context."""
from __future__ import annotations
import ast
from pathlib import Path


def inspect_python_repo(root: Path, max_files: int = 100) -> dict:
    index: dict[str, dict] = {}
    for file in sorted(root.rglob('*.py')):
        if any(part.startswith('.') or part in ('node_modules','venv','__pycache__') for part in file.relative_to(root).parts):
            continue
        if len(index) >= max_files:
            break
        if file.stat().st_size > 256_000 or file.is_symlink():
            continue
        rel = file.relative_to(root).as_posix()
        try:
            tree = ast.parse(file.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeError):
            index[rel] = {'parse_error': True}
            continue
        imports = set()
        functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = sorted({n.func.id if isinstance(n.func, ast.Name) else n.func.attr
                    for n in ast.walk(node) if isinstance(n, ast.Call)
                    and isinstance(n.func, (ast.Name, ast.Attribute))})
        index[rel] = {'imports':sorted(imports), 'functions':functions}
    return index
