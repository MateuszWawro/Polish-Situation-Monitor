import io

import pytest

from import_prg import parse_features

GML = b"""<?xml version="1.0"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:ms="http://mapserver.gis.umn.edu/mapserver" xmlns:gml="http://www.opengis.net/gml/3.2">
  <wfs:member><ms:A02_Granice_powiatow>
    <ms:msGeometry><gml:Polygon srsName="urn:ogc:def:crs:EPSG::2180"><gml:exterior><gml:LinearRing>
      <gml:posList>0 0 0 1 1 1 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>
    </ms:msGeometry>
    <ms:JPT_KOD_JE>1416</ms:JPT_KOD_JE><ms:JPT_NAZWA_>powiat ostrowski</ms:JPT_NAZWA_>
  </ms:A02_Granice_powiatow></wfs:member>
</wfs:FeatureCollection>"""


def test_parse_features() -> None:
    [f] = parse_features(io.BytesIO(GML), "A02_Granice_powiatow")
    assert f["teryt"] == "1416"
    assert f["name"] == "powiat ostrowski"
    assert f["gml"].startswith("<gml:Polygon") or "Polygon" in f["gml"]


def test_parse_rejects_feature_without_teryt() -> None:
    broken = GML.replace(b"<ms:JPT_KOD_JE>1416</ms:JPT_KOD_JE>", b"")
    with pytest.raises(ValueError):
        list(parse_features(io.BytesIO(broken), "A02_Granice_powiatow"))


def test_parse_names() -> None:
    from build_places_index import parse_names

    gml = b"""<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
        xmlns:ms="http://mapserver.gis.umn.edu/mapserver">
      <wfs:member><ms:A03_Granice_gmin><ms:JPT_KOD_JE>1861011</ms:JPT_KOD_JE>
        <ms:JPT_NAZWA_>Krosno</ms:JPT_NAZWA_></ms:A03_Granice_gmin></wfs:member>
    </wfs:FeatureCollection>"""
    assert parse_names(gml, "A03_Granice_gmin") == [("1861011", "Krosno")]
