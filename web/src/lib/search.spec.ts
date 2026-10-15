import { describe, expect, it } from 'vitest';
import { fold, searchPlaces, type PlacesIndex } from './search';

const index: PlacesIndex = {
	voivodeships: { '10': 'łódzkie', '18': 'podkarpackie', '08': 'lubuskie' },
	powiaty: {
		'1061': 'powiat Łódź',
		'1807': 'powiat krośnieński',
		'0802': 'powiat krośnieński',
		'1861': 'powiat Krosno'
	},
	gminy: [
		['Łódź', '1061011'],
		['Krosno', '1861011'],
		['Krosno Odrzańskie', '0802063'],
		['Korczyna', '1807032']
	]
};

describe('searchPlaces', () => {
	it('ignores case and Polish diacritics', () => {
		expect(fold('Łódź')).toBe('lodz');
		expect(searchPlaces(index, 'lodz')[0]).toMatchObject({ name: 'Łódź', teryt: '1061' });
	});

	it('ranks exact, then prefix, then substring matches and resolves the powiat', () => {
		const hits = searchPlaces(index, 'krosno');
		expect(hits[0]).toMatchObject({ name: 'Krosno', teryt: '1861' });
		expect(hits.map((h) => h.name)).toContain('Krosno Odrzańskie');
		expect(hits.find((h) => h.name === 'Krosno Odrzańskie')?.teryt).toBe('0802');
	});

	it('finds powiaty and tells same-named ones apart by voivodeship', () => {
		const hits = searchPlaces(index, 'krośnieński');
		expect(hits.map((h) => h.detail).sort()).toEqual(['woj. lubuskie', 'woj. podkarpackie']);
	});

	it('needs at least 2 characters', () => {
		expect(searchPlaces(index, 'k')).toEqual([]);
	});
});
