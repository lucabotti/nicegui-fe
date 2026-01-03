FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy the entire workspace configuration
COPY pyproject.toml uv.lock ./
COPY packages/fastapi-svc/pyproject.toml ./packages/fastapi-svc/

# Sync dependencies for this package
RUN uv sync --frozen --no-cache --package fastapi-svc

# Copy the source code
COPY packages/fastapi-svc/src ./packages/fastapi-svc/src

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["uv", "run", "--package", "fastapi-svc", "python", "packages/fastapi-svc/src/main.py"]
