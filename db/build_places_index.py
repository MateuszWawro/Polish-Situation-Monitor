"""Build the offline place-search index for the web app from GUGiK PRG (names only, no geometry).

Usage: python build_places_index.py ../web/static/places-index.json
Output: {"voivodeships": {"02": name}, "powiaty": {"0201": name}, "gminy": [[name, "0201011"], ...]}
A gmina's 7-digit TERYT starts with its powiat code; the last digit is the gmina type
(1 urban, 2 rural, 3 urban-rural). Re-run when PRG changes (roughly yearly).
"""

import json
import sys
import xml.etree.ElementTree as ET

import httpx

from import_prg import NS, USER_AGENT, WFS_URL

LAYERS = {
    "voivodeships": "A01_Granice_wojewodztw",
    "powiaty": "A02_Granice_powiatow",
    "gminy": "A03_Granice_gmin",
}


def fetch_names(layer: str) -> list[tuple[str, str]]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"ms:{layer}",
        "propertyName": "JPT_KOD_JE,JPT_NAZWA_",  # skip geometry: ~0.5 MB instead of ~60 MB
    }
    r = httpx.get(WFS_URL, params=params, timeout=300, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return parse_names(r.content, layer)


def parse_names(content: bytes, layer: str) -> list[tuple[str, str]]:
    rows = []
    for el in ET.fromstring(content).iter(f"{{{NS['ms']}}}{layer}"):
        code = el.findtext("ms:JPT_KOD_JE", namespaces=NS)
        name = el.findtext("ms:JPT_NAZWA_", namespaces=NS)
        if not code or not name:
            raise ValueError(f"incomplete feature in {layer}: {code!r} {name!r}")
        rows.append((code, name))
    return rows


def main() -> None:
    out = sys.argv[1]
    names = {key: fetch_names(layer) for key, layer in LAYERS.items()}
    index = {
        "voivodeships": dict(sorted(names["voivodeships"])),
        "powiaty": dict(sorted(names["powiaty"])),
        "gminy": sorted([name, code] for code, name in names["gminy"]),
    }
    if len(index["voivodeships"]) != 16 or len(index["powiaty"]) < 370:
        raise SystemExit(f"suspicious PRG response: {[len(v) for v in index.values()]}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print({k: len(v) for k, v in index.items()})


if __name__ == "__main__":
    main()
