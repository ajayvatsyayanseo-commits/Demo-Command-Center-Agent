.PHONY: install format lint type test contracts migration check run doctor

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

migration:
	uv run alembic history
	uv run alembic heads
	uv run alembic upgrade head --sql > /dev/null

check: lint type contracts migration test

run:
	uv run uvicorn demo_command_center.main:app --app-dir src --reload

doctor:
	uv run demo-command-doctor
