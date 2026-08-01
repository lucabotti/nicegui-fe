FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy the package metadata
COPY pyproject.toml README.md ./

# Copy the source code
COPY src ./src

# Install dependencies using uv pip for standalone builds
# Using --system to install into the image's python environment
RUN uv pip install --system --no-cache .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application directly with python
# Standardizing on the relative path from /app
CMD ["python", "src/htmx_fe/main.py"]
