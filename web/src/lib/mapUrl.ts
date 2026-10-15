// Shareable map state in the URL: /?l=weather_warning,road_incident&min=2&c=19.94,50.06&z=9&e=<id>
import type { MapViewState } from './geo';

export interface MapUrlState {
	/** Visible layer ids; undefined = app defaults. */
	layers?: string[];
	minSeverity?: number;
	view?: MapViewState;
	/** Event to open (from a shared /e/{id} link). */
	event?: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseMapUrl(params: URLSearchParams, knownLayers: string[]): MapUrlState {
	const state: MapUrlState = {};
	const layers = params.get('l');
	if (layers !== null) state.layers = layers.split(',').filter((l) => knownLayers.includes(l));
	const min = Number(params.get('min'));
	if (params.has('min') && Number.isInteger(min) && min >= 0 && min <= 3) state.minSeverity = min;
	const [lon, lat] = (params.get('c') ?? '').split(',').map(Number);
	const zoom = Number(params.get('z'));
	if (
		Number.isFinite(lon) &&
		Number.isFinite(lat) &&
		params.has('z') &&
		Number.isFinite(zoom) &&
		Math.abs(lon) <= 180 &&
		Math.abs(lat) <= 90 &&
		zoom >= 0 &&
		zoom <= 20
	)
		state.view = { center: [lon, lat], zoom };
	const event = params.get('e');
	if (event && UUID.test(event)) state.event = event;
	return state;
}

export function buildMapUrl(state: MapUrlState): string {
	const p = new URLSearchParams();
	if (state.layers) p.set('l', state.layers.join(','));
	if (state.minSeverity) p.set('min', String(state.minSeverity));
	if (state.view) {
		p.set('c', state.view.center.map((v) => v.toFixed(4)).join(','));
		p.set('z', state.view.zoom.toFixed(2));
	}
	if (state.event) p.set('e', state.event);
	const query = p.toString().replaceAll('%2C', ',');
	return query ? `?${query}` : '';
}
