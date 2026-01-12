FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy the package metadata
COPY pyproject.toml README.md ./

# Copy the source code
COPY src ./src

# Install dependencies using uv pip for standalone builds
RUN uv pip install --system --no-cache .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "src/main.py"]
