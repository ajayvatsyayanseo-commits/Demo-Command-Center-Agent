.PHONY: install format lint type test contracts hygiene migration check production-check production-check-local run doctor

install:
	uv sync --frozen --all-extras

format:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

lint:
	uv run ruff format --check src tests scripts
	uv run ruff check src tests scripts

type:
	uv run mypy src tests

test:
	uv run pytest --cov=demo_command_center --cov-report=term-missing

contracts:
	uv run python scripts/validate_contracts.py
	uv run python scripts/validate_workflows.py

hygiene:
	uv run python scripts/validate_production_hygiene.py

migration:
	uv run python scripts/validate_migrations.py

check: lint type contracts hygiene migration test

# A skipped release gate is an incomplete production check and exits with code 2.
production-check:
	uv run python scripts/production_check.py

# Developer convenience only. The report remains PARTIAL when tools/evidence are absent.
production-check-local:
	uv run python scripts/production_check.py --allow-skips

run:
	uv run uvicorn demo_command_center.main:app --app-dir src --reload

doctor:
	uv run demo-command-doctor
