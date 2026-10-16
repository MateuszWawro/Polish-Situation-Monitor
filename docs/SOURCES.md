# Data sources (Phase 1)

Verified with real requests on **2026-10-15**. Status legend: ✅ verified · ⚠️ works but needs a decision · ❓ not verified.

---

## 1. IMGW-PIB – meteorological warnings ✅

- **Endpoint:** `GET https://danepubliczne.imgw.pl/api/data/warningsmeteo` → `200`, JSON array, `cache-control: no-store`
- **Auth / limits:** no key. No rate-limit headers, no documented limit. Plan: poll every 10 min, send `User-Agent` with contact.
- **Sample record** (2 active warnings at check time):
  ```json
  {"id":"Sk20261015092234170","nazwa_zdarzenia":"Gęsta mgła","stopien":"1","prawdopodobienstwo":"80",
   "obowiazuje_od":"2026-10-15 22:00:00","obowiazuje_do":"2026-10-16 09:00:00","opublikowano":"2026-10-15 11:22:00",
   "tresc":"Prognozuje się gęste mgły…","komentarz":"Brak.","biuro":"Centralne Biuro Prognoz Meteorologicznych w Warszawie",
   "teryt":["1428","2401","2404", "..."]}
  ```
- **Mapping → `events`:** `source_event_id=id`, `type=weather_warning`, `severity=int(stopien)` (1–3, 1:1), `title=nazwa_zdarzenia`, `description=tresc (+komentarz)`, `valid_from/to=obowiazuje_od/do` (local time Europe/Warsaw, no TZ in payload – convert to UTC), `teryt_powiat=teryt` (4-digit powiat codes, **match PRG `JPT_KOD_JE` directly**), `geom=ST_Union` of those powiaty.
- Removed from feed ⇒ warning ended/withdrawn (no explicit cancel flag).

## 2a. IMGW-PIB – hydrological warnings ⚠️

- **Endpoint:** `GET https://danepubliczne.imgw.pl/api/data/warningshydro` → `200`, JSON array (94 records at check time)
- **Sample:**
  ```json
  {"numer":"21","opublikowano":"2026-04-17 08:45:56","stopień":"-1","data_od":"2026-04-17 08:46:51","data_do":"9999-12-31 23:59:59",
   "prawdopodobienstwo":"90","zdarzenie":"Susza hydrologiczna","przebieg":"…","komentarz":"…","biuro":"Biuro Prognoz Hydrologicznych we Wrocławiu…",
   "obszary":[{"wojewodztwo":"łódzkie","opis":"łódzkie, Warta górna z Liswartą, susza hydrologiczna","kod_zlewni":["Z_P_LD_1816","R_P_LD_18_A"]}]}
  ```
- **Problems (need decision):**
  1. **No TERYT, no geometry.** Only `wojewodztwo` name + catchment codes (`kod_zlewni`). I have not found a public geometry layer for these codes.
  2. **No stable ID** – `numer` only; key would be `biuro + numer + opublikowano`?
  3. Field name uses non-ASCII key `stopień`; value `-1` = drought (all 94 current records are droughts). Floods presumably 1–3.
  4. `data_do = 9999-12-31` = open-ended.
- **Proposed mapping:** `type=hydro_warning`, severity `1–3` as-is, drought (`-1`) → `severity=1` with subtype in `raw`; geom/TERYT = whole województwo(s) from `obszary[].wojewodztwo` (coarse).

## 2b. IMGW-PIB – water levels at stations ⚠️

- **Endpoint:** `GET https://danepubliczne.imgw.pl/api/data/hydro` → `200`, 913 stations, all with lat/lon. (`/api/data/hydro2` returns HTML – not used.)
- **Sample:** `{"id_stacji":"151140030","stacja":"Przewoźniki","rzeka":"Skroda","lat":"51.5253","lon":"14.8217","stan_wody":"226","stan_wody_data_pomiaru":"2026-10-15 13:50:00","stan_ostrzegawczy":"300","stan_alarmowy":"340",...}` – all values as strings, many `null`s.
- **Decision needed:** these are *measurements*, not events; `type` enum has no value for them. Options: (a) store only stations above `stan_ostrzegawczy` as `hydro_warning` (severity 2 ≥ warning, 3 ≥ alarm); (b) add `hydro_station` type. TERYT via `ST_Intersects(point, powiat)`.

