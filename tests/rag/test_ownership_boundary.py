"""Guard the ownership boundary between the standalone RAG and backend."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_ROOT = PROJECT_ROOT / "src" / "rag"
BACKEND_ROOT = PROJECT_ROOT / "backend"

BACKEND_MODULES = {
    "backend",
    "django",
    "rest_framework",
    "fastapi",
    "flask",
}
RAG_MODULE_PREFIXES = {"src.rag", "rag"}


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            imported.append(node.args[0].value)
    return imported


def _starts_with_any(module: str, prefixes: set[str]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in prefixes
    )


def test_rag_does_not_depend_on_backend_or_web_frameworks() -> None:
    violations: list[str] = []
    for path in _python_files(RAG_ROOT):
        for module in _imports(path):
            if _starts_with_any(module, BACKEND_MODULES):
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative}: imports {module}")
    assert not violations, (
        "RAG must remain backend/framework independent:\n"
        + "\n".join(violations)
    )


def test_backend_does_not_integrate_rag() -> None:
    violations: list[str] = []
    for path in _python_files(BACKEND_ROOT):
        for module in _imports(path):
            if _starts_with_any(module, RAG_MODULE_PREFIXES):
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative}: imports {module}")
    assert not violations, (
        "Backend integration belongs to the backend owner:\n"
        + "\n".join(violations)
    )
