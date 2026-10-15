<script lang="ts">
	import { onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Map as MlMap, GeoJSONSource, MapMouseEvent } from 'maplibre-gl';
	import type { FeatureCollection, Geometry } from 'geojson';
	import { bbox, type MapPlace, type MapViewState } from '#lib/geo.ts';
	// Emitted as a build asset: maplibre would otherwise look for the worker next to its chunk.
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
	import {
		DROUGHT_COLOR,
		LAYERS,
		ROAD_ICONS,
		layerFeatures,
		SEVERITY_COLORS,
		type EventProps,
		type EventType,
		type LayerDef
	} from '#lib/events.ts';
	import {
		AIRCRAFT_CLASSES,
		PLANE_SVG,
		type AircraftClass,
		type AircraftCollection,
		type AircraftProps
	} from '#lib/aircraft.ts';

	interface Props {
		data: Partial<Record<EventType, FeatureCollection>>;
		/** Keyed by layer id. */
		visible: Record<string, boolean>;
		/** Hide events below this severity (0 = show all). */
		minSeverity: number;
		onselect: (events: EventProps[]) => void;
		/** Start view (e.g. from a shared link); default: whole Poland. */
		initialView?: MapViewState | null;
		/** Called when the view settles, to keep the URL shareable. */
		onmove?: (view: MapViewState) => void;
		/** Geometry to zoom to (a shared event). */
		focus?: Geometry | null;
		/** User's places ("Moja okolica"); drawn locally, never sent anywhere. */
		places?: MapPlace[];
		/** Latest aircraft snapshot and which classes to show. */
		aircraft?: AircraftCollection;
		aircraftVisible?: Record<AircraftClass, boolean>;
		onaircraft?: (aircraft: AircraftProps) => void;
	}
	let {
		data,
		visible,
		minSeverity,
		onselect,
		initialView,
		onmove,
		focus,
		places = [],
		aircraft,
		aircraftVisible,
		onaircraft
	}: Props = $props();

	let MarkerCtor: typeof import('maplibre-gl').Marker | undefined;
	let markers: import('maplibre-gl').Marker[] = [];

	let container: HTMLDivElement;
	let map: MlMap | undefined = $state();
	let loaded = $state(false);

	// Places: violet, outside the severity palette so a place is never mistaken for a warning.
	const PLACE_COLOR = '#6f42c1';
	const POLAND: [[number, number], [number, number]] = [
		[14.07, 49.0],
		[24.15, 54.84]
	];
	const severityColor = [
		'match',
		['get', 'severity'],
		0,
		SEVERITY_COLORS[0],
		1,
		SEVERITY_COLORS[1],
		2,
		SEVERITY_COLORS[2],
		SEVERITY_COLORS[3]
	] as unknown as string;

	const layerIds = (layer: LayerDef) => {
		if (layer.kind === 'area')
			return layer.outline ? [`${layer.id}-line`] : [`${layer.id}-fill`, `${layer.id}-line`];
		return [layer.kind === 'icon' ? `${layer.id}-icon` : `${layer.id}-circle`];
	};
	// Draw order: areas, then points, then road icons on top.
	const DRAW_ORDER = { area: 0, point: 1, icon: 2 };

	async function loadIcons(m: MlMap) {
		await Promise.all(
			ROAD_ICONS.map(async ({ severity, svg }) => {
				const img = new Image(48, 48); // 2× for sharp icons on high-DPI screens
				img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
				await img.decode();
				m.addImage(`road-${severity}`, img, { pixelRatio: 2 });
			})
		);
		const plane = new Image(48, 48);
		plane.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(PLANE_SVG)}`;
		await plane.decode();
		m.addImage('plane', plane, { pixelRatio: 2, sdf: true }); // sdf: tinted per class
	}

	const aircraftColor = [
		'match',
		['get', 'class'],
		...AIRCRAFT_CLASSES.flatMap((c) => [c.id, c.color]),
		'#d8dee6'
	] as unknown as string;

	// OSM has no dark raster style: invert the tiles (brightness-min > max), rotate the
	// hue back so water stays blue, and mute the colours so event layers stand out.
	const BASEMAP_PAINT = {
		'raster-brightness-min': 0.92,
		'raster-brightness-max': 0.05,
		'raster-hue-rotate': 180,
		'raster-saturation': -0.9,
		'raster-contrast': -0.05
	};

	/** Cursor (or map centre on touch) readout, e.g. "52.2297°N 21.0122°E". */
	let cursor = $state('');
	let zoomLevel = $state('');
	const fmt = (lng: number, lat: number) =>
		`${Math.abs(lat).toFixed(4)}°${lat >= 0 ? 'N' : 'S'}  ${Math.abs(lng).toFixed(4)}°${lng >= 0 ? 'E' : 'W'}`;

	onMount(() => {
		let cancelled = false;
		import('maplibre-gl').then(
			({ Map: MapCtor, Marker, NavigationControl, AttributionControl, setWorkerUrl }) => {
				MarkerCtor = Marker;
				if (cancelled) return;
				setWorkerUrl(workerUrl);
				const m = new MapCtor({
					container,
					...(initialView
						? { center: initialView.center, zoom: initialView.zoom }
						: { bounds: POLAND, fitBoundsOptions: { padding: 16 } }),
					attributionControl: false,
					style: {
						version: 8,
						sources: {
							osm: {
								type: 'raster',
								tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
								tileSize: 256,
								maxzoom: 19,
								attribution: '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a>'
							}
						},
						layers: [
							{
								id: 'osm',
								type: 'raster',
								source: 'osm',
								paint: BASEMAP_PAINT
							}
						]
					}
				});
				m.addControl(new NavigationControl({ showCompass: false }), 'bottom-right');
				m.addControl(
					new AttributionControl({
						compact: true,
						customAttribution: [
							'Dane: IMGW-PIB (przetworzone), GIOŚ, NASA FIRMS, GDDKiA, GUGiK, adsb.lol (ODbL)',
							'<a href="/zrodla">źródła i licencje</a>'
						]
					}),
					'bottom-left'
				);
				m.on('load', async () => {
					await loadIcons(m);
					m.addSource('places', {
						type: 'geojson',
						data: { type: 'FeatureCollection', features: [] }
					});
					for (const layer of [...LAYERS].sort((a, b) => DRAW_ORDER[a.kind] - DRAW_ORDER[b.kind])) {
						m.addSource(layer.id, {
							type: 'geojson',
							data: { type: 'FeatureCollection', features: [] }
						});
						if (layer.kind === 'area') {
							if (!layer.outline)
								m.addLayer({
									id: `${layer.id}-fill`,
									type: 'fill',
									source: layer.id,
									// Low opacity: overlapping warnings stack up.
									paint: { 'fill-color': severityColor, 'fill-opacity': 0.12 }
								});
							m.addLayer({
								id: `${layer.id}-line`,
								type: 'line',
								source: layer.id,
								paint: layer.outline
									? { 'line-color': DROUGHT_COLOR, 'line-width': 2, 'line-dasharray': [3, 2] }
									: layer.dotted
										? { 'line-color': severityColor, 'line-width': 1.5, 'line-dasharray': [1, 1.5] }
										: { 'line-color': severityColor, 'line-width': 1.5 }
							});
						} else if (layer.kind === 'icon') {
							m.addLayer({
								id: `${layer.id}-icon`,
								type: 'symbol',
								source: layer.id,
								layout: {
									'icon-image': ['concat', 'road-', ['to-string', ['get', 'severity']]],
									'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.6, 9, 1],
									'icon-allow-overlap': true,
									// closures drawn on top of roadworks
									'symbol-sort-key': ['get', 'severity']
								}
							});
						} else {
							m.addLayer({
								id: `${layer.id}-circle`,
								type: 'circle',
								source: layer.id,
								paint: {
									'circle-color': severityColor,
									// Small at country zoom (hundreds of stations), larger when zoomed in.
									'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 3.5, 9, 7],
									'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 5, 1, 9, 1.5],
									'circle-stroke-color': '#0a0d12'
								}
							});
						}
						for (const id of layerIds(layer)) {
							m.on('mouseenter', id, () => (m.getCanvas().style.cursor = 'pointer'));
							m.on('mouseleave', id, () => (m.getCanvas().style.cursor = ''));
						}
					}
					// Aircraft on top of everything; rotated to their track, fixed to the map.
					m.addSource('aircraft', {
						type: 'geojson',
						data: { type: 'FeatureCollection', features: [] }
					});
					m.addLayer({
						id: 'aircraft',
						type: 'symbol',
						source: 'aircraft',
						layout: {
							'icon-image': 'plane',
							'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.55, 9, 0.9],
							'icon-rotate': ['coalesce', ['get', 'track'], 0],
							'icon-rotation-alignment': 'map',
							'icon-allow-overlap': true
						},
						paint: {
							'icon-color': aircraftColor,
							'icon-halo-color': '#0a0d12',
							'icon-halo-width': 1
						}
					});
					m.on('mouseenter', 'aircraft', () => (m.getCanvas().style.cursor = 'pointer'));
					m.on('mouseleave', 'aircraft', () => (m.getCanvas().style.cursor = ''));
					m.on('click', (e: MapMouseEvent) => {
						// A plane over a warning area: the plane is what was aimed at.
						const plane = m.queryRenderedFeatures(e.point, { layers: ['aircraft'] })[0];
						if (plane) {
							onaircraft?.(plane.properties as AircraftProps);
							return;
						}
						const ids = LAYERS.filter((l) => visible[l.id]).flatMap(layerIds);
						const hits = m.queryRenderedFeatures(e.point, { layers: ids });
						// One feature per event: a polygon can be hit by both its fill and line layer.
						const events = hits
							.map((f) => f.properties as EventProps)
							.filter((p, i, all) => all.findIndex((q) => q.id === p.id) === i);
						onselect(
							events.sort(
								(a, b) =>
									b.severity - a.severity || (b.valid_from ?? '').localeCompare(a.valid_from ?? '')
							)
						);
					});
					// Any settled view (gesture or zoom-to-event) is what a shared link should show.
					m.on('moveend', () => {
						const c = m.getCenter();
						onmove?.({ center: [c.lng, c.lat], zoom: m.getZoom() });
					});
					const showCenter = () => {
						const c = m.getCenter();
						cursor = fmt(c.lng, c.lat);
						zoomLevel = m.getZoom().toFixed(1);
					};
					m.on('move', showCenter);
					m.on('mousemove', (e: MapMouseEvent) => (cursor = fmt(e.lngLat.lng, e.lngLat.lat)));
					m.on('mouseout', showCenter);
					showCenter();
					loaded = true;
				});
				map = m;
			}
		);
		return () => {
			cancelled = true;
			map?.remove();
		};
	});

	$effect(() => {
		if (!map || !loaded) return;
		for (const layer of LAYERS) {
			const fc = layerFeatures(layer, data[layer.type]);
			if (fc) (map.getSource(layer.id) as GeoJSONSource).setData(fc);
			for (const id of layerIds(layer)) {
				map.setLayoutProperty(id, 'visibility', visible[layer.id] ? 'visible' : 'none');
				// Filtered features are not rendered, so clicks don't hit them either.
				map.setFilter(id, ['>=', ['get', 'severity'], minSeverity]);
			}
		}
	});

	$effect(() => {
		if (!map || !loaded) return;
		if (aircraft) (map.getSource('aircraft') as GeoJSONSource).setData(aircraft);
		const shown = AIRCRAFT_CLASSES.filter((c) => aircraftVisible?.[c.id] ?? true).map((c) => c.id);
		map.setFilter('aircraft', ['in', ['get', 'class'], ['literal', shown]]);
	});

	$effect(() => {
		if (!map || !loaded || !focus) return;
		const box = bbox(focus);
		if (box) map.fitBounds(box, { padding: 60, maxZoom: 11, duration: 600 });
	});

	$effect(() => {
		const m = map;
		if (!m || !loaded || !MarkerCtor) return;
		// Outline of each place's powiat, drawn above event areas.
		if (!m.getLayer('places-line'))
			m.addLayer({
				id: 'places-line',
				type: 'line',
				source: 'places',
				paint: { 'line-color': PLACE_COLOR, 'line-width': 2.5, 'line-opacity': 0.9 }
			});
		(m.getSource('places') as GeoJSONSource).setData({
			type: 'FeatureCollection',
			features: places
				.filter((p) => p.area)
				.map((p) => ({ type: 'Feature', properties: {}, geometry: p.area! }))
		});
		for (const marker of markers) marker.remove();
		markers = places.map((p) => {
			const el = document.createElement('button');
			el.type = 'button';
			el.className = 'place-pin';
			el.textContent = `📍 ${p.name}`; // textContent: user-typed names are never HTML
			el.setAttribute('aria-label', `Twoje miejsce: ${p.name}. Przybliż mapę.`);
			el.addEventListener('click', (e) => {
				e.stopPropagation(); // don't open event details under the pin
				const box = p.area ? bbox(p.area) : null;
				if (box) m.fitBounds(box, { padding: 60, maxZoom: 11 });
				else m.flyTo({ center: p.lngLat, zoom: 11 });
			});
			return new MarkerCtor!({ element: el, anchor: 'bottom' }).setLngLat(p.lngLat).addTo(m);
		});
	});
</script>

<div
	class="map"
	style:--place={PLACE_COLOR}
	bind:this={container}
	role="region"
	aria-label="Mapa zdarzeń w Polsce"
></div>
{#if cursor}
	<p class="readout" aria-hidden="true">{cursor}<span>Z {zoomLevel}</span></p>
{/if}

<style>
	.map {
		position: absolute;
		inset: var(--header-h) 0 0 0;
	}
	.readout {
		position: absolute;
		right: 3.25rem;
		bottom: 0.6rem;
		z-index: 4;
		margin: 0;
		padding: 0.2rem 0.5rem;
		font-family: var(--mono);
		font-size: 0.72rem;
		font-variant-numeric: tabular-nums;
		white-space: pre;
		color: var(--muted);
		background: var(--panel);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		pointer-events: none;
	}
	.readout span {
		margin-left: 0.75rem;
		padding-left: 0.75rem;
		border-left: 1px solid var(--border);
	}
	@media (max-width: 719px) {
		.readout {
			display: none;
		}
	}
	/* Marker elements are created outside Svelte, hence :global. */
	.map :global(.place-pin) {
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		padding: 0.2rem 0.55rem;
		border-radius: var(--radius);
		border: 1px solid #fff;
		background: var(--place);
		color: #fff;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
		cursor: pointer;
		white-space: nowrap;
	}
</style>
