"""Build the national outline for the web map from the imported PRG boundaries.

Usage: DATABASE_URL=... python build_poland_outline.py ../web/static/poland.geojson
Output: a GeoJSON geometry (MultiPolygon, WGS84) = union of all voivodeships, simplified.
The map uses it to dim everything outside Poland and to draw the border.
Re-run when PRG changes (roughly yearly), after import_prg.py.
"""

import os
import sys

import psycopg

# ~700 m: smooth enough for a country-wide border, a few KB gzipped.
TOLERANCE_DEG = 0.007
# ±0.003° (~300 m): close/open buffer dissolves the hairline gaps left between
# separately simplified voivodeships, which would otherwise be hundreds of sliver holes.
BUFFER_DEG = 0.003

SQL = """
    SELECT ST_AsGeoJSON(
        ST_SimplifyPreserveTopology(
            ST_Buffer(ST_Buffer(ST_Union(geom), %(buf)s), -%(buf)s),
            %(tol)s
        ), 5
    )
    FROM admin_units WHERE level = 'voivodeship'
"""


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "../web/static/poland.geojson"
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        geojson = conn.execute(SQL, {"tol": TOLERANCE_DEG, "buf": BUFFER_DEG}).fetchone()
    if not geojson or not geojson[0]:
        raise SystemExit("no voivodeships in admin_units – run import_prg.py first")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(geojson[0])
    print(f"wrote {out} ({len(geojson[0]) // 1024} KB)")


if __name__ == "__main__":
    main()
