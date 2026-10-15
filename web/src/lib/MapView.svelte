<script lang="ts">
	import { onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Map as MlMap, GeoJSONSource, MapMouseEvent } from 'maplibre-gl';
	import type { FeatureCollection, Geometry } from 'geojson';
	import { bbox, type MapViewState } from '#lib/geo.ts';
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
	}
	let { data, visible, minSeverity, onselect, initialView, onmove, focus }: Props = $props();

	let container: HTMLDivElement;
	let map: MlMap | undefined = $state();
	let loaded = $state(false);

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
	}

	const darkQuery =
		typeof window !== 'undefined' ? matchMedia('(prefers-color-scheme: dark)') : null;
	// OSM has no dark raster style: dim the tiles instead.
	const basemapPaint = (dark: boolean) => ({
		'raster-brightness-max': dark ? 0.55 : 1,
		'raster-saturation': dark ? -0.5 : 0
	});

	onMount(() => {
		let cancelled = false;
		const onScheme = () => {
			if (!map) return;
			for (const [k, v] of Object.entries(basemapPaint(darkQuery?.matches ?? false)))
				map.setPaintProperty('osm', k as 'raster-brightness-max', v);
		};
		import('maplibre-gl').then(
			({ Map: MapCtor, NavigationControl, AttributionControl, setWorkerUrl }) => {
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
								paint: basemapPaint(darkQuery?.matches ?? false)
							}
						]
					}
				});
				m.addControl(new NavigationControl({ showCompass: false }), 'bottom-right');
				m.addControl(
					new AttributionControl({
						compact: true,
						customAttribution: [
							'Dane: IMGW-PIB (przetworzone), GIOŚ, NASA FIRMS, GDDKiA, GUGiK',
							'<a href="/zrodla">źródła i licencje</a>'
						]
					}),
					'bottom-left'
				);
				m.on('load', async () => {
					await loadIcons(m);
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
									'circle-stroke-color': '#ffffff'
								}
							});
						}
						for (const id of layerIds(layer)) {
							m.on('mouseenter', id, () => (m.getCanvas().style.cursor = 'pointer'));
							m.on('mouseleave', id, () => (m.getCanvas().style.cursor = ''));
						}
					}
					m.on('click', (e: MapMouseEvent) => {
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
					loaded = true;
				});
				map = m;
			}
		);
		darkQuery?.addEventListener('change', onScheme);
		return () => {
			cancelled = true;
			darkQuery?.removeEventListener('change', onScheme);
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
		if (!map || !loaded || !focus) return;
		const box = bbox(focus);
		if (box) map.fitBounds(box, { padding: 60, maxZoom: 11, duration: 600 });
	});
</script>

<div class="map" bind:this={container} role="region" aria-label="Mapa zdarzeń w Polsce"></div>

<style>
	.map {
		position: absolute;
		inset: var(--header-h) 0 0 0;
	}
</style>
