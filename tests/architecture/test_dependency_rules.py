from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "demo_command_center"
FORBIDDEN_DOMAIN_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "boto3",
    "redis",
    "httpx",
    "openai",
    "google",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _imported_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            symbols.update(alias.asname or alias.name.rsplit(".", 1)[-1] for alias in node.names)
    return symbols


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _local_imports(path: Path) -> set[str]:
    """Resolve imports to source modules without importing application code."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = _module_name(path).split(".")
    if path.name != "__init__.py":
        current.pop()
    resolved: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            resolved.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current[: len(current) - node.level + 1]
                if node.module:
                    base.extend(node.module.split("."))
                resolved.add(".".join(base))
            elif node.module:
                resolved.add(node.module)
    return {name for name in resolved if name.startswith("demo_command_center")}


def _existing_module(import_name: str, modules: set[str]) -> str | None:
    candidate = import_name
    while candidate.startswith("demo_command_center"):
        if candidate in modules:
            return candidate
        if "." not in candidate:
            return None
        candidate = candidate.rsplit(".", 1)[0]
    return None


def test_domain_modules_do_not_import_frameworks_or_providers() -> None:
    domain_files = list((SOURCE / "modules").glob("*/domain/**/*.py"))
    assert domain_files
    for path in domain_files:
        for imported in _imports(path):
            assert not imported.startswith(FORBIDDEN_DOMAIN_PREFIXES), (path, imported)


def test_production_source_does_not_import_test_fakes() -> None:
    for path in SOURCE.rglob("*.py"):
        assert all(not name.startswith("tests") for name in _imports(path)), path


def test_ports_do_not_depend_on_integrations_or_infrastructure() -> None:
    port_files = list(SOURCE.glob("modules/*/ports/**/*.py"))
    assert port_files
    for path in port_files:
        imports = _imports(path)
        assert not any(".integrations" in name or ".infrastructure" in name for name in imports), (
            path
        )


def test_source_module_dependency_graph_has_no_cycles() -> None:
    paths = list(SOURCE.rglob("*.py"))
    module_paths = {_module_name(path): path for path in paths}
    graph: dict[str, set[str]] = defaultdict(set)
    for module, path in module_paths.items():
        for imported in _local_imports(path):
            dependency = _existing_module(imported, set(module_paths))
            if dependency and dependency != module:
                graph[module].add(dependency)

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            start = visiting.index(module)
            cycle = " -> ".join([*visiting[start:], module])
            raise AssertionError(f"source dependency cycle: {cycle}")
        if module in visited:
            return
        visiting.append(module)
        for dependency in sorted(graph[module]):
            visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in sorted(module_paths):
        visit(module)


def test_llm_port_cannot_share_an_application_module_with_effect_ports() -> None:
    """An LLM result is data; an application module cannot also own an effect port."""
    effect_ports = {"MessagingPort", "PaymentPort", "CalendarPort", "WebsiteGatewayPort"}
    for path in SOURCE.glob("modules/*/application/**/*.py"):
        names = _imported_symbols(path)
        source = path.read_text(encoding="utf-8")
        if "LlmPort" in source:
            assert not effect_ports.intersection(names), path
