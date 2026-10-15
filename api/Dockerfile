FROM python:3.12.15-slim-bookworm
WORKDIR /app
COPY pyproject.toml .
COPY app app
RUN pip install --no-cache-dir . && useradd --system --uid 10001 app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
