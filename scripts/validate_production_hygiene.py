from __future__ import annotations

import ast
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
SCRIPT_ROOT = ROOT / "scripts"

FORBIDDEN_DOMAIN_IMPORTS = (
    "boto3",
    "fastapi",
    "google",
    "httpx",
    "openai",
    "redis",
    "sqlalchemy",
    "tests",
)
PLACEHOLDER_MESSAGES = (
    "not implemented",
    "placeholder implementation",
    "stub implementation",
    "unavailable until",
)
COMMENT_MARKERS = ("TODO", "FIXME", "XXX", "HACK")
SENSITIVE_ASSIGNMENT_PARTS = (
    "api_key",
    "access_token",
    "client_secret",
    "password",
    "private_key",
    "shared_secret",
    "signing_secret",
)
SENSITIVE_TRACKED_NAMES = {
    ".env",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
SENSITIVE_TRACKED_SUFFIXES = (".key", ".p12", ".pfx", ".pem")


def _python_files(root: Path) -> Iterable[Path]:
    return sorted(root.rglob("*.py"))


def _is_exception_class(node: ast.ClassDef) -> bool:
    return any(
        isinstance(base, ast.Name) and base.id.endswith(("Error", "Exception"))
        for base in node.bases
    )


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _assignment_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SecretStr"
        and len(node.args) == 1
    ):
        return _literal_string(node.args[0])
    return None


def _is_intentional_platform_pass(node: ast.Pass, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.ExceptHandler):
        return False
    caught = parent.type
    return isinstance(caught, ast.Name) and caught.id == "NotImplementedError"


def _inspect_python(path: Path) -> list[str]:
    relative = path.relative_to(ROOT)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(relative))
    parents = _parent_map(tree)
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            raised = node.exc
            if isinstance(raised, ast.Call):
                raised = raised.func
            if isinstance(raised, ast.Name) and raised.id == "NotImplementedError":
                findings.append(f"{relative}:{node.lineno}: reachable NotImplementedError")
        elif isinstance(node, ast.Pass):
            parent = parents.get(node)
            if isinstance(parent, ast.ClassDef) and _is_exception_class(parent):
                continue
            if _is_intentional_platform_pass(node, parents):
                continue
            findings.append(f"{relative}:{node.lineno}: reachable pass statement")
        elif isinstance(node, ast.If) and isinstance(node.test, ast.Constant):
            if node.test.value is False:
                findings.append(f"{relative}:{node.lineno}: permanently disabled branch")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            normalized = node.value.casefold()
            if path.is_relative_to(SOURCE_ROOT) and any(
                marker in normalized for marker in PLACEHOLDER_MESSAGES
            ):
                findings.append(f"{relative}:{node.lineno}: runtime placeholder message")
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            value = node.value
            literal = _literal_string(value)
            if not literal:
                continue
            for name in _assignment_names(node):
                normalized_name = name.casefold()
                if any(part in normalized_name for part in SENSITIVE_ASSIGNMENT_PARTS):
                    finding = (
                        f"{relative}:{node.lineno}: hard-coded value assigned "
                        f"to sensitive name {name}"
                    )
                    findings.append(finding)

    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if any(marker in stripped.upper() for marker in COMMENT_MARKERS):
            findings.append(f"{relative}:{line_number}: unresolved marker comment")
    return findings


def _inspect_import_boundaries(path: Path) -> list[str]:
    relative = path.relative_to(ROOT)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
    findings: list[str] = []
    is_domain = "domain" in relative.parts
    for node in ast.walk(tree):
        modules: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = (node.module,)
        for module in modules:
            if module == "tests" or module.startswith("tests."):
                findings.append(f"{relative}:{node.lineno}: production code imports tests")
            if is_domain and any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in FORBIDDEN_DOMAIN_IMPORTS
            ):
                findings.append(
                    f"{relative}:{node.lineno}: domain imports forbidden dependency {module}"
                )
    return findings


def _tracked_paths() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to verify that sensitive files are not tracked")
    completed = subprocess.run(  # noqa: S603 - fixed read-only command
        [git, "ls-files", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("git ls-files failed; sensitive tracked-file policy is unverified")
    return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def _inspect_sensitive_files() -> list[str]:
    findings: list[str] = []
    for policy_file in (ROOT / ".gitignore", ROOT / ".dockerignore"):
        entries = {
            line.strip()
            for line in policy_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if ".env" not in entries:
            findings.append(f"{policy_file.relative_to(ROOT)}: must exclude .env")

    for path in _tracked_paths():
        normalized_name = path.name.casefold()
        if normalized_name in SENSITIVE_TRACKED_NAMES or normalized_name.endswith(
            SENSITIVE_TRACKED_SUFFIXES
        ):
            findings.append(f"{path.relative_to(ROOT)}: sensitive file must not be tracked")
    return findings


def main() -> None:
    paths = [*_python_files(SOURCE_ROOT), *_python_files(SCRIPT_ROOT)]
    findings: list[str] = []
    for path in paths:
        findings.extend(_inspect_python(path))
        if path.is_relative_to(SOURCE_ROOT):
            findings.extend(_inspect_import_boundaries(path))
    findings.extend(_inspect_sensitive_files())

    if findings:
        formatted = "\n".join(f" - {finding}" for finding in sorted(set(findings)))
        raise SystemExit(f"production hygiene: failed ({len(set(findings))} findings)\n{formatted}")
    print(f"production hygiene: valid ({len(paths)} Python files inspected)")


if __name__ == "__main__":
    main()
