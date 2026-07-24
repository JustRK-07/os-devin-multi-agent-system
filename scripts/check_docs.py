#!/usr/bin/env python3
"""
check_docs.py — Documentation validation loop for the OS Devin harness.

This script is the single source of truth for doc completeness. It verifies:

  1. Every required doc file exists at the expected path.
  2. Every doc has the required sections (matched by header text).
  3. Every cross-reference between docs (relative markdown link) resolves.
  4. The directory structure matches the spec.

Run from anywhere:

    python scripts/check_docs.py

Exit code 0 on full pass, 1 on any failure.

The check is re-runnable and idempotent. It does not modify any file.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────
# Configuration: which docs must exist, with required sections
# ─────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent

# A doc is "required" if it must exist. A doc is "implemented" if it must
# have its required sections. Placeholder docs (RESULTS, FAILURE_ANALYSIS,
# TRACE_SAMPLES) are required to exist but are not required to have sections.

REQUIRED_DOCS: dict[str, list[str]] = {
    "README.md": [
        "OS Devin",
        "Headline result",
        "Project status",
        "Quick start",
        "Project structure",
        "Technology stack",
        "Documentation index",
        "Reproduction",
    ],
    "PROJECT_SPEC.md": [
        "Problem statement",
        "Goals",
        "Non-goals",
        "Functional requirements",
        "Non-functional requirements",
        "Constraints",
        "Out of scope",
        "Success criteria",
        "Risks",
        "Glossary",
    ],
    "PROJECT_OVERVIEW.md": [
        "Project status",
        "Documentation completeness",
        "What is implemented today",
        "What is not implemented yet",
        "Verification",
        "Roadmap",
    ],
    "docs/ARCHITECTURE.md": [
        "Overview",
        "Component diagram",
        "Data flow",
        "Module breakdown",
        "Data model",
        "External dependencies",
        "Design invariants",
    ],
    "docs/FLOW.md": [
        "Overview",
        "Phase 1: Setup",
        "Phase 2: Pipeline",
        "Phase 3: Scoring",
        "Phase 4: Teardown",
        "Error paths",
        "Per-config flow differences",
        "Matrix flow",
    ],
    "docs/EVAL_METHODOLOGY.md": [
        "Overview",
        "The four metric families",
        "Failure class taxonomy",
        "Rubric scoring",
        "Statistical protocol",
        "Cross-model comparison",
        "What the harness does NOT measure",
    ],
    "docs/TASK_DESIGN.md": [
        "Overview",
        "Task schema",
        "Oracle",
        "Rubric",
        "Difficulty mix",
        "Category mix",
        "Ground truth failure class",
        "Task authoring workflow",
        "Immutability",
        "Example tasks",
    ],
    "docs/CONFIG_ABLATION.md": [
        "Overview",
        "The four configurations",
        "Why this ablation order",
        "Reading the ablation table",
        "Component-by-component reference",
        "What the ablation does NOT isolate",
        "Adding a new configuration",
    ],
    "docs/SAFETY.md": [
        "Overview",
        "The safety baseline",
        "Experimental isolation levels",
        "Why safety is not an experimental variable",
        "What the harness does NOT protect against",
        "Threat model",
        "Audit",
        "Future safety work",
    ],
}

# Placeholder docs: must exist, but section check is skipped (they're
# expected to be filled in by the matrix run, not by hand).
PLACEHOLDER_DOCS = [
    "docs/RESULTS.md",
    "docs/FAILURE_ANALYSIS.md",
    "docs/TRACE_SAMPLES.md",
]

# Required directories. The harness's structure depends on these.
REQUIRED_DIRECTORIES = [
    "docs",
    "scripts",
    "harness",
    "configs",
    "evals",
    "results",
    "tests",
]


# ─────────────────────────────────────────────────────────────────────────
# Check framework
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    error: str = ""

    def symbol(self) -> str:
        return "✓" if self.passed else "✗"

    def render(self) -> str:
        prefix = f"  {self.symbol()} {self.name}"
        if self.error:
            return f"{prefix}\n      ERROR: {self.error}"
        if self.detail and not self.passed:
            return f"{prefix} ({self.detail})"
        return prefix


@dataclass
class SuiteResult:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def add(self, name: str, passed: bool, detail: str = "", error: str = "") -> None:
        self.results.append(CheckResult(name, passed, detail, error))

    def add_check(self, result: CheckResult) -> None:
        self.results.append(result)


# ─────────────────────────────────────────────────────────────────────────
# Individual checks
# ─────────────────────────────────────────────────────────────────────────

def check_doc_exists(rel_path: str, suite: SuiteResult) -> None:
    """Check that a required doc exists at the expected path."""
    abs_path = REPO_ROOT / rel_path
    if abs_path.is_file():
        suite.add(f"exists: {rel_path}", True)
    else:
        suite.add(f"exists: {rel_path}", False,
                  error=f"File not found at {abs_path}")


def check_doc_has_sections(rel_path: str, required: list[str],
                           suite: SuiteResult) -> None:
    """Check that a doc has all required sections.

    Section headers are matched by their core text — leading #'s and trailing
    decorations are stripped before matching.
    """
    abs_path = REPO_ROOT / rel_path
    if not abs_path.is_file():
        # Already reported by check_doc_exists; skip.
        return

    content = abs_path.read_text(encoding="utf-8")

    # Extract all headers (lines starting with one or more '#').
    headers = re.findall(r"^#{1,6}\s+(.+?)\s*$", content, re.MULTILINE)

    # Normalize: strip backticks, em-dashes, parentheticals, colons.
    def normalize(s: str) -> str:
        s = s.strip()
        s = re.sub(r"`", "", s)
        s = re.sub(r"—", "-", s)
        return s.lower()

    header_set = {normalize(h) for h in headers}

    missing = []
    for section in required:
        # Strip decorations from the section name for matching.
        normalized = normalize(section)
        if normalized not in header_set:
            # Try a fuzzy match: does any header start with this section?
            if not any(h.startswith(normalized) for h in header_set):
                missing.append(section)

    if missing:
        suite.add(
            f"sections: {rel_path}",
            False,
            detail=f"missing {len(missing)} of {len(required)}",
            error=", ".join(missing),
        )
    else:
        suite.add(
            f"sections: {rel_path}",
            True,
            detail=f"{len(required)}/{len(required)}",
        )


def check_cross_references(rel_path: str, suite: SuiteResult) -> None:
    """Check that all relative markdown links in a doc resolve to existing files.

    Links are of the form `[text](target)` or `[text](target#anchor)`.
    We resolve the target path relative to the doc's directory.
    """
    abs_path = REPO_ROOT / rel_path
    if not abs_path.is_file():
        return

    content = abs_path.read_text(encoding="utf-8")
    doc_dir = abs_path.parent

    # Match markdown links. Skip images (![]()) and absolute URLs.
    link_pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
    links = link_pattern.findall(content)

    failures: list[str] = []
    for text, target in links:
        # Strip anchor if present
        target_path = target.split("#", 1)[0]

        # Skip absolute URLs and bare anchors
        if not target_path or target_path.startswith(("http://", "https://", "mailto:")):
            continue

        # Resolve relative to the doc's directory
        resolved = (doc_dir / target_path).resolve()
        if not resolved.exists():
            failures.append(f"[{text}]({target}) → {resolved}")

    if failures:
        # Cap the displayed failures to 5 to avoid noise.
        shown = failures[:5]
        more = f" (+{len(failures) - 5} more)" if len(failures) > 5 else ""
        suite.add(
            f"refs: {rel_path}",
            False,
            detail=f"{len(failures)} broken",
            error=", ".join(shown) + more,
        )
    else:
        suite.add(
            f"refs: {rel_path}",
            True,
            detail=f"{len(links)} links",
        )


def check_directory_exists(rel_path: str, suite: SuiteResult) -> None:
    """Check that a required directory exists."""
    abs_path = REPO_ROOT / rel_path
    if abs_path.is_dir():
        suite.add(f"dir: {rel_path}/", True)
    else:
        suite.add(f"dir: {rel_path}/", False,
                  error=f"Directory not found at {abs_path}")


def check_self_reference(suite: SuiteResult) -> None:
    """Meta-check: this script is the single source of truth for doc checks."""
    self_path = Path(__file__).resolve()
    if self_path.is_file():
        suite.add("self: scripts/check_docs.py exists", True)
    else:
        suite.add("self: scripts/check_docs.py exists", False,
                  error="This script is missing — cannot trust the check loop.")


# ─────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────

def run_all_checks() -> SuiteResult:
    suite = SuiteResult()

    # Self-reference (must pass for the rest to be meaningful)
    check_self_reference(suite)

    # 1. Required docs exist
    print("[1/4] Checking required docs exist...")
    for rel_path in REQUIRED_DOCS:
        check_doc_exists(rel_path, suite)
    for rel_path in PLACEHOLDER_DOCS:
        check_doc_exists(rel_path, suite)

    # 2. Required sections per doc
    print("[2/4] Checking required sections per doc...")
    for rel_path, sections in REQUIRED_DOCS.items():
        check_doc_has_sections(rel_path, sections, suite)

    # 3. Cross-references resolve
    print("[3/4] Checking cross-references between docs...")
    all_docs = list(REQUIRED_DOCS.keys()) + PLACEHOLDER_DOCS
    for rel_path in all_docs:
        check_cross_references(rel_path, suite)

    # 4. Directory structure
    print("[4/4] Checking directory structure...")
    for rel_path in REQUIRED_DIRECTORIES:
        check_directory_exists(rel_path, suite)

    return suite


def render_results(suite: SuiteResult) -> None:
    print()
    print("=" * 60)
    print("OS Devin Evaluation Harness — Doc Check Loop")
    print("=" * 60)
    print()

    # Render per-check results
    for r in suite.results:
        print(r.render())

    print()
    print("=" * 60)
    if suite.all_passed:
        print(f"RESULT: {suite.passed}/{suite.passed + suite.failed} checks passed")
        print("STATUS: GREEN — all docs are in order.")
    else:
        print(f"RESULT: {suite.passed}/{suite.passed + suite.failed} checks passed")
        print(f"STATUS: RED — {suite.failed} check(s) failed.")
    print("=" * 60)


def main() -> int:
    suite = run_all_checks()
    render_results(suite)
    return 0 if suite.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
