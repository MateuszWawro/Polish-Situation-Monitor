import { describe, expect, it } from 'vitest';
import { formatRange, severityLabel, timeAgo } from './events';

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
