<script lang="ts">
	import { onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Map as MlMap, GeoJSONSource, MapMouseEvent } from 'maplibre-gl';
	import type { Feature, FeatureCollection, Geometry } from 'geojson';
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
	import {
		SAT_GROUPS,
		parseEntries,
		positionsAt,
		type SatEntry,
		type SatProps,
		type SatTle
	} from '#lib/satellites.ts';

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
		/** TLEs of the satellites to show (already filtered to enabled groups). */
		satelliteTles?: SatTle[];
		onsatellite?: (sat: SatProps) => void;
		/** Count of satellites currently over Poland, emitted each tick. */
		onsatcount?: (n: number) => void;
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
		onaircraft,
		satelliteTles = [],
		onsatellite,
		onsatcount
	}: Props = $props();

	// Parsed SGP4 records; rebuilt only when the TLE set changes, then propagated every second.
	// Rebuilt only when the TLE set changes, then propagated every second.
	const satEntries: SatEntry[] = $derived(parseEntries(satelliteTles));
	let satTimer: ReturnType<typeof setInterval> | undefined;

	/** Propagate ~every second (a LEO satellite moves ~7.5 km/s, so slower looks jumpy);
	 *  on phones, ease off to 2 s when many satellites are tracked (e.g. Starlink on). */
	function startSatellites(m: MlMap): void {
		const phone = typeof matchMedia !== 'undefined' && matchMedia('(max-width: 719px)').matches;
		const tick = () => {
			const src = m.getSource('satellites') as GeoJSONSource | undefined;
			if (src) {
				const fc = positionsAt(satEntries, new Date(), POLAND_MAX_BOUNDS);
				src.setData(fc);
				onsatcount?.(fc.features.length);
			}
			satTimer = setTimeout(tick, phone && satEntries.length > 2000 ? 2000 : 1000);
		};
		tick();
	}

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

	const satColor = [
		'match',
		['get', 'group'],
		...SAT_GROUPS.flatMap((g) => [g.id, g.color]),
		'#d8dee6'
	] as unknown as string;

	const aircraftColor = [
		'match',
		['get', 'class'],
		...AIRCRAFT_CLASSES.flatMap((c) => [c.id, c.color]),
		'#d8dee6'
	] as unknown as string;

	// Rough box around Poland for the satellite filter (the map's own limits are computed per
	// screen size in lockToPoland).
	const POLAND_MAX_BOUNDS: [[number, number], [number, number]] = [
		[12.2, 48.4],
		[26.0, 55.6]
	];

	/** Room for the floating layers panel on wide screens, so it doesn't cover western Poland. */
	const fitPadding = (width: number) => {
		const side = width >= 1000 ? 340 : 16;
		return { top: 24, bottom: 24, left: side, right: 16 };
	};

	/** Whole Poland in frame is both the start view and the furthest zoom-out; panning can't
	 * leave that frame. Recomputed on resize (e.g. phone rotation). */
	function lockToPoland(m: MlMap, jumpToPoland: boolean) {
		const camera = m.cameraForBounds(POLAND, { padding: fitPadding(m.getContainer().clientWidth) });
		if (!camera?.center || camera.zoom === undefined) return;
		const previous = { center: m.getCenter(), zoom: m.getZoom() };
		m.setMaxBounds(null);
		m.setMinZoom(null);
		m.jumpTo(camera);
		const frame = m.getBounds();
		if (!jumpToPoland) m.jumpTo(previous);
		m.setMinZoom(camera.zoom);
		m.setMaxBounds(frame);
	}

	/** Keep the outside-Poland mask and the border above every data layer. */
	function raiseFrame(m: MlMap) {
		for (const id of ['poland-mask', 'poland-border-glow', 'poland-border'])
			if (m.getLayer(id)) m.moveLayer(id);
	}
	const MASK_COLOR = '#05080c';
	const BORDER_COLOR = '#5ec8d8';

	/** World box with Poland punched out, to dim everything outside the country. */
	function maskFeature(poland: Geometry): Feature {
		// Covers all of Europe – far beyond the locked view, so its edges are never seen.
		const world = [
			[-20, 30],
			[45, 30],
			[45, 72],
			[-20, 72],
			[-20, 30]
		];
		const outerRings =
			poland.type === 'MultiPolygon'
				? poland.coordinates.map((poly) => poly[0])
				: poland.type === 'Polygon'
					? [poland.coordinates[0]]
					: [];
		return {
			type: 'Feature',
			properties: {},
			geometry: { type: 'Polygon', coordinates: [world, ...outerRings] }
		};
	}

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
						: { bounds: POLAND, fitBoundsOptions: { padding: fitPadding(container.clientWidth) } }),
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
							'Dane: IMGW-PIB (przetworzone), GIOŚ, NASA FIRMS, GDDKiA, GUGiK, adsb.lol (ODbL), CelesTrak',
							'<a href="/zrodla">źródła i licencje</a>'
						]
					}),
					'bottom-left'
				);
				m.on('load', async () => {
					await loadIcons(m);
					// Poland outline: dim everything else and draw a crisp, softly glowing border.
					try {
						const poland = (await (await fetch('/poland.geojson')).json()) as Geometry;
						m.addSource('poland-outline', { type: 'geojson', data: poland });
						m.addSource('poland-mask', { type: 'geojson', data: maskFeature(poland) });
						m.addLayer({
							id: 'poland-mask',
							type: 'fill',
							source: 'poland-mask',
							// Opaque: nothing outside Poland is shown (raised above data in raiseFrame).
							paint: { 'fill-color': MASK_COLOR, 'fill-opacity': 1 }
						});
						m.addLayer({
							id: 'poland-border-glow',
							type: 'line',
							source: 'poland-outline',
							paint: {
								'line-color': BORDER_COLOR,
								'line-width': 6,
								'line-blur': 6,
								'line-opacity': 0.25
							}
						});
						m.addLayer({
							id: 'poland-border',
							type: 'line',
							source: 'poland-outline',
							paint: { 'line-color': BORDER_COLOR, 'line-width': 1.4, 'line-opacity': 0.9 }
						});
					} catch {
						// no outline is fine: the map still works, just without the Poland frame
					}
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
					// Satellites on the very top; positions recomputed every second (see startSatellites).
					m.addSource('satellites', {
						type: 'geojson',
						data: { type: 'FeatureCollection', features: [] }
					});
					m.addLayer({
						id: 'satellites',
						type: 'circle',
						source: 'satellites',
						paint: {
							'circle-color': satColor,
							'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 2.5, 9, 4.5],
							'circle-stroke-width': 1,
							'circle-stroke-color': 'rgba(230,237,243,0.7)',
							'circle-opacity': 0.95
						}
					});
					m.on('mouseenter', 'satellites', () => (m.getCanvas().style.cursor = 'pointer'));
					m.on('mouseleave', 'satellites', () => (m.getCanvas().style.cursor = ''));
					m.on('click', (e: MapMouseEvent) => {
						const sat = m.queryRenderedFeatures(e.point, { layers: ['satellites'] })[0];
						if (sat) {
							onsatellite?.(sat.properties as unknown as SatProps);
							return;
						}
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
					raiseFrame(m);
					lockToPoland(m, !initialView);
					m.on('resize', () => lockToPoland(m, false));
					loaded = true;
					startSatellites(m);
				});
				map = m;
			}
		);
		return () => {
			cancelled = true;
			if (satTimer) clearTimeout(satTimer);
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
		raiseFrame(m);
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
