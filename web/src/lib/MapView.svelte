<script lang="ts">
	import { onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Map as MlMap, GeoJSONSource, MapMouseEvent } from 'maplibre-gl';
	import type { FeatureCollection } from 'geojson';
	// Emitted as a build asset: maplibre would otherwise look for the worker next to its chunk.
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
	import {
		LAYERS,
		ROAD_ICONS,
		SEVERITY_COLORS,
		type EventProps,
		type EventType
	} from '#lib/events.ts';

	interface Props {
		data: Partial<Record<EventType, FeatureCollection>>;
		visible: Record<EventType, boolean>;
		onselect: (events: EventProps[]) => void;
	}
	let { data, visible, onselect }: Props = $props();

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

	const layerIds = (type: EventType) => {
		const kind = LAYERS.find((l) => l.type === type)?.kind;
		if (kind === 'area') return [`${type}-fill`, `${type}-line`];
		return [kind === 'icon' ? `${type}-icon` : `${type}-circle`];
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
					bounds: POLAND,
					fitBoundsOptions: { padding: 16 },
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
						m.addSource(layer.type, {
							type: 'geojson',
							data: { type: 'FeatureCollection', features: [] }
						});
						if (layer.kind === 'area') {
							m.addLayer({
								id: `${layer.type}-fill`,
								type: 'fill',
								source: layer.type,
								// Low opacity: overlapping warnings (e.g. dozens of drought areas) stack up.
								paint: { 'fill-color': severityColor, 'fill-opacity': 0.08 }
							});
							m.addLayer({
								id: `${layer.type}-line`,
								type: 'line',
								source: layer.type,
								paint: { 'line-color': severityColor, 'line-width': 1.5 }
							});
						} else if (layer.kind === 'icon') {
							m.addLayer({
								id: `${layer.type}-icon`,
								type: 'symbol',
								source: layer.type,
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
								id: `${layer.type}-circle`,
								type: 'circle',
								source: layer.type,
								paint: {
									'circle-color': severityColor,
									// Small at country zoom (hundreds of stations), larger when zoomed in.
									'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 3.5, 9, 7],
									'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 5, 1, 9, 1.5],
									'circle-stroke-color': '#ffffff'
								}
							});
						}
						for (const id of layerIds(layer.type)) {
							m.on('mouseenter', id, () => (m.getCanvas().style.cursor = 'pointer'));
							m.on('mouseleave', id, () => (m.getCanvas().style.cursor = ''));
						}
					}
					m.on('click', (e: MapMouseEvent) => {
						const ids = LAYERS.filter((l) => visible[l.type]).flatMap((l) => layerIds(l.type));
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
			const fc = data[layer.type];
			if (fc) (map.getSource(layer.type) as GeoJSONSource).setData(fc);
			for (const id of layerIds(layer.type))
				map.setLayoutProperty(id, 'visibility', visible[layer.type] ? 'visible' : 'none');
		}
	});
</script>

<div class="map" bind:this={container} role="region" aria-label="Mapa zdarzeń w Polsce"></div>

<style>
	.map {
		position: absolute;
		inset: var(--header-h) 0 0 0;
	}
</style>
