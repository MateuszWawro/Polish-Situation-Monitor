import type { Polygon } from 'geojson';

type BBox = [number, number, number, number];
let cache: Promise<Record<string, BBox>> | null = null;

/** Powiat bounding boxes from the API (~15 KB, fetched once per page load). */
export function powiatBboxes(): Promise<Record<string, BBox>> {
	cache ??= fetch('/api/admin-units/bboxes').then((r) => {
		if (!r.ok) throw new Error(`${r.status}`);
		return r.json();
	});
	cache.catch(() => (cache = null)); // retry next time after a failure
	return cache;
}

export function bboxPolygon([w, s, e, n]: BBox): Polygon {
	return {
		type: 'Polygon',
		coordinates: [
			[
				[w, s],
				[e, s],
				[e, n],
				[w, n],
				[w, s]
			]
		]
	};
}
