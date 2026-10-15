<script lang="ts">
	import { onMount } from 'svelte';
	import type { FeatureCollection } from 'geojson';
	import { resolve } from '$app/paths';
	import MapView from '#lib/MapView.svelte';
	import EventGroups from '#lib/EventGroups.svelte';
	import StaleBanner from '#lib/StaleBanner.svelte';
	import {
		LAYERS,
		layerFeatures,
		ROAD_ICONS,
		SEVERITY_COLORS,
		SEVERITY_LABELS,
		timeAgo,
		type EventProps,
		type EventType,
		type SourceStatus
	} from '#lib/events.ts';

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
	const MIN_SEVERITY_KEY = 'psm.minSeverity';
	const countFrom = (fc: FeatureCollection | undefined) =>
		fc?.features.filter((f) => (f.properties?.severity ?? 0) >= minSeverity).length;

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

	async function loadEvents() {
		const results = await Promise.allSettled(
			[...new Set(LAYERS.map((l) => l.type))].map(async (type) => {
				const r = await fetch(`/api/events?type=${type}`);
				if (!r.ok) throw new Error(`${r.status}`);
				data[type] = await r.json();
			})
		);
		loadError = results.some((r) => r.status === 'rejected');
	}

	async function loadStatus() {
		try {
			const r = await fetch('/api/sources/status');
			if (r.ok) status = await r.json();
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
		loadEvents();
		loadStatus();
		const timers = [
			setInterval(loadEvents, EVENTS_REFRESH_MS),
			setInterval(loadStatus, STATUS_REFRESH_MS),
			setInterval(() => (now = Date.now()), 30_000)
		];
		return () => timers.forEach(clearInterval);
	});
</script>

<svelte:head><title>Monitor sytuacyjny Polski – mapa</title></svelte:head>

<MapView {data} {visible} {minSeverity} onselect={(events) => (selected = events)} />

<div class="banners" aria-live="polite">
	{#if loadError}
		<p class="banner">Nie udało się pobrać części danych. Spróbujemy ponownie za kilka minut.</p>
	{/if}
	<StaleBanner {status} {now} />
</div>

<aside class="panel" aria-label="Warstwy i legenda">
	<button
		class="panel-toggle"
		aria-expanded={panelOpen}
		aria-controls="layers-body"
		onclick={() => (panelOpen = !panelOpen)}
	>
		Warstwy i legenda
	</button>
	<div id="layers-body" hidden={!panelOpen}>
		<fieldset class="min-sev">
			<legend>Pokaż od stopnia</legend>
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
		</fieldset>
		<fieldset>
			<legend class="sr-only">Widoczne warstwy</legend>
			{#each LAYERS as layer (layer.id)}
				{@const st = statusOf(layer.source)}
				<label class="layer">
					<input type="checkbox" bind:checked={visible[layer.id]} />
					<span>
						<strong>{layer.label}</strong>
						<span class="count">({countFrom(layerFeatures(layer, data[layer.type])) ?? '…'})</span>
						{#if layer.note}<small>{layer.note}</small>{/if}
						<small class:stale={st?.stale}>
							{layer.sourceName} · aktualizacja: {timeAgo(st?.last_success_at ?? null, now)}
						</small>
					</span>
				</label>
			{/each}
		</fieldset>
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
	</div>
</aside>

{#if selected.length}
	<section class="details" aria-label="Szczegóły zdarzeń" aria-live="polite">
		<button class="close" onclick={() => (selected = [])} aria-label="Zamknij szczegóły">✕</button>
		<h2 class="summary-title">
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
		max-height: calc(100% - var(--header-h) - 1rem);
		overflow: auto;
		background: var(--panel);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
	}
	.banners:not(:empty) ~ .panel {
		top: calc(var(--header-h) + 4.5rem);
	}
	.panel-toggle {
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0.75rem;
		border: 0;
		background: none;
		color: var(--fg);
		font: inherit;
		font-weight: 600;
		text-align: left;
		cursor: pointer;
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
	.min-sev legend {
		font-size: 0.85rem;
		color: var(--muted);
		margin-bottom: 0.25rem;
	}
	.segmented {
		display: flex;
		border: 1px solid var(--border);
		border-radius: 8px;
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
		min-height: 36px;
		line-height: 36px;
		text-align: center;
		font-size: 0.9rem;
	}
	.segmented label + label span {
		border-left: 1px solid var(--border);
	}
	.segmented input:checked + span {
		background: var(--accent);
		color: var(--bg);
		font-weight: 600;
	}
	.segmented input:focus-visible + span {
		outline: 3px solid var(--accent);
		outline-offset: -3px;
	}
	.layer {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		padding: 0.35rem 0;
		cursor: pointer;
	}
	.layer input {
		width: 1.2rem;
		height: 1.2rem;
		margin-top: 0.2rem;
	}
	.layer small {
		display: block;
		color: var(--muted);
	}
	.layer small.stale {
		color: var(--warn-fg);
		font-weight: 600;
	}
	.count {
		color: var(--muted);
	}
	.legend {
		list-style: none;
		padding: 0.5rem 0 0;
		margin: 0.5rem 0 0;
		border-top: 1px solid var(--border);
		font-size: 0.9rem;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.swatch {
		display: inline-block;
		width: 0.9rem;
		height: 0.9rem;
		border-radius: 3px;
		border: 1px solid rgba(0, 0, 0, 0.3);
		flex: none;
	}
	.icon {
		display: inline-flex;
		width: 1.1rem;
		height: 1.1rem;
		flex: none;
	}
	.hint {
		font-size: 0.85rem;
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
		background: var(--panel);
		border-top: 1px solid var(--border);
		border-radius: 12px 12px 0 0;
		box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.25);
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
			border-radius: 10px;
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
		margin: 0.6rem 0 0.25rem;
		font-size: 1rem;
	}
	.disclaimer {
		font-size: 0.8rem;
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
