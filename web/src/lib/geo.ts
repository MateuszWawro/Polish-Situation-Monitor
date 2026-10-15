// On-device geometry: the user's position is only ever compared locally (privacy rule).
import type { FeatureCollection, Geometry, MultiPolygon, Polygon, Position } from 'geojson';

function inRing([x, y]: Position, ring: Position[]): boolean {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const [xi, yi] = ring[i];
		const [xj, yj] = ring[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
	}
	return inside;
}

function inPolygon(point: Position, rings: Position[][]): boolean {
	const [outer, ...holes] = rings;
	return inRing(point, outer) && !holes.some((hole) => inRing(point, hole));
}

export function pointInGeometry(point: Position, geometry: Polygon | MultiPolygon): boolean {
	return geometry.type === 'Polygon'
		? inPolygon(point, geometry.coordinates)
		: geometry.coordinates.some((polygon) => inPolygon(point, polygon));
}

/** TERYT code of the powiat containing [lon, lat], or null (e.g. abroad). */
export function findPowiat(point: Position, powiaty: FeatureCollection): string | null {
	for (const f of powiaty.features) {
		const g = f.geometry;
		if ((g.type === 'Polygon' || g.type === 'MultiPolygon') && pointInGeometry(point, g))
			return String(f.properties?.teryt ?? f.id);
	}
	return null;
}

export interface MapViewState {
	center: [number, number];
	zoom: number;
}

/** [[west, south], [east, north]] of any GeoJSON geometry, or null when empty. */
export function bbox(geometry: Geometry): [[number, number], [number, number]] | null {
	let w = Infinity,
		s = Infinity,
		e = -Infinity,
		n = -Infinity;
	const walk = (c: unknown): void => {
		if (Array.isArray(c) && typeof c[0] === 'number') {
			const [x, y] = c as number[];
			w = Math.min(w, x);
			e = Math.max(e, x);
			s = Math.min(s, y);
			n = Math.max(n, y);
		} else if (Array.isArray(c)) c.forEach(walk);
	};
	if (geometry.type === 'GeometryCollection') geometry.geometries.forEach((g) => walk(bbox(g)));
	else walk(geometry.coordinates);
	return w === Infinity
		? null
		: [
				[w, s],
				[e, n]
			];
}

export interface MapPlace {
	id: string;
	name: string;
	/** Exact point from "use my location", else the middle of the powiat. */
	lngLat: [number, number];
	/** Powiat outline, when loaded. */
	area?: Geometry;
}
