import type { FeatureCollection } from 'geojson';

// Shared types and presentation helpers for events from our API (never from sources directly).

export type EventType =
	| 'weather_warning'
	| 'hydro_warning'
	| 'air_quality'
	| 'fire_hotspot'
	| 'road_incident'
	| 'gps_interference';
export type SourceId = 'imgw_meteo' | 'imgw_hydro' | 'gios' | 'firms' | 'gddkia' | 'adsb_lol';

export interface EventProps {
	id: string;
	source: SourceId;
	type: EventType;
	severity: number;
	title: string;
	description: string | null;
	valid_from: string | null;
	valid_to: string | null;
	source_url: string | null;
	updated_at: string;
	/** Present in API responses; MapLibre turns arrays in feature properties into JSON strings. */
	teryt_powiat?: string[];
	source_event_id?: string;
}

export interface SourceStatus {
	source: SourceId;
	last_error_at?: string | null;
	last_success_at: string | null;
	last_error: string | null;
	expected_interval_s: number | null;
	age_s: number | null;
	stale: boolean;
}

export interface LayerDef {
	/** Map layer id; usually the event type, unless one type is split (drought). */
	id: string;
	type: EventType;
	/** Which events of `type` belong here (default: all). */
	match?: (e: { title: string }) => boolean;
	/** Draw the area as a dashed outline only (no fill). */
	outline?: boolean;
	/** Dotted border in the severity colour, to tell estimated areas from official warnings. */
	dotted?: boolean;
	/** Short explanation shown under the layer name. */
	note?: string;
	defaultVisible?: boolean;
	/** Below DETAIL_ZOOM only events from this severity are drawn (country view stays legible). */
	overviewMinSeverity?: number;
	/** Anchor of the source's section on /zrodla (license and attribution). */
	sourceAnchor: string;
	sourceUrl: string;
	label: string;
	source: SourceId;
	sourceName: string;
	kind: 'area' | 'point' | 'icon';
}

/** IMGW's event name for drought warnings (`zdarzenie`, docs/SOURCES.md §2a). */
export const DROUGHT_TITLE = 'Susza hydrologiczna';

export const LAYERS: LayerDef[] = [
	{
		id: 'weather_warning',
		type: 'weather_warning',
		sourceAnchor: 'imgw',
		sourceUrl: 'https://meteo.imgw.pl/',
		label: 'Ostrzeżenia meteo',
		source: 'imgw_meteo',
		sourceName: 'IMGW-PIB',
		kind: 'area'
	},
	{
		id: 'hydro_warning',
		type: 'hydro_warning',
		match: (e) => e.title !== DROUGHT_TITLE,
		sourceAnchor: 'imgw',
		sourceUrl: 'https://hydro.imgw.pl/',
		label: 'Ostrzeżenia hydro',
		note: 'powodziowe i stany wód',
		source: 'imgw_hydro',
		sourceName: 'IMGW-PIB',
		kind: 'area'
	},
	{
		// Long-running, voivodeship-wide: would tint half the country if filled and on by default.
		id: 'drought',
		type: 'hydro_warning',
		match: (e) => e.title === DROUGHT_TITLE,
		outline: true,
		defaultVisible: false,
		sourceAnchor: 'imgw',
		sourceUrl: 'https://hydro.imgw.pl/',
		label: 'Susza hydrologiczna',
		note: 'obrys obszaru, domyślnie ukryta',
		source: 'imgw_hydro',
		sourceName: 'IMGW-PIB',
		kind: 'area'
	},
	{
		id: 'air_quality',
		type: 'air_quality',
		overviewMinSeverity: 1, // "good" stations (green) only when zoomed in
		sourceAnchor: 'gios',
		sourceUrl: 'https://powietrze.gios.gov.pl/',
		label: 'Jakość powietrza',
		source: 'gios',
		sourceName: 'GIOŚ',
		kind: 'point'
	},
	{
		id: 'fire_hotspot',
		type: 'fire_hotspot',
		sourceAnchor: 'firms',
		sourceUrl: 'https://firms.modaps.eosdis.nasa.gov/',
		label: 'Punkty cieplne (pożary)',
		source: 'firms',
		sourceName: 'NASA FIRMS',
		kind: 'point'
	},
	{
		id: 'road_incident',
		type: 'road_incident',
		overviewMinSeverity: 2, // routine roadworks only when zoomed in
		sourceAnchor: 'gddkia',
		sourceUrl: 'https://www.gov.pl/web/gddkia',
		label: 'Drogi',
		source: 'gddkia',
		sourceName: 'GDDKiA',
		kind: 'icon'
	},
	{
		id: 'gps_interference',
		type: 'gps_interference',
		dotted: true,
		sourceAnchor: 'adsb',
		sourceUrl: 'https://adsb.lol/',
		label: 'Zakłócenia GPS',
		note: 'szacunek z danych ADS-B samolotów, ostatnia godzina',
		source: 'adsb_lol',
		sourceName: 'adsb.lol',
		kind: 'area'
	}
];

/** Drought outline: brown, deliberately outside the severity palette (it is not a level). */
export const DROUGHT_COLOR = '#8a5a2b';

export const SEVERITY_COLORS = ['#2e9d4e', '#e8b420', '#ef7d1a', '#d1242f'];
export const SEVERITY_LABELS = [
	'Stopień 0 – brak zagrożenia',
	'Stopień 1 – niski',
	'Stopień 2 – średni',
	'Stopień 3 – wysoki'
];

