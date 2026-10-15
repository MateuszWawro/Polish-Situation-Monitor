# ADR 0001: psycopg 3 as the PostgreSQL driver

- Status: accepted (2026-10-15)

## Context
SQLAlchemy (API), Alembic (migrations) and the ingest workers need a PostgreSQL driver.
The stack does not name one.

## Decision
Use `psycopg[binary]` 3 everywhere. Ingest and the PRG import use it directly
(plain SQL, PostGIS does the geometry work); API and Alembic use it via SQLAlchemy
(`postgresql+psycopg://`).

## Consequences
One driver, no ORM models in ingest. `pydantic` and `httpx` (ingest) and `respx`
(tests) come from the agreed stack and need no ADR.
