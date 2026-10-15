# Polish Situation Monitor

A situational map of Poland built on official open data: weather and hydrological
warnings, river levels, air quality, satellite fire hotspots and road incidents,
shown per powiat and województwo on one map.

Hobby, non-commercial project. MIT licensed. No ads, ever.

## Features

- **Map** with toggleable layers, a severity filter (0–3), place search and
  shareable links that keep the view, layers and the open event in the URL.
- **Moja okolica** – up to 5 saved places with their active warnings. Places and
  the "use my location" lookup stay on the device; the position is never sent.
- **Event pages** (`/e/<id>`), including a 72-hour water level chart for gauges
  above the warning level.
- **Source status** (`/status`) with last successful fetch and 7-day availability.
- **Offline fallback** – a service worker shows the last loaded state.

## Data sources

| Source | Data | Refresh |
| --- | --- | --- |
| [IMGW-PIB](https://danepubliczne.imgw.pl/) | meteorological and hydrological warnings, water levels | every 10 min |
| [GIOŚ](https://powietrze.gios.gov.pl/) | air quality index per station | every 30 min |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | VIIRS fire hotspots (NOAA-20, NOAA-21), public CSV, no key | every 30 min |
| [GDDKiA](https://dane.gov.pl/pl/dataset/2752) | incidents and roadworks on national roads (CC0) | every 15 min |
| [GUGiK PRG](https://www.geoportal.gov.pl/) | voivodeship and powiat boundaries | one-off import |

Endpoints, limits, licences and mapping decisions are documented in
[`docs/SOURCES.md`](docs/SOURCES.md).

## Architecture

```
data sources ──► ingest ──► PostgreSQL + PostGIS ──► api ──► web (static, MapLibre)
                                                      │
                                                    Redis
```

| Directory | What | Stack |
| --- | --- | --- |
| `ingest/` | Scheduler with one job per source; a failing source never affects the others | Python 3.12, APScheduler, psycopg 3 |
| `api/` | Read API serving normalised events as GeoJSON | FastAPI, SQLAlchemy 2, GeoAlchemy2, Redis cache |
| `db/` | Alembic migrations, PRG boundary import, offline place index builder | Alembic, psycopg 3 |
| `web/` | Map frontend; talks only to `api/`, never to data sources | SvelteKit (adapter-static), MapLibre, TypeScript |
| `deploy/` | Docker Compose stack | PostgreSQL 18 + PostGIS 3.6, Redis 7.4, Caddy |
| `docs/` | Source facts and decisions ([`SOURCES.md`](docs/SOURCES.md)), [ADRs](docs/adr/) | |

## Running locally

Requires Docker with Compose v2.

```sh
cp .env.example .env          # set a password and INGEST_CONTACT
docker compose -f deploy/docker-compose.yml up --build
# once, after the first start: import administrative boundaries from PRG
docker compose -f deploy/docker-compose.yml run --rm migrate python import_prg.py
```

The `migrate` service applies database migrations on every start; `api` and
`ingest` wait for it.

| Service | URL |
| --- | --- |
| web | http://127.0.0.1:8080 |
| api | http://127.0.0.1:8000 (health: `/health`) |
| PostgreSQL | `127.0.0.1:5432` |

All ports are bound to localhost only. Every environment variable is listed in
[`.env.example`](.env.example); secrets never go into the repository.

## Development

Python (`api/`, `ingest/`, `db/`):

```sh
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
ruff check . && ruff format --check . && mypy . && pytest
```

Web (`web/`, needs npm ≥ 11; npm 10.9 crashes resolving this tree):

```sh
npx npm@11 ci
npm run lint && npm run check && npm test && npm run build
```

CI (GitLab) runs the same lint and test steps, builds all four images and scans
them with Trivy (fails on fixable HIGH/CRITICAL).

### Conventions

- The stack is fixed; a new dependency needs an ADR in `docs/adr/`.
- Pinned image tags and package versions; containers run as non-root (uid 10001).
- Small conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `ci:`.
- Code, names, comments and commits in English.

## Attribution

Required by the data licences; the site shows the full text and licence links on
`/zrodla`:

- Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy.
  Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone.
- Źródło: Główny Inspektorat Ochrony Środowiska, portal „Jakość Powietrza”.
- NASA FIRMS (NASA LANCE, ESDIS).
- Źródło: Generalna Dyrekcja Dróg Krajowych i Autostrad.
- Źródło: Główny Urząd Geodezji i Kartografii, PRG.
- Basemap: © OpenStreetMap contributors (ODbL).

The IMGW terms treat websites with advertising as commercial use, which is why
this project will never carry ads.

## License

[MIT](LICENSE)
