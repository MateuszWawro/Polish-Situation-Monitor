FROM python:3.12.15-slim-bookworm
WORKDIR /app
COPY pyproject.toml .
COPY alembic.ini import_prg.py ./
COPY migrations migrations
RUN pip install --no-cache-dir . && useradd --system --uid 10001 app
USER app
CMD ["alembic", "upgrade", "head"]
