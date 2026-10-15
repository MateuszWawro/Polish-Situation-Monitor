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

## 4. NASA FIRMS – fire hotspots ⚠️ (needs your MAP_KEY)

- **Endpoint:** `GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/14.07,49.00,24.15,54.84/1` (bbox west,south,east,north; day range 1–5). Sources: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `MODIS_NRT`.
- With invalid key: `Invalid MAP_KEY.` → **real response/sample row not yet verified.** Free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/
- **Limits ❓:** per-key "transactions" quota, checkable at `/mapserver/mapkey_status/?MAP_KEY=…`; the value was not visible without a key. Plan: every 30 min × 3 VIIRS sources.
- **Mapping (from documented attribute tables, to verify on a real row):** `source_event_id = satellite+acq_date+acq_time+lat+lon`, `type=fire_hotspot`, geom=point, severity from `confidence` (VIIRS: l/n/h → 1/2/3), `valid_from`=acq time (UTC), `valid_to`=+24 h. TERYT via `ST_Intersects`. Bbox includes neighbours → drop points outside Poland.
- **License ✅:** NASA full and open data sharing, no restrictions; cite as "NASA FIRMS" (FAQ: https://www.earthdata.nasa.gov/data/tools/firms/faq) + LANCE disclaimer.

## 5. GUGiK PRG – administrative boundaries ✅ / license ⚠️

- **Recommended:** WFS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries` – layers `ms:A01_Granice_wojewodztw`, `ms:A02_Granice_powiatow`. GetFeature works; GML 3.2, **EPSG:2180** (transform to 4326). Attributes: `JPT_KOD_JE` = TERYT (e.g. `1416`), `JPT_NAZWA_` = name.
- Alternative: full zip `https://opendata.geoportal.gov.pl/prg/granice/00_jednostki_administracyjne.zip` (**377 MB**, shapefiles) – too heavy for a one-off script.
- **Mapping:** `admin_units(teryt, level, name, geom=ST_SimplifyPreserveTopology(ST_Transform(g,4326), tol))`.
- **License ❓:** PRG is generally published free of charge by GUGiK, but **I did not find/confirm a terms page** in this session. Needs a link before going to prod.

---

## Decisions (accepted 2026-10-15)

1. **Hydro warnings** → assigned to whole województwa from `obszary[].wojewodztwo` (coarse, no catchment geometry available).
2. **Water levels** → only stations at/above `stan_ostrzegawczy` are stored, as `hydro_warning` (severity 2 ≥ warning, 3 ≥ alarm). No new event type.
3. **GIOŚ index → severity:** 0–1→0, 2→1, 3→2, 4–5→3; `-1`/null skipped.
4. **FIRMS:** worker built against documented CSV format; verify with a real MAP_KEY once provided.
5. **PRG license** and exact **GIOŚ regulamin URL** still to confirm before prod.
