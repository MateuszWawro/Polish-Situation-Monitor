import { describe, expect, it } from 'vitest';
import {
	countByClass,
	formatAltitude,
	formatSpeed,
	snapshotTime,
	type AircraftCollection,
	type AircraftProps
} from './aircraft';

const plane = (hex: string, cls: AircraftProps['class'], seen_at: string) => ({
	type: 'Feature' as const,
	geometry: { type: 'Point' as const, coordinates: [21, 52] },
	properties: { hex, class: cls, seen_at } as AircraftProps
});

describe('aircraft', () => {
	it('formats altitude in metres with flight level', () => {
		expect(formatAltitude(34000)).toMatch(/^10\s?360 m \(FL340\)$/);
		expect(formatAltitude(2500)).toBe('760 m (FL025)');
		expect(formatAltitude(null)).toBe('brak danych');
	});

	it('formats speed in km/h', () => {
		expect(formatSpeed(450)).toBe('833 km/h');
		expect(formatSpeed(null)).toBe('brak danych');
	});

	it('counts by class and finds the newest position', () => {
		const fc: AircraftCollection = {
			type: 'FeatureCollection',
			features: [
				plane('a', 'commercial', '2026-10-15T17:00:00Z'),
				plane('b', 'commercial', '2026-10-15T17:01:00Z'),
				plane('c', 'military', '2026-10-15T16:59:00Z')
			]
		};
		expect(countByClass(fc)).toEqual({ commercial: 2, private: 0, military: 1 });
		expect(snapshotTime(fc)).toBe('2026-10-15T17:01:00Z');
		expect(snapshotTime(undefined)).toBeNull();
	});
});
