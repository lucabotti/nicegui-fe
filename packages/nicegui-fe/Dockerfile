FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy the entire workspace configuration
# We need the root pyproject.toml and uv.lock to sync correctly
COPY pyproject.toml uv.lock ./
COPY packages/nicegui-fe/pyproject.toml ./packages/nicegui-fe/

# Sync dependencies for this package
RUN uv sync --frozen --no-cache --package nicegui-fe

# Copy the source code
COPY packages/nicegui-fe/src ./packages/nicegui-fe/src

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["uv", "run", "--package", "nicegui-fe", "python", "packages/nicegui-fe/src/main.py"]
