# ADR 0002: "Moja okolica" without new dependencies

- Status: accepted (2026-10-15)

## Context
"Moja okolica" needs place search, "use my location" → powiat lookup on the device
(GPS never leaves the device), and local storage of up to 5 places. The Phase 2 brief
suggests e.g. `@turf/boolean-point-in-polygon` and IndexedDB.

## Decision
- **Point-in-polygon:** own ray-casting function (`web/src/lib/geo.ts`, ~30 lines, unit
  tested incl. holes and multipolygons) against `/api/admin-units?level=powiat`. A Turf
  package would add a dependency for the same few lines.
- **Storage:** native IndexedDB API through a tiny wrapper (`web/src/lib/places.ts`), no
  `idb`/`localforage`. Five small records do not need a library.
- **Search:** offline index `web/static/places-index.json` (16 voivodeships, 380 powiaty,
  2479 gminy; ~22 KB gzip) built from PRG by `db/build_places_index.py`. No external geocoder.

## Consequences
No new runtime dependencies. The index must be rebuilt when PRG changes (roughly yearly).
Powiat boundaries are simplified (~200 m), so a location within ~200 m of a powiat border
can resolve to the neighbouring powiat; the user sees the result and can pick manually.
