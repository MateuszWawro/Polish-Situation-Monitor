// Shared types and presentation helpers for events from our API (never from sources directly).

export type EventType =
	'weather_warning' | 'hydro_warning' | 'air_quality' | 'fire_hotspot' | 'road_incident';
export type SourceId = 'imgw_meteo' | 'imgw_hydro' | 'gios' | 'firms' | 'gddkia';

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
}

export interface SourceStatus {
	source: SourceId;
	last_success_at: string | null;
	last_error: string | null;
	expected_interval_s: number | null;
	age_s: number | null;
	stale: boolean;
}

export interface LayerDef {
	type: EventType;
	label: string;
	source: SourceId;
	sourceName: string;
	kind: 'area' | 'point' | 'icon';
}

export const LAYERS: LayerDef[] = [
	{
		type: 'weather_warning',
		label: 'Ostrzeżenia meteo',
		source: 'imgw_meteo',
		sourceName: 'IMGW-PIB',
		kind: 'area'
	},
	{
		type: 'hydro_warning',
		label: 'Ostrzeżenia hydro',
		source: 'imgw_hydro',
		sourceName: 'IMGW-PIB',
		kind: 'area'
	},
	{
		type: 'air_quality',
		label: 'Jakość powietrza',
		source: 'gios',
		sourceName: 'GIOŚ',
		kind: 'point'
	},
	{
		type: 'fire_hotspot',
		label: 'Punkty cieplne (pożary)',
		source: 'firms',
		sourceName: 'NASA FIRMS',
		kind: 'point'
	},
	{ type: 'road_incident', label: 'Drogi', source: 'gddkia', sourceName: 'GDDKiA', kind: 'icon' }
];

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
