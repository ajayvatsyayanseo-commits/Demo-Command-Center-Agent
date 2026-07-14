from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable).resolve()
LARAVEL_ADAPTER = ROOT / "integrations" / "nxtutors-laravel-adapter"
TERRAFORM_ROOT = ROOT / "infra" / "terraform"


class GateStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 - gate status, not a credential
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    status: GateStatus
    detail: str


class GateRunner:
    def __init__(self) -> None:
        self.results: list[GateResult] = []

    def skip(self, name: str, detail: str) -> None:
        self._record(GateResult(name, GateStatus.SKIP, detail))

    def run_command(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path = ROOT,
        environment: dict[str, str] | None = None,
        timeout_seconds: int = 600,
    ) -> bool:
        print(f"\n--- {name} ---", flush=True)
        try:
            completed = subprocess.run(  # noqa: S603 - commands are fixed gate definitions
                command,
                cwd=cwd,
                env=environment,
                check=False,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._record(GateResult(name, GateStatus.FAIL, type(exc).__name__))
            return False
        if completed.returncode == 0:
            self._record(GateResult(name, GateStatus.PASS, "completed"))
            return True
        self._record(
            GateResult(name, GateStatus.FAIL, f"command exited with {completed.returncode}")
        )
        return False

    def _record(self, result: GateResult) -> None:
        self.results.append(result)
        print(f"[{result.status}] {result.name}: {result.detail}", flush=True)


def _module_command(module: str, *arguments: str) -> list[str]:
    return [str(PYTHON), "-m", module, *arguments]


def _module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _tool(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered is not None:
        return discovered
    executable_name = f"{name}.exe" if os.name == "nt" else name
    sibling = PYTHON.parent / executable_name
    return str(sibling) if sibling.is_file() else None


def _run_python_gates(runner: GateRunner) -> None:
    uv = _tool("uv")
    if uv is None:
        runner.skip("dependency lock", "uv is not installed or not on PATH")
    else:
        runner.run_command("dependency lock", [uv, "lock", "--check"])

    if _module_available("pip_audit"):
        runner.run_command(
            "dependency vulnerability audit",
            _module_command("pip_audit", "--local", "--progress-spinner", "off"),
            timeout_seconds=900,
        )
    else:
        runner.skip(
            "dependency vulnerability audit",
            "pip-audit is not installed in the active Python environment",
        )

    if _module_available("ruff"):
        runner.run_command(
            "format",
            _module_command("ruff", "format", "--check", "src", "tests", "scripts"),
        )
        runner.run_command("lint", _module_command("ruff", "check", "src", "tests", "scripts"))
    else:
        runner.skip("format", "ruff is not installed in the active Python environment")
        runner.skip("lint", "ruff is not installed in the active Python environment")

    if _module_available("mypy"):
        runner.run_command("strict type check", _module_command("mypy", "src", "tests"))
    else:
        runner.skip("strict type check", "mypy is not installed in the active Python environment")

    runner.run_command("contract validation", [str(PYTHON), "scripts/validate_contracts.py"])
    runner.run_command("workflow validation", [str(PYTHON), "scripts/validate_workflows.py"])
    runner.run_command(
        "production hygiene", [str(PYTHON), "scripts/validate_production_hygiene.py"]
    )
    runner.run_command(
        "migration graph and offline SQL", [str(PYTHON), "scripts/validate_migrations.py"]
    )

    if _module_available("pytest") and _module_available("pytest_cov"):
        with tempfile.TemporaryDirectory(prefix="dcc-pytest-") as temporary_directory:
            runner.run_command(
                "tests and coverage",
                _module_command(
                    "pytest",
                    "-c",
                    str(ROOT / "pyproject.toml"),
                    "--rootdir",
                    str(ROOT),
                    "--cov=demo_command_center",
                    "--cov-config",
                    str(ROOT / "pyproject.toml"),
                    "--cov-report=term-missing",
                    str(ROOT / "tests"),
                ),
                cwd=Path(temporary_directory),
                timeout_seconds=900,
            )
    else:
        runner.skip("tests and coverage", "pytest/pytest-cov is not installed")


def _run_terraform_gates(runner: GateRunner) -> None:
    terraform = _tool("terraform")
    if terraform is None:
        runner.skip("terraform format", "terraform is not installed or not on PATH")
        runner.skip("terraform initialization", "terraform is not installed or not on PATH")
        runner.skip("terraform validation", "terraform is not installed or not on PATH")
        return
    runner.run_command(
        "terraform format",
        [terraform, f"-chdir={TERRAFORM_ROOT}", "fmt", "-check", "-recursive"],
    )
    initialized = runner.run_command(
        "terraform initialization",
        [
            terraform,
            f"-chdir={TERRAFORM_ROOT}",
            "init",
            "-backend=false",
            "-input=false",
            "-upgrade=false",
        ],
        timeout_seconds=900,
    )
    if initialized:
        runner.run_command(
            "terraform validation", [terraform, f"-chdir={TERRAFORM_ROOT}", "validate"]
        )
    else:
        runner.skip("terraform validation", "terraform initialization did not complete")


def _run_terraform_policy_gates(runner: GateRunner) -> None:
    tflint = _tool("tflint")
    if tflint is None:
        runner.skip("terraform lint", "tflint is not installed or not on PATH")
    else:
        runner.run_command(
            "terraform lint",
            [tflint, f"--chdir={TERRAFORM_ROOT}", "--recursive"],
            timeout_seconds=900,
        )

    checkov = _tool("checkov")
    tfsec = _tool("tfsec")
    if checkov is not None:
        runner.run_command(
            "terraform security scan",
            [checkov, "--directory", str(TERRAFORM_ROOT), "--framework", "terraform", "--quiet"],
            timeout_seconds=900,
        )
    elif tfsec is not None:
        runner.run_command(
            "terraform security scan",
            [tfsec, str(TERRAFORM_ROOT)],
            timeout_seconds=900,
        )
    else:
        runner.skip(
            "terraform security scan",
            "neither checkov nor tfsec is installed or on PATH",
        )


def _run_laravel_adapter_gates(runner: GateRunner) -> None:
    if not LARAVEL_ADAPTER.is_dir():
        runner.skip("Laravel adapter manifest", "adapter directory is absent")
        runner.skip("Laravel adapter tests", "adapter directory is absent")
        return

    composer = _tool("composer")
    if composer is None:
        runner.skip("Laravel adapter manifest", "composer is not installed or not on PATH")
    else:
        runner.run_command(
            "Laravel adapter manifest",
            [composer, "validate", "--strict", "--no-check-publish", "--no-ansi"],
            cwd=LARAVEL_ADAPTER,
        )

    php = _tool("php")
    phpunit = LARAVEL_ADAPTER / "vendor" / "bin" / "phpunit"
    php_test_command = [php] if php is not None else []
    if php is None:
        runner.skip("Laravel adapter tests", "PHP is not installed or not on PATH")
    elif not phpunit.is_file():
        runner.skip(
            "Laravel adapter tests",
            "vendor/bin/phpunit is absent; run a locked composer install first",
        )
    else:
        extension_probe = "exit(extension_loaded('pdo_sqlite') ? 0 : 1);"
        if not _probe([php, "-r", extension_probe], cwd=LARAVEL_ADAPTER):
            explicit_extensions = [
                php,
                "-d",
                "extension=pdo_sqlite",
                "-d",
                "extension=sqlite3",
            ]
            if not _probe([*explicit_extensions, "-r", extension_probe], cwd=LARAVEL_ADAPTER):
                runner.skip(
                    "Laravel adapter tests",
                    "PHP pdo_sqlite is unavailable; the Testbench database cannot start",
                )
                return
            php_test_command = explicit_extensions
        runner.run_command(
            "Laravel adapter tests",
            [*php_test_command, str(phpunit), "--colors=never"],
            cwd=LARAVEL_ADAPTER,
            timeout_seconds=900,
        )


def _probe(command: list[str], *, cwd: Path = ROOT) -> bool:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed availability probe
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _run_container_gate(runner: GateRunner) -> None:
    docker = _tool("docker")
    if docker is None:
        runner.skip("container build", "docker is not installed or not on PATH")
        runner.skip("container vulnerability scan", "docker is unavailable")
        runner.skip("container SBOM", "docker is unavailable")
        return
    if not _probe([docker, "info", "--format", "{{.ServerVersion}}"]):
        runner.skip("container build", "docker daemon is unavailable")
        runner.skip("container vulnerability scan", "docker daemon is unavailable")
        runner.skip("container SBOM", "docker daemon is unavailable")
        return
    built = runner.run_command(
        "container build",
        [
            docker,
            "build",
            "--tag",
            "demo-command-center:production-check",
            "--build-arg",
            "VCS_REF=production-check",
            str(ROOT),
        ],
        timeout_seconds=1800,
    )
    if not built:
        runner.skip("container vulnerability scan", "container build did not complete")
        runner.skip("container SBOM", "container build did not complete")
        return
    trivy = _tool("trivy")
    if trivy is None:
        runner.skip("container vulnerability scan", "trivy is not installed or not on PATH")
    else:
        runner.run_command(
            "container vulnerability scan",
            [
                trivy,
                "image",
                "--exit-code",
                "1",
                "--severity",
                "HIGH,CRITICAL",
                "demo-command-center:production-check",
            ],
            timeout_seconds=1800,
        )
    syft = _tool("syft")
    if syft is None:
        runner.skip("container SBOM", "syft is not installed or not on PATH")
    else:
        runner.run_command(
            "container SBOM",
            [syft, "demo-command-center:production-check", "--output", "cyclonedx-json"],
            timeout_seconds=900,
        )


def _run_secret_scan_gate(runner: GateRunner) -> None:
    gitleaks = _tool("gitleaks")
    if gitleaks is None:
        runner.skip("repository secret scan", "gitleaks is not installed or not on PATH")
        return
    if not (ROOT / ".git").exists():
        runner.skip(
            "repository secret scan",
            "Git metadata is absent; refusing a directory scan that could read ignored .env files",
        )
        return
    runner.run_command(
        "repository secret scan",
        [gitleaks, "detect", "--source", str(ROOT), "--no-banner", "--redact"],
    )


def _safe_local_test_database(database_url: str) -> bool:
    normalized = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    database_name = parsed.path.removeprefix("/").casefold()
    return (
        parsed.scheme == "postgresql"
        and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        and any(marker in database_name for marker in ("test", "check", "ci"))
    )


def _run_postgres_round_trip(runner: GateRunner, *, mutation_allowed: bool) -> None:
    database_url = os.environ.get("PRODUCTION_CHECK_POSTGRES_URL", "")
    if not database_url:
        runner.skip(
            "PostgreSQL migration round-trip",
            "PRODUCTION_CHECK_POSTGRES_URL is not set; offline SQL was validated instead",
        )
        return
    if not mutation_allowed:
        runner.skip(
            "PostgreSQL migration round-trip",
            "test database URL is present but --allow-database-mutation was not supplied",
        )
        return
    if not _safe_local_test_database(database_url):
        runner.results.append(
            GateResult(
                "PostgreSQL migration round-trip",
                GateStatus.FAIL,
                "URL must target a loopback PostgreSQL database named test/check/ci",
            )
        )
        print(
            "[FAIL] PostgreSQL migration round-trip: unsafe database target rejected",
            flush=True,
        )
        return

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    runner.run_command(
        "PostgreSQL migration round-trip",
        [str(PYTHON), "scripts/validate_migrations.py", "--round-trip"],
        environment=environment,
    )


def _validate_smoke_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("smoke URL must not contain credentials, query parameters, or fragments")
    is_loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise ValueError("smoke URL must use HTTPS, except for a loopback test service")
    if not parsed.hostname:
        raise ValueError("smoke URL must include a hostname")
    return base_url.rstrip("/")


def _run_live_smoke_gate(runner: GateRunner) -> None:
    configured_url = os.environ.get("PRODUCTION_CHECK_SMOKE_BASE_URL", "")
    if not configured_url:
        runner.skip(
            "deployed environment smoke",
            "PRODUCTION_CHECK_SMOKE_BASE_URL/live dependency evidence is not configured",
        )
        return
    try:
        base_url = _validate_smoke_base_url(configured_url)
        for endpoint in ("/health/live", "/health/ready"):
            request = urllib.request.Request(  # noqa: S310 - URL policy is validated above
                base_url + endpoint,
                headers={"User-Agent": "demo-command-center-production-check/1"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                if response.status != 200:
                    raise RuntimeError(f"{endpoint} returned HTTP {response.status}")
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        runner.results.append(
            GateResult("deployed environment smoke", GateStatus.FAIL, type(exc).__name__)
        )
        print(f"[FAIL] deployed environment smoke: {exc}", flush=True)
        return
    runner.results.append(
        GateResult("deployed environment smoke", GateStatus.PASS, "live and ready")
    )
    print("[PASS] deployed environment smoke: live and ready", flush=True)


def _run_load_smoke_gate(runner: GateRunner) -> None:
    configured_url = os.environ.get("PRODUCTION_CHECK_LOAD_BASE_URL", "")
    if not configured_url:
        runner.skip(
            "load smoke",
            "PRODUCTION_CHECK_LOAD_BASE_URL is not configured; no capacity claim is made",
        )
        return
    if not _module_available("locust"):
        runner.skip("load smoke", "locust is not installed in the active Python environment")
        return
    try:
        base_url = _validate_smoke_base_url(configured_url)
    except ValueError as exc:
        runner.results.append(GateResult("load smoke", GateStatus.FAIL, str(exc)))
        print(f"[FAIL] load smoke: {exc}", flush=True)
        return
    runner.run_command(
        "load smoke",
        _module_command(
            "locust",
            "--locustfile",
            str(ROOT / "tests" / "load" / "locustfile.py"),
            "--headless",
            "--host",
            base_url,
            "--users",
            "5",
            "--spawn-rate",
            "5",
            "--run-time",
            "10s",
            "--stop-timeout",
            "5",
            "--only-summary",
            "--exit-code-on-error",
            "1",
        ),
        timeout_seconds=60,
    )


def _summary(results: list[GateResult], *, allow_skips: bool) -> int:
    print("\n=== PRODUCTION CHECK SUMMARY ===")
    for result in results:
        print(f"{result.status:4}  {result.name}: {result.detail}")
    failed = sum(result.status == GateStatus.FAIL for result in results)
    skipped = sum(result.status == GateStatus.SKIP for result in results)
    passed = sum(result.status == GateStatus.PASS for result in results)
    print(f"totals: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        print("overall: FAILED")
        return 1
    if skipped and not allow_skips:
        print("overall: INCOMPLETE (skipped release evidence is not production approval)")
        return 2
    if skipped:
        print("overall: PARTIAL (skips allowed for local evidence; not production approval)")
        return 0
    print("overall: PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run cross-platform production evidence gates without loading .env files."
    )
    parser.add_argument(
        "--allow-skips",
        action="store_true",
        help="Return success when completed gates pass, while still reporting PARTIAL evidence.",
    )
    parser.add_argument(
        "--allow-database-mutation",
        action="store_true",
        help=(
            "Permit upgrade/downgrade only against a loopback test database supplied through "
            "PRODUCTION_CHECK_POSTGRES_URL."
        ),
    )
    arguments = parser.parse_args()

    runner = GateRunner()
    _run_python_gates(runner)
    _run_terraform_gates(runner)
    _run_terraform_policy_gates(runner)
    _run_laravel_adapter_gates(runner)
    _run_container_gate(runner)
    _run_secret_scan_gate(runner)
    _run_postgres_round_trip(
        runner,
        mutation_allowed=arguments.allow_database_mutation,
    )
    _run_load_smoke_gate(runner)
    _run_live_smoke_gate(runner)
    return _summary(runner.results, allow_skips=arguments.allow_skips)


if __name__ == "__main__":
    raise SystemExit(main())
