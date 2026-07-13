from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowLoader(yaml.SafeLoader):
    """YAML 1.2-like loader that does not coerce the GitHub key `on` to bool."""


for first_character, resolvers in list(WorkflowLoader.yaml_implicit_resolvers.items()):
    WorkflowLoader.yaml_implicit_resolvers[first_character] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]


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


def main() -> None:
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    if not workflow_paths:
        raise ValueError("no GitHub workflows found")
    for path in workflow_paths:
        document = _load(path)
        missing = {"name", "on", "jobs"}.difference(document)
        if missing:
            raise ValueError(f"workflow missing {sorted(missing)}: {path}")
        if not isinstance(document["jobs"], dict) or not document["jobs"]:
            raise ValueError(f"workflow jobs must be a non-empty object: {path}")

    action_paths = sorted((ROOT / ".github" / "actions").glob("*/action.yml"))
    for path in action_paths:
        document = _load(path)
        missing = {"name", "runs"}.difference(document)
        if missing:
            raise ValueError(f"action missing {sorted(missing)}: {path}")
        runs = document["runs"]
        if not isinstance(runs, dict) or runs.get("using") != "composite":
            raise ValueError(f"only composite actions are expected: {path}")
    print(f"workflows: valid ({len(workflow_paths)} workflows, {len(action_paths)} actions)")


if __name__ == "__main__":
    main()
