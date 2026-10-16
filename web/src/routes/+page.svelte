<script lang="ts">
	import { onMount } from 'svelte';
	import type { FeatureCollection, Geometry } from 'geojson';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { MapPlace, MapViewState } from '#lib/geo.ts';
	import { loadPlaces } from '#lib/places.ts';
	import { buildMapUrl, parseMapUrl } from '#lib/mapUrl.ts';
	import { shareLink } from '#lib/share.ts';
	import { getJson } from '#lib/offline.svelte.ts';
	import { poll } from '#lib/poll.ts';
	import MapSearch from '#lib/MapSearch.svelte';
	import { bboxPolygon, powiatBboxes } from '#lib/bboxes.ts';
	import type { PlaceHit } from '#lib/search.ts';
	import MapView from '#lib/MapView.svelte';
	import EventGroups from '#lib/EventGroups.svelte';
	import StaleBanner from '#lib/StaleBanner.svelte';
	import {
		DETAIL_ZOOM,
		LAYERS,
		effectiveMinSeverity,
		layerFeatures,
		ROAD_ICONS,
		SEVERITY_COLORS,
		SEVERITY_LABELS,
		timeAgo,
		type EventProps,
		type EventType,
		type LayerDef,
		type SourceStatus
	} from '#lib/events.ts';
	import {
		AIRCRAFT_CLASSES,
		countByClass,
		formatAltitude,
		formatSpeed,
		snapshotTime,
		type AircraftClass,
		type AircraftCollection,
		type AircraftProps
	} from '#lib/aircraft.ts';
	import {
		SAT_GROUPS,
		orbitalPeriodMin,
		type SatGroup,
		type SatProps,
		type SatTle
	} from '#lib/satellites.ts';

	const EVENTS_REFRESH_MS = 5 * 60_000;
	const STATUS_REFRESH_MS = 60_000;

	let data: Partial<Record<EventType, FeatureCollection>> = $state({});
	let visible = $state(
		Object.fromEntries(LAYERS.map((l) => [l.id, l.defaultVisible ?? true])) as Record<
			string,
			boolean
		>
	);
	let minSeverity = $state(0);
	let status: SourceStatus[] = $state([]);
	let selected: EventProps[] = $state([]);

	const AIRCRAFT_REFRESH_MS = 60_000;
	let aircraft: AircraftCollection | undefined = $state();
	let aircraftVisible: Record<AircraftClass, boolean> = $state({
		commercial: true,
		private: true,
		military: true
	});
	let plane: AircraftProps | null = $state(null);
	const aircraftCounts = $derived(countByClass(aircraft));

	const SAT_REFRESH_MS = 60 * 60_000; // TLE changes every few hours; one fetch per hour is plenty
	let satellitesVisible: Record<SatGroup, boolean> = $state(
		Object.fromEntries(SAT_GROUPS.map((g) => [g.id, g.default])) as Record<SatGroup, boolean>
	);
	let satTles: SatTle[] = $state([]);
	let satUpdatedAt: string | null = $state(null);
	let satOverPoland = $state(0);
	let satDetails: SatProps | null = $state(null);

	// Shared link state (?l=…&min=…&c=…&z=…&e=…). Read synchronously so the map starts there.
	const fromUrl =
		typeof window !== 'undefined'
			? parseMapUrl(
					new URLSearchParams(location.search),
					LAYERS.map((l) => l.id)
				)
			: {};
	let view: MapViewState | undefined = $state(fromUrl.view);
	let focus: Geometry | null = $state(null);
	/** Event opened from a shared link; kept in the URL while its details are open. */
	let linkedEvent: string | undefined = $state(fromUrl.event);
	let shareNote = $state('');

	async function shareView() {
		const result = await shareLink(location.href, 'Monitor sytuacyjny Polski – mapa');
		shareNote =
			result === 'copied' ? 'Skopiowano link' : result === 'failed' ? 'Nie udało się' : '';
		setTimeout(() => (shareNote = ''), 2500);
	}

	let myPlaces: MapPlace[] = $state([]);

	/** Pins and powiat outlines for "Moja okolica" places (all local to this device). */
	async function loadMyPlaces() {
		try {
			const places = await loadPlaces();
			if (!places.length) return;
			const boxes = await powiatBboxes();
			const center = (t: string): [number, number] => {
				const [w, s, e, n] = boxes[t] ?? [19, 52, 19, 52];
				return [(w + e) / 2, (s + n) / 2];
			};
			myPlaces = places.map((p) => ({
				id: p.id,
				name: p.name,
				lngLat: p.point ?? center(p.teryt)
			}));
			// Outlines need the full boundaries (~300 KB, browser-cached for a day).
			const powiaty: FeatureCollection = await (
				await fetch('/api/admin-units?level=powiat')
			).json();
			const shape = (t: string) => powiaty.features.find((f) => f.id === t)?.geometry;
			myPlaces = myPlaces.map((mp, i) => ({ ...mp, area: shape(places[i].teryt) }));
		} catch {
			// no places on the map is fine
		}
	}

	async function zoomToPlace(hit: PlaceHit) {
		try {
			const box = (await powiatBboxes())[hit.teryt];
			// Gminy have no geometry in the index: zoom to their powiat.
			if (box) focus = bboxPolygon(box);
		} catch {
			// map stays where it is
		}
	}

	async function openLinkedEvent(id: string) {
		try {
			const r = await fetch(`/api/events/${id}`);
			if (!r.ok) return;
			const feature = await r.json();
			selected = [feature.properties as EventProps];
			if (!fromUrl.view) focus = feature.geometry;
		} catch {
			// a broken link just shows the map
		}
	}
	const MIN_SEVERITY_KEY = 'psm.minSeverity';
	/** Zoomed in past DETAIL_ZOOM (reported by the map); below it minor events are hidden. */
	let detailed = $state(true);
	/** What the map actually draws for a layer at the current zoom. */
	const countFrom = (layer: LayerDef, fc: FeatureCollection | undefined) => {
		const min = effectiveMinSeverity(layer, minSeverity, detailed ? DETAIL_ZOOM : 0);
		return fc?.features.filter((f) => (f.properties?.severity ?? 0) >= min).length;
	};
	const hiddenInOverview = $derived(
		!detailed && LAYERS.some((l) => visible[l.id] && (l.overviewMinSeverity ?? 0) > minSeverity)
	);

	function setMinSeverity(value: number) {
		minSeverity = value;
		selected = [];
		try {
			localStorage.setItem(MIN_SEVERITY_KEY, String(value)); // per-viewer convenience only
		} catch {
			// storage blocked (private mode): the filter still works for this visit
		}
	}
	let loadError = $state(false);
	let panelOpen = $state(false);
	let now = $state(Date.now());

	const statusOf = (source: string) => status.find((s) => s.source === source);

	let urlReady = false;
	$effect(() => {
		const defaults = LAYERS.every((l) => visible[l.id] === (l.defaultVisible ?? true));
		const url = buildMapUrl({
			layers: defaults ? undefined : LAYERS.filter((l) => visible[l.id]).map((l) => l.id),
			minSeverity,
			view,
			event: selected.length ? linkedEvent : undefined
		});
		// Shallow + replace: keeps the link shareable without navigating or filling history.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolved path + query
		if (urlReady) goto(`${resolve('/')}${url}`, { shallow: true, replace: true });
	});

	async function loadEvents() {
		const results = await Promise.allSettled(
			[...new Set(LAYERS.map((l) => l.type))].map(async (type) => {
				data[type] = await getJson<FeatureCollection>(`/api/events?type=${type}`);
			})
		);
		loadError = results.some((r) => r.status === 'rejected');
	}

	async function loadSatellites() {
		const groups = SAT_GROUPS.filter((g) => satellitesVisible[g.id]).map((g) => g.id);
		if (!groups.length) {
			satTles = [];
			return;
		}
		try {
			const r = await fetch(`/api/satellites?groups=${groups.join(',')}`);
			if (r.ok) {
				const body = await r.json();
				satTles = body.satellites;
				satUpdatedAt = body.updated_at;
			}
		} catch {
			// keep the last TLE set; positions keep being propagated from it
		}
	}

	async function loadAircraft() {
		try {
			// Plain fetch, not the offline cache: positions from an old visit would mislead.
			const r = await fetch('/api/aircraft');
			if (r.ok) aircraft = await r.json();
		} catch {
			// keep the last snapshot; it is labelled with its age
		}
	}

	async function loadStatus() {
		try {
			status = await getJson<SourceStatus[]>('/api/sources/status');
		} catch {
			// keep the previous status; the events error banner covers a dead API
		}
	}

	onMount(() => {
		panelOpen = matchMedia('(min-width: 720px)').matches;
		try {
			const saved = Number(localStorage.getItem(MIN_SEVERITY_KEY));
			if (saved >= 0 && saved <= 3) minSeverity = saved;
		} catch {
			// storage blocked: default filter
		}
		// A shared link wins over local preferences.
		if (fromUrl.layers) for (const l of LAYERS) visible[l.id] = fromUrl.layers.includes(l.id);
		if (fromUrl.minSeverity !== undefined) minSeverity = fromUrl.minSeverity;
		if (fromUrl.event) openLinkedEvent(fromUrl.event);
		loadMyPlaces();
		urlReady = true;
		loadEvents();
		loadStatus();
		loadAircraft();
		loadSatellites();
		return poll([
			{ run: loadAircraft, everyMs: AIRCRAFT_REFRESH_MS },
			{ run: loadSatellites, everyMs: SAT_REFRESH_MS },
			{ run: loadEvents, everyMs: EVENTS_REFRESH_MS },
			{ run: loadStatus, everyMs: STATUS_REFRESH_MS },
			{ run: () => (now = Date.now()), everyMs: 30_000 }
		]);
	});
