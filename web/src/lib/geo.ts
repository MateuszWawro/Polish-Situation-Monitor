// On-device geometry: the user's position is only ever compared locally (privacy rule).
import type { FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson';

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
