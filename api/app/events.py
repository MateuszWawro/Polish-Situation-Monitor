"""Event, source status and admin unit queries. GeoJSON is assembled in PostGIS."""

from typing import Literal, get_args

from sqlalchemy import text

EventType = Literal[
    "weather_warning", "hydro_warning", "air_quality", "fire_hotspot", "road_incident"
]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)

# Cache TTL per type: well below each source's polling interval (docs/SOURCES.md).
CACHE_TTL_S = {
    "weather_warning": 60,
    "hydro_warning": 60,
    "air_quality": 300,
    "fire_hotspot": 300,
    "road_incident": 300,
}
MAX_FEATURES = 5000

PROPERTIES = """
    'id', id, 'source', source, 'source_event_id', source_event_id, 'type', type,
    'severity', severity, 'title', title,
    'description', description, 'teryt_powiat', teryt_powiat, 'valid_from', valid_from,
    'valid_to', valid_to, 'source_url', source_url, 'fetched_at', fetched_at,
    'updated_at', updated_at
"""

# Active = not ended yet (includes warnings that start later, e.g. tonight's fog).
# List geometry is simplified (~1 km) – warning areas can span hundreds of powiaty.
EVENTS_SQL = text(f"""
    SELECT json_build_object('type', 'FeatureCollection', 'features', coalesce(json_agg(
        json_build_object(
            'type', 'Feature', 'id', id,
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.01), 5)::json,
            'properties', json_build_object({PROPERTIES})
        ) ORDER BY severity DESC, valid_from DESC NULLS LAST), '[]'::json))::text
    FROM (
        SELECT * FROM events
        WHERE (CAST(:types AS text[]) IS NULL OR type::text = ANY(CAST(:types AS text[])))
          AND (NOT :active OR valid_to IS NULL OR valid_to > now())
          AND (CAST(:codes AS text[]) IS NULL OR EXISTS (
               SELECT 1 FROM unnest(teryt_powiat) t
               WHERE t = ANY(CAST(:codes AS text[])) OR left(t, 2) = ANY(CAST(:codes AS text[]))))
          AND (CAST(:west AS float8) IS NULL OR geom && ST_MakeEnvelope(
               CAST(:west AS float8), CAST(:south AS float8),
               CAST(:east AS float8), CAST(:north AS float8), 4326))
        ORDER BY severity DESC, valid_from DESC NULLS LAST
        LIMIT {MAX_FEATURES}
    ) e
""")

EVENT_SQL = text(f"""
    SELECT json_build_object(
        'type', 'Feature', 'id', id, 'geometry', ST_AsGeoJSON(geom, 6)::json,
        'properties', json_build_object({PROPERTIES}, 'raw', raw)
    )::text
    FROM events WHERE id = :id
""")

# Every known source is listed, including ones that never ran (stale by definition).
# "Moja okolica": active events per powiat, no geometry (list view). Every requested code is a key.
AREAS_SUMMARY_SQL = text(f"""
    SELECT json_object_agg(code, coalesce(e.events, '[]'::json))::text
    FROM unnest(CAST(:codes AS text[])) AS code
    LEFT JOIN LATERAL (
        SELECT json_agg(json_build_object({PROPERTIES})
                        ORDER BY severity DESC, valid_from DESC NULLS LAST) AS events
        FROM events
        WHERE teryt_powiat @> ARRAY[code] AND (valid_to IS NULL OR valid_to > now())
    ) e ON true
""")

STATUS_SQL = text("""
    SELECT json_agg(json_build_object(
        'source', s.source,
        'last_success_at', st.last_success_at,
        'last_error', st.last_error,
        'last_error_at', st.last_error_at,
        'expected_interval_s', st.expected_interval_s,
        'age_s', extract(epoch FROM now() - st.last_success_at)::int,
        'stale', st.last_success_at IS NULL
                 OR now() - st.last_success_at > 3 * st.expected_interval_s * interval '1 second'
    ) ORDER BY s.source)::text
    FROM unnest(enum_range(NULL::event_source)) AS s(source)
    LEFT JOIN source_status st ON st.source = s.source
""")

# /status: per source, per local day of the last 7 days – runs and successful runs.
SOURCES_HISTORY_SQL = text("""
    SELECT json_agg(json_build_object(
        'source', s.source,
        'days', (
            SELECT json_agg(json_build_object(
                'date', d.day::date, 'attempts', coalesce(a.n, 0), 'ok', coalesce(a.ok, 0)
            ) ORDER BY d.day)
            FROM generate_series(
                (now() AT TIME ZONE 'Europe/Warsaw')::date - 6,
                (now() AT TIME ZONE 'Europe/Warsaw')::date, interval '1 day') AS d(day)
            LEFT JOIN (
                SELECT (started_at AT TIME ZONE 'Europe/Warsaw')::date AS day,
                       count(*) AS n, count(*) FILTER (WHERE ok) AS ok
                FROM fetch_attempts
                WHERE source = s.source AND started_at > now() - interval '8 days'
                GROUP BY 1
            ) a ON a.day = d.day::date
        ),
        'last_attempt', (
            SELECT json_build_object('at', started_at, 'ok', ok, 'error', error,
                                     'duration_ms', duration_ms)
            FROM fetch_attempts WHERE source = s.source ORDER BY started_at DESC LIMIT 1
        )
    ) ORDER BY s.source)::text
    FROM unnest(enum_range(NULL::event_source)) AS s(source)
""")

# Water level chart for one gauge (history kept by the ingest worker, 7 days).
WATER_LEVELS_SQL = text("""
    SELECT json_build_object(
        'station_id', st.station_id, 'name', st.name, 'river', st.river,
        'warning_cm', st.warning_cm, 'alarm_cm', st.alarm_cm,
        'levels', coalesce((
            SELECT json_agg(json_build_array(measured_at, level_cm) ORDER BY measured_at)
            FROM water_levels
            WHERE station_id = st.station_id
              AND measured_at > now() - CAST(:hours AS integer) * interval '1 hour'
        ), '[]'::json)
    )::text
    FROM hydro_stations st WHERE st.station_id = :station_id
""")

ADMIN_UNITS_SQL = text("""
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(json_agg(json_build_object(
            'type', 'Feature',
            'id', teryt,
            'geometry', ST_AsGeoJSON(geom, 4)::json,
            'properties', json_build_object('teryt', teryt, 'level', level, 'name', name)
        ) ORDER BY teryt), '[]'::json)
    )::text
    FROM admin_units
    WHERE CAST(:level AS text) IS NULL OR level = :level
""")
