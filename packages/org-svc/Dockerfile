FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

COPY start.sh ./
RUN chmod +x start.sh

RUN uv pip install --system --no-cache .

ENV PYTHONUNBUFFERED=1
ENV PORT=8001
ENV DATABASE_URL=postgresql://keycloak:password@db:5432/contacts

CMD ["./start.sh"]
