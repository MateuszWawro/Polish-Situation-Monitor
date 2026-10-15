import { describe, expect, it } from 'vitest';
import { describeTrend, trend, yRange, type WaterLevels } from './hydro';

const at = (h: number) => new Date(Date.UTC(2026, 9, 15, h)).toISOString();

describe('water level trend', () => {
	it('compares the latest reading with ~6 h earlier', () => {
		const levels: [string, number][] = [
			[at(0), 250],
			[at(6), 280],
			[at(9), 300],
			[at(12), 312]
		];
		expect(trend(levels)).toBe(32);
		expect(describeTrend(32)).toBe('rośnie: +32 cm w ciągu 6 godz.');
		expect(describeTrend(-8)).toBe('opada: -8 cm w ciągu 6 godz.');
		expect(describeTrend(1)).toBe('stabilny w ciągu 6 godz.');
	});

	it('needs at least two readings', () => {
		expect(trend([[at(1), 200]])).toBeNull();
		expect(describeTrend(null)).toContain('za mało');
	});

	it('keeps thresholds inside the y range', () => {
		const data: WaterLevels = {
			station_id: '1',
			name: 'X',
			river: null,
			warning_cm: 300,
			alarm_cm: 400,
			levels: [
				[at(0), 200],
				[at(1), 210]
			]
		};
		const [lo, hi] = yRange(data);
		expect(lo).toBeLessThanOrEqual(200);
		expect(hi).toBeGreaterThanOrEqual(400);
		expect(lo % 10).toBe(0);
	});
});