</script>

<svelte:head><title>Monitor sytuacyjny Polski – mapa</title></svelte:head>

<MapView
	{data}
	{visible}
	{minSeverity}
	{focus}
	places={myPlaces}
	initialView={fromUrl.view}
	onmove={(v) => (view = v)}
	onselect={(events) => {
		selected = events;
		plane = null;
		linkedEvent = undefined;
	}}
	{aircraft}
	{aircraftVisible}
	onaircraft={(a) => {
		plane = a;
		selected = [];
		satDetails = null;
	}}
	satelliteTles={satTles}
	onsatellite={(sat) => {
		satDetails = sat;
		selected = [];
		plane = null;
	}}
	onsatcount={(n) => (satOverPoland = n)}
	ondetailchange={(d) => (detailed = d)}
/>

<div class="banners" aria-live="polite">
	{#if loadError}
		<p class="banner">Nie udało się pobrać części danych. Spróbujemy ponownie za kilka minut.</p>
	{/if}
	<StaleBanner {status} {now} />
</div>

<aside class="panel" aria-label="Wyszukiwanie, warstwy i legenda">
	<MapSearch onpick={zoomToPlace} />
	<button
		class="panel-toggle"
		aria-expanded={panelOpen}
		aria-controls="layers-body"
		onclick={() => (panelOpen = !panelOpen)}
	>
		<span class="label">Warstwy i legenda</span>
		<span class="chev" aria-hidden="true">{panelOpen ? '−' : '+'}</span>
	</button>
	<div id="layers-body" hidden={!panelOpen}>
		<fieldset class="min-sev">
			<legend class="label">Pokaż od stopnia</legend>
			<div class="segmented">
				{#each [0, 1, 2, 3] as level (level)}
					<label>
						<input
							type="radio"
							name="min-severity"
							value={level}
							checked={minSeverity === level}
							onchange={() => setMinSeverity(level)}
						/>
						<span>{level === 0 ? 'wszystko' : `${level}+`}</span>
					</label>
				{/each}
			</div>
			{#if hiddenInOverview}
				<p class="overview-note">
					Widok całego kraju: ukryto drobne zdarzenia (roboty drogowe, dobra jakość powietrza).
					Przybliż mapę, aby zobaczyć wszystkie.
				</p>
			{/if}
		</fieldset>
		<fieldset>
			<legend class="sr-only">Widoczne warstwy</legend>
			{#each LAYERS as layer (layer.id)}
				{@const st = statusOf(layer.source)}
				<label class="layer">
					<input type="checkbox" bind:checked={visible[layer.id]} />
					<span class="layer-body">
						<span class="layer-head">
							<strong>{layer.label}</strong>
							<span class="count mono"
								>{countFrom(layer, layerFeatures(layer, data[layer.type])) ?? '…'}</span
							>
						</span>
						{#if layer.note}<small>{layer.note}</small>{/if}
						<small class="src mono" class:stale={st?.stale} class:ok={st && !st.stale}>
							<span class="dot" aria-hidden="true"></span>{layer.sourceName} ·
							<span class="sr-only">aktualizacja:</span>
							{timeAgo(st?.last_success_at ?? null, now)}
						</small>
					</span>
				</label>
			{/each}
		</fieldset>
		<fieldset class="aircraft">
			<legend class="label">Samoloty</legend>
			{#each AIRCRAFT_CLASSES as cls (cls.id)}
				<label class="layer">
					<input type="checkbox" bind:checked={aircraftVisible[cls.id]} />
					<span class="layer-body">
						<span class="layer-head">
							<strong
								><span class="plane-dot" style:background={cls.color} aria-hidden="true"
								></span>{cls.label}</strong
							>
							<span class="count mono">{aircraft ? aircraftCounts[cls.id] : '…'}</span>
						</span>
						<small>{cls.note}</small>
					</span>
				</label>
			{/each}
			<small class="src mono" class:ok={!!aircraft?.features.length}>
				<span class="dot" aria-hidden="true"></span>adsb.lol ·
				<span class="sr-only">pozycje z:</span>
				{timeAgo(snapshotTime(aircraft), now)}
			</small>
		</fieldset>
		<fieldset class="aircraft">
			<legend class="label">Satelity nad Polską</legend>
			{#each SAT_GROUPS as grp (grp.id)}
				<label class="layer">
					<input
						type="checkbox"
						bind:checked={satellitesVisible[grp.id]}
						onchange={loadSatellites}
					/>
					<span class="layer-body">
						<span class="layer-head">
							<strong
								><span class="plane-dot sat" style:background={grp.color} aria-hidden="true"
								></span>{grp.label}</strong
							>
						</span>
						<small>{grp.note}</small>
					</span>
				</label>
			{/each}
			<small class="src mono" class:ok={satTles.length > 0}>
				<span class="dot" aria-hidden="true"></span>CelesTrak · {satOverPoland} na niebie ·
				<span class="sr-only">dane z:</span>
				{timeAgo(satUpdatedAt, now)}
			</small>
		</fieldset>
		<p class="label legend-title" aria-hidden="true">Legenda</p>
		<ul class="legend" aria-label="Legenda stopni">
			{#each SEVERITY_LABELS as label, i (label)}
				<li><span class="swatch" style:background={SEVERITY_COLORS[i]}></span>{label}</li>
			{/each}
		</ul>
		<ul class="legend" aria-label="Legenda dróg">
			{#each ROAD_ICONS as icon (icon.severity)}
				<li>
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- static SVG constants -->
					<span class="icon" aria-hidden="true">{@html icon.svg}</span>{icon.label}
				</li>
			{/each}
		</ul>
		<p class="hint">Kliknij obszar lub punkt, aby zobaczyć szczegóły.</p>
		<p class="share-view">
			<button type="button" class="link" onclick={shareView}>Udostępnij ten widok ↗</button>
			<span role="status">{shareNote}</span>
		</p>
	</div>
</aside>

{#if satDetails}
	<section class="details" aria-label="Szczegóły satelity" aria-live="polite">
		<button class="close" onclick={() => (satDetails = null)} aria-label="Zamknij szczegóły"
			>✕</button
		>
		<h2 class="summary-title label">
			{SAT_GROUPS.find((g) => g.id === satDetails?.group)?.label ?? 'Satelita'}
		</h2>
		<p class="plane-name">{satDetails.name}</p>
		<dl class="plane-facts">
			<dt>Nr katalogowy</dt>
			<dd class="mono">{satDetails.norad_id}</dd>
			<dt>Wysokość</dt>
			<dd class="mono">{satDetails.altitude_km.toLocaleString('pl-PL')} km</dd>
			<dt>Prędkość</dt>
			<dd class="mono">{satDetails.speed_kms} km/s</dd>
			<dt>Okres obiegu</dt>
			<dd class="mono">{Math.round(orbitalPeriodMin(satDetails.altitude_km))} min</dd>
		</dl>
		<p class="share-view">
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
			<a href={`https://www.n2yo.com/satellite/?s=${satDetails.norad_id}`} rel="noopener"
				>Śledź na n2yo.com ↗</a
			>
		</p>
		<p class="disclaimer">
			Pozycja liczona na żywo w przeglądarce z danych orbitalnych CelesTrak (TLE). To punkt pod
			satelitą (ślad na ziemi), nie widok z orbity.
		</p>
	</section>
{/if}

{#if plane}
	<section class="details" aria-label="Szczegóły samolotu" aria-live="polite">
		<button class="close" onclick={() => (plane = null)} aria-label="Zamknij szczegóły">✕</button>
		<h2 class="summary-title label">
			{AIRCRAFT_CLASSES.find((c) => c.id === plane?.class)?.label ?? 'Samolot'}
		</h2>
		<p class="plane-name">
			{plane.callsign ?? plane.registration ?? plane.hex.toUpperCase()}
		</p>
		<dl class="plane-facts">
			<dt>Rejestracja</dt>
			<dd class="mono">{plane.registration ?? '—'}</dd>
			<dt>Typ</dt>
			<dd class="mono">{plane.aircraft_type ?? '—'}</dd>
			<dt>Wysokość</dt>
			<dd class="mono">{formatAltitude(plane.altitude_ft)}</dd>
			<dt>Prędkość</dt>
			<dd class="mono">{formatSpeed(plane.speed_kt)}</dd>
			<dt>Kurs</dt>
			<dd class="mono">{plane.track === null ? '—' : `${Math.round(plane.track)}°`}</dd>
			<dt>Pozycja</dt>
			<dd class="mono">{timeAgo(plane.seen_at, now)}</dd>
		</dl>
		<p class="share-view">
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
			<a href={`https://adsb.lol/?icao=${plane.hex}`} rel="noopener">Śledź na adsb.lol ↗</a>
		</p>
		<p class="disclaimer">
			Dane ze społecznościowej sieci odbiorników ADS-B (adsb.lol, ODbL), odświeżane co minutę.
			Podział na klasy jest przybliżony; wojskowe – według bazy adsb.lol.
		</p>
	</section>
{/if}

{#if selected.length}
	<section class="details" aria-label="Szczegóły zdarzeń" aria-live="polite">
		<button class="close" onclick={() => (selected = [])} aria-label="Zamknij szczegóły">✕</button>
		<h2 class="summary-title label">
			{selected.length === 1 ? '1 zdarzenie' : `${selected.length} zdarzeń`} w tym miejscu
		</h2>
		<EventGroups events={selected} {now} openAll={selected.length === 1} />
		<p class="disclaimer">
			Narzędzie pomocnicze – nie zastępuje Alertów RCB ani komunikatów służb.
			<a href={resolve('/o-projekcie')}>Więcej</a>
		</p>
	</section>
{/if}

<style>
	.banners {
		position: absolute;
		top: calc(var(--header-h) + 0.5rem);
		left: 50%;
		transform: translateX(-50%);
		z-index: 6;
		width: min(36rem, calc(100% - 1rem));
	}
	.panel {
		position: absolute;
		top: calc(var(--header-h) + 0.5rem);
		left: 0.5rem;
		z-index: 5;
		width: min(20rem, calc(100% - 1rem));
		/* Leaves the bottom strip free: the map attribution (licence requirement) lives there. */
		--attribution-h: 2.75rem;
		max-height: calc(100% - var(--header-h) - 0.5rem - var(--attribution-h));
		overflow: auto;
		background: var(--panel);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
		backdrop-filter: blur(6px);
	}
	.banners:not(:empty) ~ .panel {
		top: calc(var(--header-h) + 4.5rem);
		max-height: calc(100% - var(--header-h) - 4.5rem - var(--attribution-h));
	}
	.panel-toggle {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0.75rem;
		border: 0;
		background: none;
		color: var(--fg);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.chev {
		font-family: var(--mono);
		color: var(--muted);
	}
	#layers-body {
		padding: 0 0.75rem 0.75rem;
	}
	fieldset {
		border: 0;
		margin: 0;
		padding: 0;
	}
	.min-sev {
		margin-bottom: 0.5rem;
	}
	.overview-note {
		margin: 0.4rem 0 0;
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--muted);
	}
	.min-sev legend {
		margin-bottom: 0.35rem;
	}
	.segmented {
		display: flex;
		border: 1px solid var(--border-strong);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.segmented label {
		flex: 1;
		position: relative;
	}
	.segmented input {
		position: absolute;
		opacity: 0;
		inset: 0;
		margin: 0;
		cursor: pointer;
	}
	.segmented span {
		display: block;
		min-height: 32px;
		line-height: 32px;
		text-align: center;
		font-family: var(--mono);
		font-size: 0.78rem;
		color: var(--muted);
	}
	.segmented label + label span {
		border-left: 1px solid var(--border);
	}
	.segmented input:checked + span {
		background: color-mix(in srgb, var(--accent) 18%, transparent);
		color: var(--accent);
		font-weight: 600;
	}
	.segmented input:focus-visible + span {
		outline: 3px solid var(--accent);
		outline-offset: -3px;
	}
	.layer {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		padding: 0.45rem 0;
		cursor: pointer;
	}
	.layer + .layer {
		border-top: 1px solid var(--border);
	}
	.layer input {
		width: 1rem;
		height: 1rem;
		margin-top: 0.2rem;
		accent-color: var(--accent);
	}
	.layer-body {
		flex: 1;
		min-width: 0;
	}
	.layer-head {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		font-size: 0.92rem;
	}
	.layer-head strong {
		font-weight: 600;
	}
	.layer small {
		display: block;
		color: var(--muted);
		font-size: 0.78rem;
	}
	.layer small.src {
		font-size: 0.7rem;
		margin-top: 0.1rem;
	}
	.dot {
		display: inline-block;
		width: 0.4rem;
		height: 0.4rem;
		margin-right: 0.4rem;
		border-radius: 50%;
		background: var(--muted);
		vertical-align: 0.1em;
	}
	.src.ok .dot {
		background: var(--ok);
	}
	.layer small.stale {
		color: var(--warn-fg);
	}
	.src.stale .dot {
		background: var(--warn-fg);
	}
	.count {
		color: var(--accent);
		font-size: 0.85rem;
	}
	.aircraft {
		margin-top: 0.6rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--border-strong);
	}
	.aircraft legend {
		margin-bottom: 0.15rem;
	}
	.aircraft > .src {
		display: block;
		margin-top: 0.25rem;
		font-size: 0.7rem;
		color: var(--muted);
	}
	.plane-dot {
		display: inline-block;
		width: 0.55rem;
		height: 0.55rem;
		margin-right: 0.45rem;
		border-radius: 1px;
		transform: rotate(45deg);
		vertical-align: 0.08em;
	}
	.plane-dot.sat {
		border-radius: 50%;
		transform: none;
	}
	.plane-name {
		margin: 0.25rem 0 0.5rem;
		font-family: var(--mono);
		font-size: 1.15rem;
		font-weight: 600;
		letter-spacing: 0.04em;
	}
	.plane-facts {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.2rem 1rem;
		margin: 0;
		font-size: 0.85rem;
	}
	.plane-facts dt {
		color: var(--muted);
	}
	.plane-facts dd {
		margin: 0;
	}
	.legend-title {
		margin: 0.75rem 0 0;
		padding-top: 0.6rem;
		border-top: 1px solid var(--border-strong);
	}
	.legend {
		list-style: none;
		padding: 0.35rem 0 0;
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.legend + .legend {
		margin-top: 0.35rem;
		border-top: 1px solid var(--border);
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.swatch {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 2px;
		flex: none;
	}
	.icon {
		display: inline-flex;
		width: 1.1rem;
		height: 1.1rem;
		flex: none;
	}
	.share-view {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0.25rem 0 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.link {
		background: none;
		border: 0;
		padding: 0.4rem 0;
		min-height: 36px;
		color: var(--accent);
		font: inherit;
		cursor: pointer;
	}
	.hint {
		font-size: 0.78rem;
		color: var(--muted);
		margin: 0.5rem 0 0;
	}
	.details {
		position: absolute;
		z-index: 7;
		left: 0;
		right: 0;
		bottom: 0;
		max-height: 55%;
		overflow: auto;
		padding: 0.75rem 1rem 1rem;
		background: var(--panel-solid);
		border-top: 1px solid var(--border-strong);
		border-radius: var(--radius) var(--radius) 0 0;
		box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.45);
	}
	@media (min-width: 720px) {
		.details {
			left: auto;
			right: 0.5rem;
			top: calc(var(--header-h) + 0.5rem);
			bottom: auto;
			width: 24rem;
			max-height: calc(100% - var(--header-h) - 3rem);
			border: 1px solid var(--border);
			border-radius: var(--radius);
		}
	}
	.close {
		float: right;
		min-width: 44px;
		min-height: 44px;
		border: 0;
		background: none;
		color: var(--fg);
		font-size: 1.1rem;
		cursor: pointer;
	}
	.summary-title {
		margin: 0.9rem 0 0.25rem;
		color: var(--accent);
	}
	.disclaimer {
		font-size: 0.75rem;
		color: var(--muted);
		margin-top: 0.75rem;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
