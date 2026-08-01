# Default to showing help
default:
    @just --list

# Install pre-commit hooks
install-hooks:
    uv run pre-commit install

# Run tests
test:
    uv run --package nicegui-fe pytest packages/nicegui-fe/tests
    uv run --package fastapi-svc pytest packages/fastapi-svc/tests

# Lint and format code
lint:
    uv run ruff check . --fix
    uv run ruff format .

# Type checking
type:
    uv run ty check

# Run frontend
run:
    uv run --package nicegui-fe python packages/nicegui-fe/src/main.py

# Run the backend service
run-service:
    uv run --package fastapi-svc python packages/fastapi-svc/src/main.py
