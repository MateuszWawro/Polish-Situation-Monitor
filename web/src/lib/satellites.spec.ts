import { describe, expect, it } from 'vitest';
import { orbitalPeriodMin, parseEntries, positionsAt, type SatTle } from './satellites';

const ISS: SatTle = {
	norad_id: 25544,
	name: 'ISS (ZARYA)',
	group: 'stations',
	tle1: '1 25544U 98067A   26288.11220063  .00005682  00000+0  11168-3 0  9991',
	tle2: '2 25544  51.6331  66.6267 0006716 264.3647  95.6576 15.48871015590345'
};
const WORLD: [[number, number], [number, number]] = [
	[-180, -90],
	[180, 90]
];
const EMPTY: [[number, number], [number, number]] = [
	[0, 0],
	[0.001, 0.001]
];

describe('satellites', () => {
	it('parses valid TLEs and drops broken ones', () => {
		const bad: SatTle = { ...ISS, norad_id: 1, tle1: 'garbage', tle2: 'garbage' };
		const entries = parseEntries([ISS, bad]);
		expect(entries.map((e) => e.norad_id)).toEqual([25544]);
	});

	it('computes a plausible ISS sub-point, altitude and speed', () => {
		const [iss] = parseEntries([ISS]);
		const when = new Date('2026-10-15T03:00:00Z');
		const fc = positionsAt([iss], when, WORLD);
		expect(fc.features).toHaveLength(1);
		const p = fc.features[0].properties;
		expect(p.altitude_km).toBeGreaterThan(350);
		expect(p.altitude_km).toBeLessThan(500);
		expect(p.speed_kms).toBeGreaterThan(7);
		expect(p.speed_kms).toBeLessThan(8);
		const [lon, lat] = fc.features[0].geometry.coordinates;
		expect(Math.abs(lat)).toBeLessThanOrEqual(52); // inclination 51.6°
		expect(Math.abs(lon)).toBeLessThanOrEqual(180);
	});

	it('filters out satellites outside the bounds', () => {
		const [iss] = parseEntries([ISS]);
		expect(positionsAt([iss], new Date('2026-10-15T03:00:00Z'), EMPTY).features).toHaveLength(0);
	});

	it('estimates an orbital period around 90 min for LEO', () => {
		expect(orbitalPeriodMin(420)).toBeGreaterThan(90);
		expect(orbitalPeriodMin(420)).toBeLessThan(94);
	});
});
