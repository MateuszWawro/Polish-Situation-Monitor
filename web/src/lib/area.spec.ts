import { describe, expect, it } from 'vitest';
import { describeArea } from './area';
import type { PlacesIndex } from './search';

const index: PlacesIndex = {
	voivodeships: { '18': 'podkarpackie', '16': 'opolskie' },
	powiaty: {
		'1801': 'powiat bieszczadzki',
		'1807': 'powiat krośnieński',
		'1861': 'powiat Krosno',
		'1601': 'powiat brzeski',
		'1602': 'powiat głubczycki'
	},
	gminy: []
};

describe('describeArea', () => {
	it('names whole voivodeships and lists partial ones', () => {
		expect(describeArea(['1601', '1602', '1861', '1807'], index)).toEqual([
			'całe woj. opolskie',
			'powiat krośnieński, powiat Krosno (woj. podkarpackie)'
		]);
	});

	it('counts instead of listing many powiaty', () => {
		const big: PlacesIndex = {
			...index,
			powiaty: Object.fromEntries(Array.from({ length: 10 }, (_, i) => [`180${i}`, `p${i}`]))
		};
		expect(describeArea(['1800', '1801', '1802', '1803', '1804', '1805', '1806'], big)).toEqual([
			'woj. podkarpackie: 7 z 10 powiatów'
		]);
	});
});
