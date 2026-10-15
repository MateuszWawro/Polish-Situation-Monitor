# Polish Situation Monitor

A situational map of Poland built on official open data: weather and hydrological
warnings, river levels, air quality and fire hotspots, shown per powiat and
województwo on one map.

Hobby, non-commercial project. MIT licensed. No ads, ever.

> **Status:** early skeleton. The service layout, compose stack and CI are in place;
> data ingestion, the database schema and the map are not built yet.

## Data sources

| Source | Data | Status |
| --- | --- | --- |
| [IMGW-PIB](https://danepubliczne.imgw.pl/) | meteorological warnings, hydrological warnings, water levels | planned |
| [GIOŚ](https://powietrze.gios.gov.pl/) | air quality index per station | planned |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | VIIRS fire hotspots | planned, needs a free `MAP_KEY` |
| [GUGiK PRG](https://www.geoportal.gov.pl/) | administrative boundaries (powiaty, województwa) | planned |

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
| `ingest/` | Scheduler with one job per source; a failing source never affects the others | Python 3.12, APScheduler |
| `api/` | Read API serving normalised events | FastAPI, SQLAlchemy 2, GeoAlchemy2, Redis cache |
| `web/` | Map frontend; talks only to `api/`, never to data sources | SvelteKit (adapter-static), MapLibre, TypeScript |
| `deploy/` | Docker Compose stack | PostgreSQL 18 + PostGIS 3.6, Redis 7.4, Caddy |
| `docs/` | Source facts, decisions, ADRs | |

## Running locally

Requires Docker with Compose v2.

```sh
cp .env.example .env          # fill in values; FIRMS_MAP_KEY is optional for now
docker compose -f deploy/docker-compose.yml up --build
```

| Service | URL |
| --- | --- |
| web | http://127.0.0.1:8080 |
| api | http://127.0.0.1:8000 (health: `/health`) |
| PostgreSQL | `127.0.0.1:5432` |

All ports are bound to localhost only. Every environment variable is listed in
[`.env.example`](.env.example); secrets never go into the repository.

## Development

Python (`api/`, `ingest/`):

```sh
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
ruff check . && ruff format --check . && mypy . && pytest
```

Web (`web/`, needs npm ≥ 11; npm 10.9 crashes resolving this tree):

```sh
npx npm@11 ci
npm run lint && npm run check && npm test && npm run build
```

CI (GitLab) runs the same lint and test steps, builds all three images and scans
them with Trivy (fails on fixable HIGH/CRITICAL).

### Conventions

- The stack is fixed; a new dependency needs an ADR in `docs/adr/`.
- Pinned image tags and package versions; containers run as non-root (uid 10001).
- Small conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `ci:`.
- Code, names, comments and commits in English.

## Attribution

Required by the data licences and shown on the site:

- Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy.
  Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone.
- Źródło: GIOŚ, portal Jakość Powietrza.
- Fire data: NASA FIRMS (LANCE).
- Administrative boundaries: GUGiK, Państwowy Rejestr Granic.

The IMGW terms treat websites with advertising as commercial use, which is why
this project will never carry ads.

## License

[MIT](LICENSE)
