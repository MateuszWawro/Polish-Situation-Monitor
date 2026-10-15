# ADR 0003: satellite.js for orbit propagation

- Status: accepted (2026-10-15)

## Context
The satellite layer shows which satellites are over Poland in real time. Positions must be
computed in the browser: satellites in low Earth orbit move ~7.5 km/s and cross Poland in
1–2 minutes, so server-side snapshots would be stale between fetches and jump hundreds of
kilometres. The standard algorithm is SGP4, propagating from TLE (two-line element) data.

The stack is fixed and new dependencies need an ADR. ADR 0002 favours small own code over a
dependency, but SGP4 is several hundred lines of non-trivial orbital mechanics; a hand-rolled
version would be error-prone and a maintenance burden, unlike the ~30-line point-in-polygon
there.

## Decision
Add **`satellite.js`** (pinned `6.0.1`) to `web`. MIT-licensed, TypeScript types, no runtime
dependencies, ~14 KB gzipped. It implements SGP4/SDP4 and the TLE parsing and coordinate
transforms we need (ECI → geodetic sub-point).

TLE data comes from **CelesTrak** (`gp.php`, keyless, see docs/SOURCES.md §11). The ingest
worker fetches it no more than CelesTrak's 2-hour update cycle allows; the browser propagates
from the stored TLE every second.

## Consequences
One new web dependency. TLE stays accurate for days, so a few-hour fetch interval is fine.
The layer shows sub-satellite points (ground track position), not a view from orbit.
