"""One-off import of voivodeship and powiat boundaries from GUGiK PRG (WFS) into admin_units.

Usage: DATABASE_URL=... python import_prg.py [--tolerance-m 200]
Re-runnable: rows are upserted by TERYT code.
"""

import argparse
import os
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from typing import IO

import httpx
import psycopg

WFS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
LAYERS = {"voivodeship": "A01_Granice_wojewodztw", "powiat": "A02_Granice_powiatow"}
NS = {"ms": "http://mapserver.gis.umn.edu/mapserver"}
USER_AGENT = f"psm-import/0.1 (+{os.environ.get('INGEST_CONTACT', 'unknown')})"

# GML is EPSG:2180 (metres): simplify there, then transform for the map.
# shortcut: per-feature simplification can leave hairline gaps between neighbours; switch to
# a topology-aware approach (e.g. ST_CoverageSimplify) if gaps show up on the map.
UPSERT_SQL = """
    INSERT INTO admin_units (teryt, level, name, geom)
    VALUES (%(teryt)s, %(level)s, %(name)s, ST_Multi(ST_CollectionExtract(ST_MakeValid(
        ST_Transform(ST_SimplifyPreserveTopology(ST_GeomFromGML(%(gml)s), %(tol)s), 4326)
    ), 3)))
    ON CONFLICT (teryt) DO UPDATE SET level = EXCLUDED.level, name = EXCLUDED.name,
        geom = EXCLUDED.geom
"""


def parse_features(source: IO[bytes], layer: str) -> Iterator[dict[str, str]]:
    """Yield teryt/name/gml for each feature of a WFS 2.0 GML response."""
    for _, el in ET.iterparse(source):
        if el.tag == f"{{{NS['ms']}}}{layer}":
            geom = el.find("ms:msGeometry", NS)
            teryt = el.findtext("ms:JPT_KOD_JE", namespaces=NS)
            name = el.findtext("ms:JPT_NAZWA_", namespaces=NS)
            if geom is None or len(geom) == 0 or not teryt or not name:
                raise ValueError(f"incomplete feature in {layer}: teryt={teryt!r}")
            yield {"teryt": teryt, "name": name, "gml": ET.tostring(geom[0], encoding="unicode")}
            el.clear()


def fetch_layer(layer: str, dest: IO[bytes]) -> None:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"ms:{layer}",
    }
    with httpx.stream(
        "GET", WFS_URL, params=params, timeout=600, headers={"User-Agent": USER_AGENT}
    ) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            dest.write(chunk)
    dest.seek(0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tolerance-m", type=float, default=200.0)
    args = parser.parse_args()
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(dsn) as conn:
        for level, layer in LAYERS.items():
            with tempfile.TemporaryFile() as tmp:
                print(f"downloading {layer}…", flush=True)
                fetch_layer(layer, tmp)
                rows = [
                    {**f, "level": level, "tol": args.tolerance_m}
                    for f in parse_features(tmp, layer)
                ]
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, rows)
            print(f"{level}: {len(rows)} units", flush=True)
        # all-or-nothing: psycopg commits on clean exit of the connection block


if __name__ == "__main__":
    main()
