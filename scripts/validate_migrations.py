from __future__ import annotations

import argparse
import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def _config(*, output_buffer: io.StringIO | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("prepend_sys_path", str(ROOT / "src"))
    return config


@contextmanager
def _isolated_working_directory() -> Iterator[None]:
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="dcc-migration-check-") as temporary_directory:
        os.chdir(temporary_directory)
        try:
            yield
        finally:
            os.chdir(original)


def validate_offline() -> None:
    upgrade_output = io.StringIO()
    config = _config(output_buffer=upgrade_output)
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise ValueError(f"migration graph must have exactly one head; found {heads!r}")

    revisions = list(script.walk_revisions(base="base", head="heads"))
    if not revisions:
        raise ValueError("migration graph contains no revisions")
    revision_ids = [revision.revision for revision in revisions]
    if len(revision_ids) != len(set(revision_ids)):
        raise ValueError("migration graph contains duplicate revision identifiers")

    with _isolated_working_directory():
        command.upgrade(config, "head", sql=True)
    upgrade_sql = upgrade_output.getvalue()
    if not upgrade_sql.strip():
        raise ValueError("offline migration rendering produced no SQL")
    missing_revisions = [revision for revision in revision_ids if revision not in upgrade_sql]
    if missing_revisions:
        raise ValueError(
            "offline migration rendering omitted revisions: " + ", ".join(missing_revisions)
        )

    downgrade_output = io.StringIO()
    downgrade_config = _config(output_buffer=downgrade_output)
    with _isolated_working_directory():
        command.downgrade(downgrade_config, "heads:base", sql=True)
    downgrade_sql = downgrade_output.getvalue()
    if not downgrade_sql.strip():
        raise ValueError("offline downgrade rendering produced no SQL")
    missing_downgrades = [revision for revision in revision_ids if revision not in downgrade_sql]
    if missing_downgrades:
        raise ValueError(
            "offline downgrade rendering omitted revisions: " + ", ".join(missing_downgrades)
        )

    print(
        "migrations: valid "
        f"({len(revisions)} revisions, head={heads[0]}, "
        f"upgrade_sql_bytes={len(upgrade_sql)}, downgrade_sql_bytes={len(downgrade_sql)})"
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


def run_round_trip() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not _safe_local_test_database(database_url):
        raise ValueError("DATABASE_URL must target a loopback PostgreSQL test/check/ci database")
    with _isolated_working_directory():
        command.upgrade(_config(), "head")
        command.downgrade(_config(), "base")
        command.upgrade(_config(), "head")
    print("migrations: PostgreSQL upgrade/downgrade/upgrade round-trip valid")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Alembic migration graph.")
    parser.add_argument(
        "--round-trip",
        action="store_true",
        help="Mutate only the loopback test database supplied in DATABASE_URL.",
    )
    arguments = parser.parse_args()
    if arguments.round_trip:
        run_round_trip()
    else:
        validate_offline()


if __name__ == "__main__":
    main()
