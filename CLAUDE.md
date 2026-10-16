# Polish Situation Monitor – project conventions

Hobby, non-commercial, MIT. Situational map of Poland built on official open data (one agreed exception: adsb.lol for
aircraft and the GPS interference estimate, see docs/SOURCES.md §9–10).
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
- Privacy: the user's location and place names never leave the device (powiat lookup and
  places storage are client-side, see ADR 0002). The server only ever sees powiat codes.

## Commands
- Python (`api/`, `ingest/`, `db/`): `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`,
  then `ruff check . && ruff format --check . && mypy . && pytest`
- Web: `npm ci && npm run lint && npm run check && npm test && npm run build`
  (npm 10.9 crashes resolving this tree – use npm ≥ 11, e.g. `npx npm@11 install`)
- Stack: `cp .env.example .env && docker compose -f deploy/docker-compose.yml up --build`

- Migrations: `cd db && DATABASE_URL=... alembic upgrade head` (hand-written SQL, no autogenerate)
- Boundaries: `cd db && DATABASE_URL=... python import_prg.py` (~1 min, re-runnable)
- Place search index: `cd db && python build_places_index.py ../web/static/places-index.json` (re-run when PRG changes)
- DB-backed tests (api, ingest) run only when `TEST_DATABASE_URL` is set and never touch
  `DATABASE_URL`. The session fixture (`db/testdb.py`) runs Alembic and wipes every table, then
  loads a few box-shaped admin_units (no PRG import). Create the DB once:
  `createdb -h localhost -p 5433 -U psm psm_test`, then
  `TEST_DATABASE_URL=postgresql+psycopg://psm@localhost:5433/psm_test pytest`. CI uses a postgis service.

## Web routing
- Static build (adapter-static). Dynamic pages (`/e/{id}`) are not prerendered: the server
  must fall back to `200.html` for unknown paths (Caddy: `try_files {path} {path}.html /200.html`).
- Map state lives in the URL (`?l=&min=&c=&z=&e=`, see `web/src/lib/mapUrl.ts`).
- Service worker (`web/src/service-worker/`): app shell cache-first, selected `/api/*` network-first
  with the last good answer kept (marked `x-psm-cached-at` → "Offline" banner). OSM tiles are not
  cached. Serve `service-worker.js` with `Cache-Control: no-cache` in prod so updates roll out.
  It only runs in production builds – test with `npm run build && npm run preview`.

## Gotchas
- Repo lives on exFAT: macOS creates `._*` files. They are git/prettier/docker-ignored; delete before tooling if something chokes
  (Alembic crashes on `._*.py` in `db/migrations/versions`).
