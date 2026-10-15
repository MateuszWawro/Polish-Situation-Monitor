import { describe, expect, it } from 'vitest';
import {
	LAYERS,
	formatInterval,
	inLayer,
	formatRange,
	groupEvents,
	severityLabel,
	sourceHealth,
	timeAgo,
	type EventProps,
	type SourceStatus
} from './events';

describe('timeAgo', () => {
	const now = Date.parse('2026-10-15T12:00:00Z');
	it.each([
		['2026-10-15T11:59:40Z', 'przed chwilą'],
		['2026-10-15T11:55:00Z', '5 min temu'],
		['2026-10-15T09:00:00Z', '3 godz. temu'],
		['2026-10-14T11:00:00Z', '1 dzień temu'],
		['2026-10-12T12:00:00Z', '3 dni temu'],
		[null, 'brak danych']
	])('%s → %s', (iso, expected) => {
		expect(timeAgo(iso, now)).toBe(expected);
	});
});

describe('formatting', () => {
	it('shows Warsaw local time and open-ended ranges', () => {
		// 20:00 UTC in summer = 22:00 CEST
		expect(formatRange('2026-07-01T20:00:00Z', '2026-07-02T07:00:00Z')).toMatch(/22:00.*09:00/);
		expect(formatRange('2026-07-01T20:00:00Z', null)).toContain('bez określonego końca');
	});

	it('labels severity with text, not only colour', () => {
		expect(severityLabel(3)).toBe('Stopień 3 – wysoki');
		expect(severityLabel(9)).toBe('Stopień 9');
	});
});

describe('groupEvents', () => {
	const ev = (id: string, type: EventProps['type'], severity: number, title: string) =>
		({ id, type, severity, title }) as EventProps;

	it('groups by layer, merges identical rows and puts the most severe first', () => {
		const groups = groupEvents([
			ev('1', 'hydro_warning', 1, 'Susza hydrologiczna'),
			ev('2', 'hydro_warning', 1, 'Susza hydrologiczna'),
			ev('3', 'road_incident', 1, 'Roboty drogowe: A4'),
			ev('4', 'road_incident', 3, 'Zamknięcie drogi: A4'),
			ev('5', 'air_quality', 0, 'Jakość powietrza: Dobry')
		]);
		expect(groups.map((g) => [g.layer.type, g.count])).toEqual([
			['road_incident', 2],
			['hydro_warning', 2],
			['air_quality', 1]
		]);
		expect(groups[0].rows.map((r) => r.severity)).toEqual([3, 1]);
		expect(groups[1].rows).toHaveLength(1);
		expect(groups[1].rows[0].events.map((e) => e.id)).toEqual(['1', '2']);
	});
});

describe('sourceHealth', () => {
	const status = (age_s: number, stale = false) =>
		({
			source: 'gios',
			age_s,
			expected_interval_s: 600,
			stale,
			last_success_at: null,
			last_error: null
		}) as SourceStatus;

	it('maps age, staleness and the last attempt to a state', () => {
		expect(sourceHealth(status(300), true)).toBe('ok');
		expect(sourceHealth(status(300), false)).toBe('delayed'); // last run failed
		expect(sourceHealth(status(1000), true)).toBe('delayed'); // > 1.5 × 10 min
		expect(sourceHealth(status(2000, true), true)).toBe('down');
	});

	it('formats intervals', () => {
		expect(formatInterval(600)).toBe('co 10 min');
		expect(formatInterval(3600)).toBe('co 1 godz.');
	});
});

describe('drought layer', () => {
	it('splits drought from other hydro warnings', () => {
		const hydro = LAYERS.find((l) => l.id === 'hydro_warning')!;
		const drought = LAYERS.find((l) => l.id === 'drought')!;
		const dry = { type: 'hydro_warning' as const, title: 'Susza hydrologiczna' };
		const flood = {
			type: 'hydro_warning' as const,
			title: 'Wezbranie z przekroczeniem stanów alarmowych'
		};
		expect([inLayer(hydro, dry), inLayer(drought, dry)]).toEqual([false, true]);
		expect([inLayer(hydro, flood), inLayer(drought, flood)]).toEqual([true, false]);
		expect(drought.defaultVisible).toBe(false);
	});
});
