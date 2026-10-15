// Water level chart helpers (history kept by our ingest, docs/SOURCES.md §8).

export interface WaterLevels {
	station_id: string;
	name: string;
	river: string | null;
	warning_cm: number | null;
	alarm_cm: number | null;
	/** [ISO time, cm], oldest first. */
	levels: [string, number][];
}

/** Change over roughly the last `hours`, or null without enough history. */
export function trend(levels: [string, number][], hours = 6): number | null {
	if (levels.length < 2) return null;
	const [lastAt, last] = levels[levels.length - 1];
	const since = Date.parse(lastAt) - hours * 3600_000;
	const past = levels.find(([at]) => Date.parse(at) >= since);
	if (!past || past[0] === lastAt) return null;
	return Math.round(last - past[1]);
}

export function describeTrend(delta: number | null, hours = 6): string {
	if (delta === null) return 'za mało pomiarów, by ocenić trend';
	if (Math.abs(delta) < 3) return `stabilny w ciągu ${hours} godz.`;
	return `${delta > 0 ? 'rośnie' : 'opada'}: ${delta > 0 ? '+' : ''}${delta} cm w ciągu ${hours} godz.`;
}

/** Y range covering the data and the thresholds, padded and rounded to 10 cm. */
export function yRange(data: WaterLevels): [number, number] {
	const values = [
		...data.levels.map(([, cm]) => cm),
		...[data.warning_cm, data.alarm_cm].filter((v): v is number => v !== null)
	];
	const lo = Math.min(...values);
	const hi = Math.max(...values);
	const pad = Math.max(10, (hi - lo) * 0.1);
	return [Math.floor((lo - pad) / 10) * 10, Math.ceil((hi + pad) / 10) * 10];
}