export function severityLabel(severity: number): string {
	return SEVERITY_LABELS[severity] ?? `Stopień ${severity}`;
}

/** "przed chwilą", "5 min temu", "3 godz. temu", "2 dni temu". */
export function timeAgo(iso: string | null, now: number = Date.now()): string {
	if (!iso) return 'brak danych';
	const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
	if (minutes < 1) return 'przed chwilą';
	if (minutes < 60) return `${minutes} min temu`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours} godz. temu`;
	const days = Math.floor(hours / 24);
	return days === 1 ? '1 dzień temu' : `${days} dni temu`;
}

const dateFormat = new Intl.DateTimeFormat('pl-PL', {
	timeZone: 'Europe/Warsaw',
	day: 'numeric',
	month: 'short',
	hour: '2-digit',
	minute: '2-digit'
});

export function formatDate(iso: string | null): string {
	return iso ? dateFormat.format(new Date(iso)) : '—';
}

export function formatRange(from: string | null, to: string | null): string {
	if (!to) return `od ${formatDate(from)} (bez określonego końca)`;
	return `${formatDate(from)} – ${formatDate(to)}`;
}

// Road incident icons by severity (= kind of restriction, docs/SOURCES.md §6).
// Shared by the map (rasterised) and the legend (inline), so they always match.
export const ROAD_ICONS: { severity: number; label: string; svg: string }[] = [
	{
		severity: 3,
		label: 'Zamknięcie drogi',
		svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#d1242f" stroke="#fff" stroke-width="2"/><rect x="6" y="10" width="12" height="4" fill="#fff"/></svg>'
	},
	{
		severity: 2,
		label: 'Utrudnienie (wahadło, sygnalizacja, zdarzenie)',
		svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 1.5 22.5 12 12 22.5 1.5 12Z" fill="#ef7d1a" stroke="#fff" stroke-width="2"/><rect x="11" y="6.5" width="2" height="7.5" fill="#fff"/><rect x="11" y="15.5" width="2" height="2" fill="#fff"/></svg>'
	},
	{
		severity: 1,
		label: 'Roboty drogowe / ograniczenia',
		svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2 22.5 21H1.5Z" fill="#e8b420" stroke="#1b1f24" stroke-width="1.5"/><rect x="11" y="8.5" width="2" height="6.5" fill="#1b1f24"/><rect x="11" y="16.5" width="2" height="2" fill="#1b1f24"/></svg>'
	}
];

export interface EventRow {
	key: string;
	title: string;
	severity: number;
	/** Same title + severity in one place, e.g. 14 drought warnings for one voivodeship. */
	events: EventProps[];
}

export interface EventGroup {
	layer: LayerDef;
	count: number;
	rows: EventRow[];
}

export function inLayer(layer: LayerDef, e: { type: EventType; title: string }): boolean {
	return e.type === layer.type && (!layer.match || layer.match(e));
}

/** The part of a type's FeatureCollection that belongs to one layer. */
export function layerFeatures(layer: LayerDef, fc: FeatureCollection | undefined) {
	if (!fc || !layer.match) return fc;
	return {
		...fc,
		features: fc.features.filter((f) => inLayer(layer, f.properties as EventProps))
	};
}

/** Group clicked events by layer, merging identical rows. Most severe group/row first. */
export function groupEvents(events: EventProps[]): EventGroup[] {
	return LAYERS.map((layer) => {
		const rows: EventRow[] = [];
		for (const ev of events.filter((e) => inLayer(layer, e))) {
			const key = `${ev.severity}|${ev.title}`;
			const row = rows.find((r) => r.key === key);
			if (row) row.events.push(ev);
			else rows.push({ key, title: ev.title, severity: ev.severity, events: [ev] });
		}
		rows.sort((a, b) => b.severity - a.severity);
		return { layer, count: rows.reduce((n, r) => n + r.events.length, 0), rows };
	})
		.filter((g) => g.count)
		.sort((a, b) => b.rows[0].severity - a.rows[0].severity);
}

export interface SourceHistory {
	source: SourceId;
	days: { date: string; attempts: number; ok: number }[];
	last_attempt: { at: string; ok: boolean; error: string | null; duration_ms: number } | null;
}

export type Health = 'ok' | 'delayed' | 'down';

/** down = stale (no success for > 3× interval, as the API decides); delayed = last run failed
 * or no success for > 1.5× interval; ok otherwise. */
export function sourceHealth(status: SourceStatus, lastAttemptOk: boolean | null): Health {
	if (status.stale) return 'down';
	const late =
		status.age_s !== null &&
		status.expected_interval_s !== null &&
		status.age_s > 1.5 * status.expected_interval_s;
	return late || lastAttemptOk === false ? 'delayed' : 'ok';
}

export function formatInterval(seconds: number | null): string {
	if (!seconds) return '—';
	return seconds < 3600 ? `co ${Math.round(seconds / 60)} min` : `co ${seconds / 3600} godz.`;
}

/** Zoom from which every event is drawn; below it, layers use `overviewMinSeverity`. */
export const DETAIL_ZOOM = 7.5;

/** Severity threshold actually applied to a layer at a given zoom. */
export function effectiveMinSeverity(layer: LayerDef, userMin: number, zoom: number): number {
	const overview = zoom < DETAIL_ZOOM ? (layer.overviewMinSeverity ?? 0) : 0;
	return Math.max(userMin, overview);
}
