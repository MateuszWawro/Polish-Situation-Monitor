"""Event, source status and admin unit queries. GeoJSON is assembled in PostGIS."""

from typing import Literal, get_args

from sqlalchemy import text

EventType = Literal["weather_warning", "hydro_warning", "air_quality", "fire_hotspot"]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)

# Cache TTL per type: well below each source's polling interval (docs/SOURCES.md).
CACHE_TTL_S = {"weather_warning": 60, "hydro_warning": 60, "air_quality": 300, "fire_hotspot": 300}
MAX_FEATURES = 5000

PROPERTIES = """
    'id', id, 'source', source, 'type', type, 'severity', severity, 'title', title,
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
