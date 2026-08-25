"""Architecture boundary tests: statically verify the dependency rule
and the AI/browser separation via AST inspection of actual imports --
no third-party architecture-linting dependency, just Python's own `ast`
module. See ARCHITECTURE.md's "Architecture Boundary Tests" section.

Verified against the actual codebase before being written (not just
assumed): as of this test's introduction, `domain/` and `application/`
already satisfy every boundary checked here, and `infrastructure/ai/`/
`infrastructure/browser/` do not cross-import (trivially true today
since `infrastructure/ai/` is still an empty scaffold -- this test
exists specifically to keep that true once Phase 3 populates it).

Uses `Path(__file__).resolve()` to locate the source tree, not the
current working directory, so this is deterministic regardless of where
pytest is invoked from (including inside a fresh, isolated venv).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "jaap"


def _python_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.py"))


def _imported_module_names(file_path: Path) -> set[str]:
    """Every fully-qualified module name a file imports, via both
    `import x.y.z` and `from x.y.z import w` forms. Relative imports
    (`from . import foo`) are skipped -- this codebase uses absolute
    `jaap....` imports throughout, so a relative import here would
    already be a style deviation worth a separate lint rule, not
    something this boundary check needs to resolve.
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
    return modules


def _find_boundary_violations(
    source_dir: Path, forbidden_prefixes: tuple[str, ...]
) -> list[tuple[Path, str]]:
    """(file, forbidden_module) pairs for every import in `source_dir`
    whose module name matches one of `forbidden_prefixes` -- an exact
    match, or a match followed by '.', so "jaap.infrastructure" doesn't
    false-positive-match some future "jaap.infrastructure_other" package.
    """
    violations: list[tuple[Path, str]] = []
    for file_path in _python_files(source_dir):
        for module_name in _imported_module_names(file_path):
            for forbidden in forbidden_prefixes:
                if module_name == forbidden or module_name.startswith(forbidden + "."):
                    violations.append((file_path, module_name))
    return violations


def _format_violations(violations: list[tuple[Path, str]]) -> str:
    return "\n".join(f"  {path} imports forbidden module {module!r}" for path, module in violations)


def test_source_root_is_found_and_nonempty() -> None:
    # Guards against every other test in this file silently "passing" by
    # finding zero files to check, if the path computation above were
    # ever wrong (e.g. pointing at a nonexistent directory).
    assert _SRC_ROOT.is_dir(), f"Expected to find src/jaap at {_SRC_ROOT}"
    assert any(_SRC_ROOT.rglob("*.py")), f"Expected to find .py files under {_SRC_ROOT}"


def test_domain_does_not_import_application_infrastructure_or_presentation() -> None:
    violations = _find_boundary_violations(
        _SRC_ROOT / "domain",
        ("jaap.application", "jaap.infrastructure", "jaap.presentation"),
    )
    assert not violations, (
        "domain/ must not import from application/, infrastructure/, or "
        f"presentation/ (see ARCHITECTURE.md's Dependency Rule):\n{_format_violations(violations)}"
    )


def test_application_does_not_import_infrastructure_or_presentation() -> None:
    violations = _find_boundary_violations(
        _SRC_ROOT / "application",
        ("jaap.infrastructure", "jaap.presentation"),
    )
    assert not violations, (
        "application/ must not import from infrastructure/ or presentation/ "
        f"(see ARCHITECTURE.md's Dependency Rule):\n{_format_violations(violations)}"
    )


def test_infrastructure_ai_does_not_import_infrastructure_browser() -> None:
    violations = _find_boundary_violations(
        _SRC_ROOT / "infrastructure" / "ai",
        ("jaap.infrastructure.browser",),
    )
    assert not violations, (
        "infrastructure/ai/ must never import infrastructure/browser/ (see "
        f"ARCHITECTURE.md's AI/Browser Separation, ADR-0001):\n{_format_violations(violations)}"
    )


def test_infrastructure_browser_does_not_import_infrastructure_ai() -> None:
    violations = _find_boundary_violations(
        _SRC_ROOT / "infrastructure" / "browser",
        ("jaap.infrastructure.ai",),
    )
    assert not violations, (
        "infrastructure/browser/ must never import infrastructure/ai/ (see "
        f"ARCHITECTURE.md's AI/Browser Separation, ADR-0001):\n{_format_violations(violations)}"
    )
