import { describe, expect, it } from 'vitest';
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import { findPowiat, pointInGeometry } from './geo';

const square = (x: number, y: number, size: number) => [
	[x, y],
	[x + size, y],
	[x + size, y + size],
	[x, y + size],
	[x, y]
];

describe('pointInGeometry', () => {
	const withHole: Polygon = { type: 'Polygon', coordinates: [square(0, 0, 10), square(4, 4, 2)] };
	const multi: MultiPolygon = {
		type: 'MultiPolygon',
		coordinates: [[square(0, 0, 1)], [square(5, 5, 1)]]
	};

	it.each([
		[[1, 1], true],
		[[5, 5], false], // inside the hole
		[[11, 5], false],
		[[-0.001, 5], false]
	])('polygon with hole: %j → %s', (point, expected) => {
		expect(pointInGeometry(point, withHole)).toBe(expected);
	});

	it('handles multipolygons (e.g. powiaty with enclaves)', () => {
		expect(pointInGeometry([5.5, 5.5], multi)).toBe(true);
		expect(pointInGeometry([3, 3], multi)).toBe(false);
	});
});

describe('findPowiat', () => {
	const fc: FeatureCollection = {
		type: 'FeatureCollection',
		features: [
			{
				type: 'Feature',
				id: '1465',
				properties: { teryt: '1465' },
				geometry: { type: 'Polygon', coordinates: [square(20, 52, 1)] }
			},
			{
				type: 'Feature',
				id: '1261',
				properties: { teryt: '1261' },
				geometry: { type: 'Polygon', coordinates: [square(19, 50, 1)] }
			}
		]
	};

	it('returns the containing powiat or null', () => {
		expect(findPowiat([20.5, 52.5], fc)).toBe('1465');
		expect(findPowiat([19.5, 50.5], fc)).toBe('1261');
		expect(findPowiat([13.4, 52.5], fc)).toBeNull(); // abroad
	});
});