**IMGW license ✅** – [Regulamin udostępniania danych](https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf) (also on the page https://danepubliczne.imgw.pl/). Free for private (non-commercial) purposes; high-value datasets free for any purpose. Required text on the product:
- „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy”
- if processed (we normalize → yes): „Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone”
- ⚠️ Regulamin counts *websites containing advertising* as business use (paid agreement). → **No ads on the site, ever.**

## 3. GIOŚ – air quality ✅ (old API is dead)

- Old `/pjp-api/rest/...` returns **410 Gone** (retired 2025-06-30). Use `/pjp-api/v1/rest/...`. OpenAPI: https://api.gios.gov.pl/pjp-api/swagger-ui/
- **Stations:** `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll?size=500` → 288 stations, 1 page. JSON-LD with **Polish keys containing spaces/Greek letters**: `"Identyfikator stacji":11, "WGS84 φ N":"50.912475", "WGS84 λ E":"15.312190", "Powiat":"lubański", ...`
- **Index:** `GET https://api.gios.gov.pl/pjp-api/v1/rest/aqindex/getIndex/{stationId}` → `{"AqIndex":{"Identyfikator stacji pomiarowej":52,"Wartość indeksu":0,"Nazwa kategorii indeksu":"Bardzo dobry","Data danych źródłowych…":"2026-10-15 16:00:00", ...per-pollutant fields}}`
- **No bulk endpoint** → 288 requests per cycle.
- **Limits** (from https://powietrze.gios.gov.pl/pjp/content/api): index 1500 req/min; station list "2 i 1500 req/min" (ambiguous → fetch list once a day); metadata/archive 2 req/min. `Cache-Control: max-age=30` on index. Plan: hourly cycle (data is hourly), throttled ~5 req/s.
- **Mapping:** `source_event_id=stationId`, `type=air_quality`, geom=station point, TERYT via `ST_Intersects`, `valid_from` = source data hour. **Decision needed:** index is 0–5 (Bardzo dobry…Bardzo zły), severity is 0–3. Proposal: 0–1→0, 2→1, 3→2, 4–5→3. Index `-1`/null = no data → skip.
- **License ✅/⚠️:** using the API = accepting the portal Regulamin; must "clearly indicate the source". Exact regulamin URL not yet confirmed (link on the API page). Proposed attribution: „Źródło: GIOŚ, portal Jakość Powietrza”. Data is unverified (may change later).

## 4. NASA FIRMS – fire hotspots ✅ (no key needed)

- **Used:** public, key-less 24 h Europe CSV files, verified 2026-10-15 (≈80 KB each, same columns as the MAP_KEY area API):
  - `https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv`
  - `https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_Europe_24h.csv`
- **Suomi NPP deliveries end 2026-11-02** (banner on earthdata.nasa.gov) → only NOAA-20/NOAA-21.
- **Columns:** `latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight`
  Sample: `52.58381,19.66626,295.24,0.58,0.52,2026-10-14,0009,N20,nominal,2.0NRT,277.14,1.35,N`
- `confidence` ∈ `low/nominal/high` → severity 1/2/3. `acq_time` = HHMM UTC.
- **Mapping:** `source_event_id = satellite:acq_date:acq_time:lat:lon`, geom = point, `valid_to = acq + 24 h`, TERYT via `ST_Intersects`; points outside Polish powiaty are dropped (bbox pre-filter in Python).
- Poll every 30 min (2 requests). The MAP_KEY area API remains an option if the public files disappear.
- **License ✅:** NASA full and open data sharing, no restrictions; cite as "NASA FIRMS" (FAQ: https://www.earthdata.nasa.gov/data/tools/firms/faq) + LANCE disclaimer.

## 5. GUGiK PRG – administrative boundaries ✅ / license ⚠️

- **Recommended:** WFS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries` – layers `ms:A01_Granice_wojewodztw`, `ms:A02_Granice_powiatow`. GetFeature works; GML 3.2, **EPSG:2180** (transform to 4326). Attributes: `JPT_KOD_JE` = TERYT (e.g. `1416`), `JPT_NAZWA_` = name.
- Alternative: full zip `https://opendata.geoportal.gov.pl/prg/granice/00_jednostki_administracyjne.zip` (**377 MB**, shapefiles) – too heavy for a one-off script.
- **Mapping:** `admin_units(teryt, level, name, geom=ST_SimplifyPreserveTopology(ST_Transform(g,4326), tol))`.
- **National outline:** `db/build_poland_outline.py` writes `web/static/poland.geojson` (union of voivodeships, buffer-closed and simplified, ~14 KB) – the map dims everything outside Poland and locks the view to it. Re-run after `import_prg.py` when PRG changes.
- **License ❓:** PRG is generally published free of charge by GUGiK, but **I did not find/confirm a terms page** in this session. Needs a link before going to prod.

---

## 6. GDDKiA – road incidents on national roads ⚠️ (step 0 for pre-launch, 2026-10-15)

### Options checked
| Option | Result |
|---|---|
| **Open XML feed** `https://www.archiwum.gddkia.gov.pl/dane/zima_html/utrdane.xml` | ✅ `200`, `application/xml`, ~580 KB, **550 records**, `Last-Modified` 15:22 UTC, `ETag` present. No key, `robots.txt: Allow: /`. Old URL `www.gddkia.gov.pl/dane/zima_html/utrdane.xml` → 404. |
| dane.gov.pl dataset [2752 „Utrudnienia na drogach”](https://dane.gov.pl/pl/dataset/2752) (publisher: GDDKiA) | ✅ points to the XML above. **License: CC0 1.0.** Metadata last modified 2024-02-16, frequency „nie dotyczy”. |
| KPD – Krajowy Punkt Dostępowy (DATEX II), https://kpd.gddkia.gov.pl/ | ⚠️ needs a **formal registration of an organisation** (paper/scan application to GDDKiA), test certificates and a scheduled message-exchange test before production access. Not realistic for a hobby project. |

**Recommendation:** use the open XML feed (CC0). ⚠️ Risk: it lives on an `archiwum.` (archive) domain – it may disappear without notice; KPD is the long-term fallback.

### Format (sample record, trimmed)
```xml
<utrudnienia gen="2026-10-15T17:28:02+0200">
  <utr><typ>U</typ><nr_drogi>A1</nr_drogi><woj>pomorskie</woj><km>65.150</km><dl>9.830</dl>
    <geo_lat>53.682945</geo_lat><geo_long>18.633125</geo_long>
    <nazwa_odcinka>Kopytkowo - Warlubie</nazwa_odcinka>
    <data_powstania>2026-09-23T00:00:00+0200</data_powstania><data_likwidacji>2026-11-08T23:59:00+0100</data_likwidacji>
    <objazd>Prace remontowe na nitce prawej (kierunek Łódź). Przełożenie ruchu na przeciwległą jezdnię…</objazd>
    <rodzaj><poz>U33</poz></rodzaj><ogr_predkosc>50</ogr_predkosc>
    <ruch_wahadlowy>false</ruch_wahadlowy><sygnalizacja_swietlna>false</sygnalizacja_swietlna><awaria_mostu>false</awaria_mostu>
    <ruch_2_kierunkowy>false</ruch_2_kierunkowy><droga_zamknieta>false</droga_zamknieta> …</utr>
```
Snapshot of 2026-10-15 (550 records): `typ` U=522, I=26, W=2; `rodzaj` U33=451, U42=63, I04=26, U27=8, R11=2;
`droga_zamknieta=true` 8, `ruch_wahadlowy=true` 134, `sygnalizacja_swietlna=true` 42, `ruch_2_kierunkowy=true` 29, `awaria_mostu=true` 1;
33 records **without coordinates**; flag fields missing on the 28 non-U records. Saved trimmed fixture: `ingest/tests/fixtures/gddkia_utrdane.xml`.

### What is NOT documented ❓
- **No code list** for `typ` / `rodzaj` in the feed or on dane.gov.pl. From samples (inference, not verified): `U` = roadworks (U33 roadworks, U42 lane narrowing, U27 junction/viaduct works), `W` = incident (R11: blocked lane, ~2 h), `I` = other restriction (I04: speed limit after pavement damage, long-running).
- **Update frequency:** unknown. The file did not change during a 10-minute observation. Polling every 15 min with `If-None-Match` (ETag) costs ~nothing when unchanged.
- **No stable record ID.**
- **No line geometry** – only a point (`geo_lat/long`) plus road kilometre `km` and length `dl` (km).
- **`objazd`** is free text (often a description of the restriction, not a detour).

### Proposed mapping → `events` (needs your decision)
- `type = road_incident` (new enum value + migration), `source = gddkia` (new enum value).
- `source_event_id` = hash of `typ|nr_drogi|woj|km|data_powstania|nazwa_odcinka` (2 collisions on the 6-field key `nr_drogi|km|data_powstania|woj` alone). ⚠️ If GDDKiA edits any of these, it becomes a new event (old one is closed as missing) → possible duplicate push for closures.
- `severity`: `droga_zamknieta` → **3**; `ruch_wahadlowy` / `sygnalizacja_swietlna` / `ruch_2_kierunkowy` / `awaria_mostu` / `typ=W` → **2**; everything else (roadworks, speed limits, narrowing) → **1**. (Matches the brief's examples; 0 unused.)
- `title` = e.g. „Zamknięcie drogi: A1, Kopytkowo – Warlubie” / „Ruch wahadłowy: DK15 …” / „Roboty drogowe: …”; `description` = `objazd` + limits (`ogr_predkosc`, `ogr_nosnosc`, …) + `km`/`dl`.
- `valid_from/valid_to` = `data_powstania` / `data_likwidacji` (have explicit offsets).
- Geometry: **point**; TERYT via `ST_Intersects`. Records **without coordinates are skipped** (decision below).
- `source_url`: no per-record link; use https://www.gov.pl/web/gddkia (to verify a better public map link).
- **License:** CC0 1.0 – no attribution required; we will still credit „Źródło: GDDKiA”.

## 7. IOŚ-PIB – air quality forecast ❌ (research 2026-10-15, dropped by the owner the same day)

- **Endpoint:** `GET https://api.prognozy.ios.edu.pl/v1/{PM10|NO2|O3|SO2}/{TERYT}/` (trailing slash required – without it the server answers **308 → plain `http://`**). Accepts 4-digit powiat and 7-digit gmina codes. `PM25` → 404.
- **Sample:** `{"20261015": 22.19, "20261016": 30.09, "20261017": 35.1}` – forecast daily mean, µg/m³, today + 2 days. Served as `text/html` although the body is JSON.
- Advertised by GIOŚ on https://powietrze.gios.gov.pl/pjp/content/api ("Interfejs API Prognoz jakości powietrza … IOŚ-PIB"); questions go to IOŚ-PIB.
- ⚠️ **TLS:** the server sends only the leaf certificate (`CN=*.zmaik.pl`, SAN includes `api.prognozy.ios.edu.pl`) without the `GEANT TLS RSA 1` intermediate → verification fails in curl/httpx (`unable to verify the first certificate`). Fix on our side would be pinning the official GEANT intermediate in a CA bundle – never disabling verification.
- ⚠️ **License: unknown.** No terms in the API; https://prognozy.ios.edu.pl/ did not respond (timeout). Not implemented until terms are confirmed.
- Usable reference threshold (verified via GIOŚ `/v1/rest/levels/getPermissible`): **PM10 daily limit 50 µg/m³** („Poziom dopuszczalny … S24 > 50 ug/m3”). No verified daily thresholds for NO₂/O₃/SO₂.

## 8. IMGW-PIB – water level history (2026-10-15)

- The official API (`/api/data/hydro`, `/api/data/hydro/id/{id}`) returns **only the current measurement**.
- `https://hydro-back.imgw.pl/station/hydro/status?id=…` (backend of the hydro.imgw.pl map) has series, but it is **not covered by the IMGW data terms** (they name danepubliczne.imgw.pl and meteo.imgw.pl) → not used.
- **Decision:** keep our own history – the stations worker already reads all 913 stations every 10 min; each new measurement is stored in `water_levels` (7-day retention). Charts start filling from deployment; no backfill.

## 9. adsb.lol – GPS interference estimate from ADS-B ⚠️ (2026-10-15, unofficial source)

- **No official source exists** for GNSS interference over Poland. Accepted by the owner as the **only non-official source** on the map, labelled as an estimate.
- **Endpoint:** `GET https://api.adsb.lol/v2/point/51.9/19.3/250` → `200`, JSON `{"ac": [...], "now": ms, "total": n}`, `cache-control: no-store`. One circle (250 NM = API max, 463 km) covers all of Poland; the farthest corner (Bieszczady) is ~420 km from the centre. ~200 aircraft at 19:20 local time, ~110 usable.
- **Auth / limits:** no key, no rate-limit headers, none documented ("The API is available to everyone"). One request per minute (the same response also feeds the aircraft layer, §10). Occasional dropped connections seen → covered by the worker's retry.
- **License ✅:** ODbL 1.0 (https://www.adsb.lol/docs/open-data/api/). Attribution: „adsb.lol, ODbL 1.0”.
- **Fields used:** `hex`, `lat`, `lon`, `nac_p` (Navigation Accuracy Category – Position), `version` (ADS-B version), `alt_baro` (`"ground"` on the ground), `seen_pos`, `mlat`/`tisb` (lists of fields derived on the ground).
- **Method** (gpsjam.org's, over a rolling 60-minute window instead of 24 h):
  - aircraft counted only with ADS-B v2, airborne, position ≤ 60 s old, position not from MLAT/TIS-B;
  - degraded = `nac_p < 8` (estimated position error ≥ 93 m; airliners normally report 9–11);
  - grid 0.5° lat × 0.75° lon (~55 × 50 km), distinct aircraft per cell in the window; an aircraft is degraded if any of its reports in that cell was;
  - share = `100 × (degraded − 1) / all` (one aircraft alone never counts), only cells with ≥ 8 aircraft;
  - severity: 2–10 % → 1, 10–30 % → 2, ≥ 30 % → 3 (gpsjam.org uses 2 % and 10 % for yellow/red; the 30 % step is ours).
- **Mapping → `events`:** `source=adsb_lol`, `type=gps_interference`, `source_event_id = row:col` of the cell, geom = cell polygon, TERYT via `ST_Intersects` (cells entirely outside Poland, e.g. over Kaliningrad, are dropped), `valid_from` = when the cell first crossed the threshold, `valid_to` open; the cell is closed when it drops below.
- **Limits of the estimate:** low NACp can also come from a faulty or old transponder; few aircraft at night → fewer cells; the window is kept in memory, so after an ingest restart it takes up to an hour to fill again.

## 10. adsb.lol – aircraft over Poland (map layer, 2026-10-15)

- Same request as §9 (`/v2/point/51.9/19.3/250`, every 60 s); no extra load on the source.
- **Stored:** only the latest snapshot in `aircraft` (table replaced on every run) – no tracks or history are kept. API `/api/aircraft` hides positions older than 5 min (e.g. ingest down).
- **Filtered out:** outside Poland's bbox; `alt_baro = "ground"`; position older than 60 s; category `C*` (surface vehicles, obstacles) and registrations `TWR`/`GND` (airport ground stations reported by some feeders – 20+ per snapshot); **`dbFlags` 4 (PIA) or 8 (FAA LADD)** – owners who asked not to be shown (adsb.lol itself does not filter them).
- **Classes:**
  - `military` – `dbFlags & 1` (adsb.lol aircraft database). Checked 2026-10-15: 8 over Poland, e.g. C-17 (RCH), NATO E-3, W-3 (PLF), PZL-130 Orlik, Mi-8. Military aircraft that fly without a transponder are not visible at all.
  - `commercial` – callsign = ICAO airline designator + flight number (`^[A-Z]{3}\d[0-9A-Z]{0,4}$`, e.g. LOT3AB, RYR12QK) or wake category A3–A6 (≥ 34 t). Includes charter/business-jet operators with airline-style callsigns (e.g. NetJets).
  - `private` – everything else: light aircraft, helicopters (incl. rescue and police), gliders, unknown.
- Snapshot 2026-10-15 19:49 local: 96 aircraft over Poland – 74 commercial, 14 private, 8 military.

## 11. CelesTrak – satellite orbital data (map layer, 2026-10-15)

- **Source:** CelesTrak `gp.php` (keyless, verified live). TLE/GP data of the US Space Force public catalogue. Fetched groups: `stations`, `visual`, `gnss`, `starlink`.
- **Usage policy** (https://celestrak.org/usage-policy.php): freely available; **GP updates every ~2 h, callers must not fetch more often**, cache, and stop on non-200. We fetch every 6 h (TLE stays accurate for days).
- **Stored:** latest TLE per satellite in `satellites` (table replaced each run); a satellite in several groups keeps the first (priority stations > visual > gnss > starlink). API `/api/satellites?groups=…` serves the requested groups.
- **Positions are computed in the browser** with SGP4 (satellite.js, ADR 0003), every second. Server snapshots would be stale: LEO satellites move ~7.5 km/s and cross Poland in 1–2 min.
- **"Over Poland"** = sub-satellite point within the locked map view. Measured 2026-10-15: `visual`+`stations` gives ~0 over Poland at any instant (tiny window, ~150 fast LEO objects), so **Starlink is on by default** (~30 over Poland at any time, ~10.6k TLEs, 52 ms to propagate once). GNSS is an optional toggle.
- **Counts 2026-10-15:** stations 17, visual 152, gnss 168, starlink ~10 650.
- Shows the ground-track point, not a view from orbit. Satellites without a transponder-independent public catalogue entry are not shown; the catalogue is the US Space Force's public one.

## 9. EMSC – earthquakes and mining tremors ✅ (step 0, 2026-10-16)

- **Endpoint:** `GET https://www.seismicportal.eu/fdsnws/event/1/query?format=json&minlat=48.5&maxlat=55.5&minlon=13.5&maxlon=24.5&starttime=…&limit=…` → `200`, GeoJSON FeatureCollection. No key.
- **Sample:** `{"id":"20261016_0000213","geometry":{"type":"Point","coordinates":[16.1008,51.5633,-1.0]},"properties":{"time":"2026-10-16T17:00:55.92Z","lastupdate":"2026-10-16T18:49:44Z","flynn_region":"POLAND","mag":2.5,"magtype":"m","depth":1.0,"evtype":"ke","auth":"EMSC","unid":"20261016_0000213"}}`
- Last 30 days in the box: **50 events (48 POLAND, 2 SLOVAKIA)**, M 1.1–2.5, almost all LGOM (Polkowice/Lubin mining area). USGS (`earthquake.usgs.gov/fdsnws/event/1/query?format=geojson`) has only the 4 strongest (M3.9–4.4) → EMSC is the better source; USGS is public domain if ever needed as a fallback.
- **Limits:** none documented; poll every 10–15 min with a `starttime` window of ~7 days.
- **License ✅:** CC BY 4.0 (https://www.seismicportal.eu/terms.html). Credit: „EMSC-CSEM SeismicPortal, https://www.seismicportal.eu”.
- **Proposed mapping:** new type `earthquake`, `source_event_id = unid`, point geometry, TERYT via `ST_Intersects` (events outside Poland dropped), `valid_from = time`, `valid_to = time + 24 h`, title „Wstrząs M2.5 – <powiat>”, severity by magnitude: <2.0 → 0, 2.0–2.9 → 1, 3.0–3.9 → 2, ≥4.0 → 3 (to confirm). Fixture: `ingest/tests/fixtures/emsc_events.json`.

## 10. Gamma dose rate (PAA / EURDEP) ❌ no open machine-readable source (2026-10-16)

- PAA map portal `https://monitoring.paa.gov.pl/maps-portal/` answers scripted requests with a **Web Application Firewall block page** („This transfer is blocked”); no documented API.
- dane.gov.pl only has **biweekly PDF/table reports** („Rozkład mocy dawki promieniowania gamma …”), not real-time data.
- EURDEP (JRC): public maps only; „Authorized users can do more such as unlimited access … through various web-services”. No open endpoint found behind the public map.
- **Recommendation:** ask PAA (or JRC) for data access/terms before building anything. Not implementable today without bypassing a WAF or an authorization scheme.

## 11. Power outages (Tauron, PGE, Energa, Enea, Stoen) ⚠️ no open data (2026-10-16)

- dane.gov.pl: no outage datasets.
- Operators only publish their own web pages (`tauron-dystrybucja.pl/wylaczenia`, `wylaczenia.operator.enea.pl`, `energa-operator.pl/uslugi/awarie-i-wylaczenia`); PGE `power-outage.gkpge.pl` returns **403** to scripts; Stoen URL 404.
- Data exists only behind each site's internal (undocumented) endpoints; **no license or terms for reuse** found. Five different formats, high maintenance.
- **Recommendation:** not without written permission from the operators (or an official open dataset). Marked unclear — not implemented.

## 12. PKP PLK „Otwarte Dane Kolejowe” – rail disruptions ✅ with API key (2026-10-16)

- **API:** `https://pdp-api.plk-sa.pl` („Open Railway Data API” v1.1.4, Swagger at `/swagger/v1/swagger.json`). **`GET /api/v1/disruptions`** – disruptions on railway lines (params `dateFrom`, `dateTo`, `stations`, carriers…). Also real-time train operations and schedules.
- Response (schema): `DisruptionResponseDto {generatedAt, disruptions[], disruptionTypes, stations}`, `DisruptionDto {disruptionId, disruptionTypeCode, startStationId, endStationId, message, affectedRoutes}`. Stations dictionary (`/api/v1/dictionaries/stations`) to resolve coordinates – **to verify** that it has lat/lon.
- **Key required:** header `X-Api-Key`; request via form on https://pdp-api.plk-sa.pl/ (project name, e-mail, usage tier), **manual activation in 3–5 working days**. Without a key: `401 MissingKey`. → **The owner must apply** (personal data – not done by Claude).
- **Limits:** Basic 100/h, 1 000/day (enough for polling every 15 min); Standard 500/h; Premium 2 000/h.
- **Terms ✅ (v1.0, from 2025-12-31, `/api/v1/terms`):** must credit „PKP Polskie Linie Kolejowe S.A.” when publishing; forbidden: commercial resale of raw data without consent, bypassing limits, misleading about the source, sharing the key. Non-commercial map use fits.
- **Proposed mapping:** type `rail_disruption`, `source_event_id = disruptionId`, geometry = line between start/end station (or point when equal), TERYT via `ST_Intersects`, title from `disruptionTypeCode` + stations, description = `message`; severity from disruption type (to decide once the type dictionary is visible with a key). Sample response not yet verified.

## Decisions (accepted 2026-10-15)

1. **Hydro warnings** → assigned to whole województwa from `obszary[].wojewodztwo` (coarse, no catchment geometry available).
2. **Water levels** → only stations at/above `stan_ostrzegawczy` are stored, as `hydro_warning` (severity 2 ≥ warning, 3 ≥ alarm). No new event type.
3. **GIOŚ index → severity:** 0–1→0, 2→1, 3→2, 4–5→3; `-1`/null skipped.
4. **FIRMS:** uses the public key-less Europe CSV files (found during step 4) – no MAP_KEY needed.
5. **PRG license** and exact **GIOŚ regulamin URL** still to confirm before prod.
6. **GDDKiA** (accepted 2026-10-15): open XML feed, mapping as proposed in §6. **Records without coordinates are skipped** (changed 2026-10-15): the first choice – assigning them to the whole voivodeship – made 28 incidents show up in 724 powiaty, e.g. S19 roadworks near Dukla listed for the city of Krosno in „Moja okolica”. ~5% of records (33 of 550 on 2026-10-15) are lost; they reappear automatically once GDDKiA adds coordinates. Poll every 15 min, full download (no ETag shortcut: an unchanged-file response would otherwise close all incidents as missing). Note: the source's `droga_zamknieta` flag is also set for partial closures (one carriageway / heavy vehicles only).
7. **GPS interference** (accepted 2026-10-15): adsb.lol (ODbL) as the one non-official source, method as in §9, layer labelled as an estimate on the map and on `/zrodla`.
8. **Aircraft layer** (accepted 2026-10-15): adsb.lol snapshot, classes and filters as in §10; latest positions only, LADD/PIA aircraft hidden.
9. **Satellites** (accepted 2026-10-15): CelesTrak TLE, SGP4 in the browser (ADR 0003). Starlink on by default so the layer is not empty; see §11.
