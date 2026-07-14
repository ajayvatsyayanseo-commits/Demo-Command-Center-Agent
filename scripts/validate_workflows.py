from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MUTABLE_ACTION_REFS = {"main", "master", "latest"}


class WorkflowLoader(yaml.SafeLoader):
    """YAML 1.2-like loader that does not coerce the GitHub key `on` to bool."""


for first_character, resolvers in list(WorkflowLoader.yaml_implicit_resolvers.items()):
    WorkflowLoader.yaml_implicit_resolvers[first_character] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        loader = WorkflowLoader(handle)
        try:
            document = loader.get_single_data()
        finally:
            loader.dispose()
    if not isinstance(document, dict):
        raise ValueError(f"workflow must be an object: {path}")
    return document


def _validate_action_reference(reference: object, *, path: Path) -> None:
    if not isinstance(reference, str) or not reference:
        raise ValueError(f"workflow step has an invalid uses value: {path}")
    if reference.startswith("./"):
        action_path = ROOT / reference
        if action_path.is_file() and action_path.suffix in {".yaml", ".yml"}:
            return
        if (
            not (action_path / "action.yml").is_file()
            and not (action_path / "action.yaml").is_file()
        ):
            raise ValueError(f"local workflow action does not exist: {path}: {reference}")
        return
    if reference.startswith("docker://"):
        if "@sha256:" not in reference:
            raise ValueError(f"container action must use an immutable digest: {path}: {reference}")
        return
    if "@" not in reference:
        raise ValueError(f"external action must include a version: {path}: {reference}")
    version = reference.rsplit("@", maxsplit=1)[1]
    if version.casefold() in MUTABLE_ACTION_REFS:
        raise ValueError(f"external action uses a mutable branch: {path}: {reference}")


def _trigger_names(value: object, *, path: Path) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    if isinstance(value, dict):
        return set(value)
    raise ValueError(f"workflow triggers must be a string, list, or object: {path}")


def _validate_workflow(path: Path, document: dict[str, Any]) -> int:
    missing = {"name", "on", "jobs"}.difference(document)
    if missing:
        raise ValueError(f"workflow missing {sorted(missing)}: {path}")
    permissions = document.get("permissions")
    if not isinstance(permissions, dict) or not permissions:
        raise ValueError(f"workflow must declare least-privilege permissions: {path}")
    if "write-all" in permissions or "read-all" in permissions:
        raise ValueError(f"workflow uses a broad permission preset: {path}")
    if "pull_request_target" in _trigger_names(document["on"], path=path):
        raise ValueError(f"pull_request_target is prohibited: {path}")

    jobs = document["jobs"]
    if not isinstance(jobs, dict) or not jobs:
        raise ValueError(f"workflow jobs must be a non-empty object: {path}")
    step_count = 0
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            raise ValueError(f"workflow job must be an object: {path}: {job_name}")
        if "uses" in job:
            _validate_action_reference(job["uses"], path=path)
            continue
        if not job.get("runs-on"):
            raise ValueError(f"workflow job is missing runs-on: {path}: {job_name}")
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"workflow job has no steps: {path}: {job_name}")
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError(f"workflow step must be an object: {path}: {job_name}")
            if "uses" not in step and "run" not in step:
                raise ValueError(f"workflow step has neither uses nor run: {path}: {job_name}")
            if "uses" in step:
                _validate_action_reference(step["uses"], path=path)
            run = step.get("run")
            if isinstance(run, str) and "${{ secrets." in run:
                raise ValueError(
                    "secret must be passed through a step environment, "
                    f"not interpolated in run: {path}"
                )
            step_count += 1
    return step_count


def _validate_release_workflows(workflows: dict[str, dict[str, Any]]) -> None:
    for filename in ("deploy-staging.yml", "deploy-prod.yml", "rollback.yml"):
        document = workflows.get(filename)
        if document is None:
            raise ValueError(f"required release workflow is missing: {filename}")
        triggers = document["on"]
        if not isinstance(triggers, dict) or _trigger_names(triggers, path=Path(filename)) != {
            "workflow_dispatch"
        }:
            raise ValueError(f"protected release workflow must be manual-only: {filename}")
        run_commands = "\n".join(
            str(step.get("run", ""))
            for job in document["jobs"].values()
            for step in job.get("steps", [])
            if isinstance(job, dict) and isinstance(step, dict)
        )
        if "@sha256:" not in run_commands:
            raise ValueError(f"release workflow does not enforce an immutable digest: {filename}")
        for job in document["jobs"].values():
            if (
                not isinstance(job, dict)
                or not job.get("environment")
                or not job.get("concurrency")
            ):
                raise ValueError(
                    f"release job must declare a protected environment and concurrency: {filename}"
                )
        dispatch = triggers["workflow_dispatch"]
        inputs = dispatch.get("inputs", {}) if isinstance(dispatch, dict) else {}
        image_input = inputs.get("image_uri") if isinstance(inputs, dict) else None
        if not isinstance(image_input, dict) or image_input.get("required") is not True:
            raise ValueError(f"release workflow must require image_uri: {filename}")
    rollback = workflows["rollback.yml"]
    rollback_inputs = rollback["on"]["workflow_dispatch"].get("inputs", {})
    if "incident_reference" not in rollback_inputs:
        raise ValueError("rollback workflow must require an incident/change reference")


def main() -> None:
    workflow_root = ROOT / ".github" / "workflows"
    workflow_paths = sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])
    if not workflow_paths:
        raise ValueError("no GitHub workflows found")
    workflows: dict[str, dict[str, Any]] = {}
    workflow_names: set[str] = set()
    step_count = 0
    for path in workflow_paths:
        document = _load(path)
        name = document.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"workflow name must be a non-empty string: {path}")
        if name in workflow_names:
            raise ValueError(f"duplicate workflow name {name!r}: {path}")
        workflow_names.add(name)
        workflows[path.name] = document
        step_count += _validate_workflow(path, document)

    _validate_release_workflows(workflows)

    action_root = ROOT / ".github" / "actions"
    action_paths = sorted([*action_root.glob("*/action.yml"), *action_root.glob("*/action.yaml")])
    for path in action_paths:
        document = _load(path)
        missing = {"name", "runs"}.difference(document)
        if missing:
            raise ValueError(f"action missing {sorted(missing)}: {path}")
        runs = document["runs"]
        if not isinstance(runs, dict) or runs.get("using") != "composite":
            raise ValueError(f"only composite actions are expected: {path}")
        steps = runs.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"composite action must define steps: {path}")
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError(f"composite action step must be an object: {path}")
            if "uses" in step:
                _validate_action_reference(step["uses"], path=path)
    print(
        "workflows: valid "
        f"({len(workflow_paths)} workflows, {len(action_paths)} actions, {step_count} job steps)"
    )


if __name__ == "__main__":
    main()
