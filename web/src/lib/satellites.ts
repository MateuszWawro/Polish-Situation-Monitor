import {
	twoline2satrec,
	propagate,
	gstime,
	eciToGeodetic,
	degreesLat,
	degreesLong,
	type SatRec
} from 'satellite.js';
import type { FeatureCollection, Point } from 'geojson';

// Satellite layer: TLE from our API (CelesTrak), propagated to sub-satellite points in the
// browser with SGP4. The server never computes positions – satellites move too fast (see ADR 0003).

export type SatGroup = 'stations' | 'visual' | 'gnss' | 'starlink';

export interface SatTle {
	norad_id: number;
	name: string;
	group: SatGroup;
	tle1: string;
	tle2: string;
}

export interface SatellitesResponse {
	updated_at: string | null;
	satellites: SatTle[];
}

export interface SatProps {
	norad_id: number;
	name: string;
	group: SatGroup;
	altitude_km: number;
	speed_kms: number;
}

export type SatFeatureCollection = FeatureCollection<Point, SatProps>;

/** Groups shown by default (first two) and offered as toggles. Colours avoid the severity palette. */
export const SAT_GROUPS: {
	id: SatGroup;
	label: string;
	note: string;
	color: string;
	default: boolean;
}[] = [
	{
		id: 'stations',
		label: 'Stacje kosmiczne',
		note: 'ISS, Tiangong',
		color: '#f2c94c',
		default: true
	},
	{
		id: 'visual',
		label: 'Jasne (widoczne)',
		note: '~150 najjaśniejszych',
		color: '#5ec8d8',
		default: true
	},
	{
		id: 'gnss',
		label: 'Nawigacja (GNSS)',
		note: 'GPS, Galileo, GLONASS',
		color: '#9d8cff',
		default: false
	},
	{
		id: 'starlink',
		label: 'Starlink',
		note: 'konstelacja, gęsto',
		color: '#9aa5b1',
		default: true
	}
];

export interface SatEntry {
	norad_id: number;
	name: string;
	group: SatGroup;
	satrec: SatRec;
}

/** Parse TLEs to SGP4 records once; records with bad elements are dropped. */
export function parseEntries(tles: SatTle[]): SatEntry[] {
	const entries: SatEntry[] = [];
	for (const t of tles) {
		try {
			const satrec = twoline2satrec(t.tle1, t.tle2);
			// A malformed TLE yields error flags or NaN elements rather than throwing.
			if (satrec.error || !Number.isFinite(satrec.no)) continue;
			entries.push({ norad_id: t.norad_id, name: t.name, group: t.group, satrec });
		} catch {
			// skip unparseable TLE
		}
	}
	return entries;
}

const EARTH_RADIUS_KM = 6371;

/** Sub-satellite points within `bounds` ([[w,s],[e,n]]) at time `when`. */
export function positionsAt(
	entries: SatEntry[],
	when: Date,
	bounds: [[number, number], [number, number]]
): SatFeatureCollection {
	const gmst = gstime(when);
	const [[west, south], [east, north]] = bounds;
	const features: SatFeatureCollection['features'] = [];
	for (const e of entries) {
		const pv = propagate(e.satrec, when);
		if (!pv || !pv.position || typeof pv.position === 'boolean') continue;
		const geo = eciToGeodetic(pv.position, gmst);
		const lat = degreesLat(geo.latitude);
		const lon = degreesLong(geo.longitude);
		if (lat < south || lat > north || lon < west || lon > east) continue;
		const v = pv.velocity;
		const speed = v && typeof v !== 'boolean' ? Math.hypot(v.x, v.y, v.z) : 0; // km/s
		features.push({
			type: 'Feature',
			id: e.norad_id,
			geometry: { type: 'Point', coordinates: [lon, lat] },
			properties: {
				norad_id: e.norad_id,
				name: e.name,
				group: e.group,
				altitude_km: Math.round(Math.max(0, geo.height)),
				speed_kms: Math.round(speed * 100) / 100
			}
		});
	}
	return { type: 'FeatureCollection', features };
}

export function orbitalPeriodMin(altitudeKm: number): number {
	const a = EARTH_RADIUS_KM + altitudeKm;
	// T = 2π√(a³/µ), µ = 398600 km³/s²; in minutes.
	return (2 * Math.PI * Math.sqrt(a ** 3 / 398600)) / 60;
}
