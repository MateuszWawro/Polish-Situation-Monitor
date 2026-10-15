FROM python:3.12.15-slim-bookworm
WORKDIR /app
COPY pyproject.toml .
COPY ingest ingest
RUN pip install --no-cache-dir . && useradd --system --uid 10001 app
USER app
CMD ["python", "-m", "ingest.main"]
