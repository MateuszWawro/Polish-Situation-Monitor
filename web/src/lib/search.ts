// Offline place search over /places-index.json (built from PRG by db/build_places_index.py).

export interface PlacesIndex {
	voivodeships: Record<string, string>;
	powiaty: Record<string, string>;
	gminy: [name: string, teryt7: string][];
}

export interface PlaceHit {
	/** 4-digit powiat TERYT the place belongs to. */
	teryt: string;
	name: string;
	detail: string;
}

const GMINA_KIND: Record<string, string> = {
	'1': 'gmina miejska',
	'2': 'gmina wiejska',
	'3': 'gmina miejsko-wiejska'
};

/** Lower-case, strip Polish diacritics: "Łódź" → "lodz". */
export function fold(text: string): string {
	return text.toLowerCase().replace(/ł/g, 'l').normalize('NFD').replace(/[̀-ͯ]/g, '');
}

export function searchPlaces(index: PlacesIndex, query: string, limit = 8): PlaceHit[] {
	const q = fold(query.trim());
	if (q.length < 2) return [];
	const woj = (teryt: string) => `woj. ${index.voivodeships[teryt.slice(0, 2)] ?? '?'}`;
	const candidates: (PlaceHit & { key: string })[] = [
		...index.gminy.map(([name, code]) => ({
			key: fold(name),
			teryt: code.slice(0, 4),
			name,
			detail: `${GMINA_KIND[code[6]] ?? 'gmina'}, ${index.powiaty[code.slice(0, 4)] ?? ''}, ${woj(code)}`
		})),
		...Object.entries(index.powiaty).map(([code, name]) => ({
			key: fold(name.replace(/^powiat /, '')),
			teryt: code,
			name,
			detail: woj(code)
		}))
	];
	const rank = (key: string) => (key === q ? 0 : key.startsWith(q) ? 1 : key.includes(q) ? 2 : -1);
	return candidates
		.map((c) => ({ c, r: rank(c.key) }))
		.filter(({ r }) => r >= 0)
		.sort((a, b) => a.r - b.r || a.c.name.localeCompare(b.c.name, 'pl'))
		.slice(0, limit)
		.map(({ c }) => ({ teryt: c.teryt, name: c.name, detail: c.detail }));
}
