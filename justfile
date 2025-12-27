# Default to showing help
default:
    @just --list

# Install pre-commit hooks
install-hooks:
    uv run pre-commit install

# Run tests
test:
    uv run pytest

# Lint and format code
lint:
    uv run ruff check . --fix
    uv run ruff format .

# Type checking
type:
    uv run ty check

# Run in development mode with auto-reload
run:
    uv run python src/main.py
