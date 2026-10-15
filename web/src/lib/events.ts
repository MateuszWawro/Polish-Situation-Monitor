// Shared types and presentation helpers for events from our API (never from sources directly).

export type EventType = 'weather_warning' | 'hydro_warning' | 'air_quality' | 'fire_hotspot';
export type SourceId = 'imgw_meteo' | 'imgw_hydro' | 'gios' | 'firms';

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
	kind: 'area' | 'point';
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
	}
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
