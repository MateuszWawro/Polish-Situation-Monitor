import { describe, expect, it } from 'vitest';
import { bbox } from './geo';
import { buildMapUrl, parseMapUrl } from './mapUrl';

const KNOWN = ['weather_warning', 'drought', 'road_incident'];
const ID = '0b9e7c1a-1234-4abc-8def-0123456789ab';

describe('map URL state', () => {
	it('round-trips layers, filter, view and event', () => {
		const url = buildMapUrl({
			layers: ['weather_warning', 'road_incident'],
			minSeverity: 2,
			view: { center: [19.94, 50.06], zoom: 9 },
			event: ID
		});
		expect(url).toBe(`?l=weather_warning,road_incident&min=2&c=19.9400,50.0600&z=9.00&e=${ID}`);
		expect(parseMapUrl(new URLSearchParams(url), KNOWN)).toEqual({
			layers: ['weather_warning', 'road_incident'],
			minSeverity: 2,
			view: { center: [19.94, 50.06], zoom: 9 },
			event: ID
		});
	});

	it('ignores junk instead of breaking the map', () => {
		const state = parseMapUrl(
			new URLSearchParams('l=evil,drought&min=9&c=500,1&z=x&e=<script>'),
			KNOWN
		);
		expect(state).toEqual({ layers: ['drought'] });
		expect(buildMapUrl({})).toBe('');
	});
});

describe('bbox', () => {
	it('covers points and multipolygons', () => {
		expect(bbox({ type: 'Point', coordinates: [21, 52] })).toEqual([
			[21, 52],
			[21, 52]
		]);
		expect(
			bbox({
				type: 'MultiPolygon',
				coordinates: [
					[
						[
							[14, 49],
							[15, 50],
							[14, 50],
							[14, 49]
						]
					],
					[
						[
							[24, 54],
							[24.1, 54.8],
							[23, 54],
							[24, 54]
						]
					]
				]
			})
		).toEqual([
			[14, 49],
			[24.1, 54.8]
		]);
	});
});
