# Polish Situation Monitor – project conventions

Hobby, non-commercial, MIT. Situational map of Poland built on official open data.
Talk to the owner in Polish; code, names, comments and commits in English.

## Layout
- `ingest/` – Python 3.12, APScheduler, one job per source (a failing source must not affect others)
- `api/` – FastAPI (SQLAlchemy 2 + GeoAlchemy2, Redis cache)
- `web/` – SvelteKit + adapter-static, MapLibre, TypeScript. Never calls data sources directly.
- `db/` – Alembic migrations, PRG boundary import
- `deploy/` – docker-compose files, Caddyfile
- `docs/` – SOURCES.md (source facts + decisions), ARCHITECTURE.md, `adr/`

## Rules
- Stack is fixed; new dependencies need an ADR in `docs/adr/`.
- Secrets only in env / CI variables. `.env.example` lists every variable.
- Pinned image tags and package versions; containers run as non-root (uid 10001).
- Small conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`).
- Ask the owner when something needs a decision. Server commands run as root: no `sudo`.
- No ads on the site, ever (IMGW terms treat ad-bearing sites as commercial use).

## Commands
- Python (`api/`, `ingest/`, `db/`): `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`,
  then `ruff check . && ruff format --check . && mypy . && pytest`
- Web: `npm ci && npm run lint && npm run check && npm test && npm run build`
  (npm 10.9 crashes resolving this tree – use npm ≥ 11, e.g. `npx npm@11 install`)
- Stack: `cp .env.example .env && docker compose -f deploy/docker-compose.yml up --build`

- Migrations: `cd db && DATABASE_URL=... alembic upgrade head` (hand-written SQL, no autogenerate)
- Boundaries: `cd db && DATABASE_URL=... python import_prg.py` (~1 min, re-runnable)
- DB-backed API tests run only when `DATABASE_URL` is set (skipped in CI for now)

## Gotchas
- Repo lives on exFAT: macOS creates `._*` files. They are git/prettier/docker-ignored; delete before tooling if something chokes
  (Alembic crashes on `._*.py` in `db/migrations/versions`).
