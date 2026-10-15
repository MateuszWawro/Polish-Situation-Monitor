import type { FeatureCollection, Point } from 'geojson';

// Aircraft map layer: latest adsb.lol snapshot from our API (never from the source directly).

export type AircraftClass = 'commercial' | 'private' | 'military';

export interface AircraftProps {
	hex: string;
	class: AircraftClass;
	callsign: string | null;
	registration: string | null;
	aircraft_type: string | null;
	altitude_ft: number | null;
	speed_kt: number | null;
	track: number | null;
	seen_at: string;
}

export type AircraftCollection = FeatureCollection<Point, AircraftProps>;

/** Colours stay outside the severity palette: an aircraft is not a warning level. */
export const AIRCRAFT_CLASSES: { id: AircraftClass; label: string; note: string; color: string }[] =
	[
		{
			id: 'commercial',
			label: 'Komercyjne',
			note: 'linie lotnicze, cargo, czartery',
			color: '#5ec8d8'
		},
		{
			id: 'private',
			label: 'Prywatne i pozostałe',
			note: 'awionetki, śmigłowce (też ratownicze), szybowce',
			color: '#d8dee6'
		},
		{ id: 'military', label: 'Wojskowe', note: 'wg bazy adsb.lol', color: '#e879f9' }
	];

/** Top-down plane pointing north; drawn as an SDF icon so MapLibre can tint it per class. */
export const PLANE_SVG =
	'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#fff" d="M12 1.5c.8 0 1.3.9 1.3 2v5.6l8.2 4.8v2.2l-8.2-2.5v4.9l2.4 1.8v1.8L12 21.2l-3.7 0.9v-1.8l2.4-1.8v-4.9l-8.2 2.5v-2.2l8.2-4.8V3.5c0-1.1.5-2 1.3-2z"/></svg>';

const FT_TO_M = 0.3048;
const KT_TO_KMH = 1.852;

export function formatAltitude(ft: number | null): string {
	if (ft === null) return 'brak danych';
	const m = Math.round((ft * FT_TO_M) / 10) * 10;
	return `${m.toLocaleString('pl-PL')} m (FL${String(Math.round(ft / 100)).padStart(3, '0')})`;
}

export function formatSpeed(kt: number | null): string {
	return kt === null ? 'brak danych' : `${Math.round(kt * KT_TO_KMH)} km/h`;
}

export function countByClass(fc: AircraftCollection | undefined): Record<AircraftClass, number> {
	const counts: Record<AircraftClass, number> = { commercial: 0, private: 0, military: 0 };
	for (const f of fc?.features ?? []) counts[f.properties.class]++;
	return counts;
}

/** Newest position in the snapshot, to show how fresh the layer is. */
export function snapshotTime(fc: AircraftCollection | undefined): string | null {
	let latest: string | null = null;
	for (const f of fc?.features ?? [])
		if (!latest || f.properties.seen_at > latest) latest = f.properties.seen_at;
	return latest;
}
