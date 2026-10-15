import type { PlacesIndex } from './search';

const MAX_LISTED = 6;

/** Human description of the powiaty an event covers, e.g. "całe woj. podkarpackie" or
 * "powiat Krosno, powiat krośnieński (woj. podkarpackie)". One line per voivodeship. */
export function describeArea(teryt: string[], index: PlacesIndex): string[] {
	const byVoivodeship = new Map<string, string[]>();
	for (const code of [...new Set(teryt)].sort()) {
		const list = byVoivodeship.get(code.slice(0, 2)) ?? [];
		list.push(code);
		byVoivodeship.set(code.slice(0, 2), list);
	}
	return [...byVoivodeship].map(([woj, codes]) => {
		const name = `woj. ${index.voivodeships[woj] ?? woj}`;
		const all = Object.keys(index.powiaty).filter((c) => c.startsWith(woj)).length;
		if (codes.length === all) return `całe ${name}`;
		if (codes.length > MAX_LISTED) return `${name}: ${codes.length} z ${all} powiatów`;
		const names = codes.map((c) => index.powiaty[c] ?? `powiat ${c}`).join(', ');
		return `${names} (${name})`;
	});
}
