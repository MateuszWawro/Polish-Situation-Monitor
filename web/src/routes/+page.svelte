<script lang="ts">
	import { onMount } from 'svelte';
	import type { FeatureCollection } from 'geojson';
	import { resolve } from '$app/paths';
	import MapView from '#lib/MapView.svelte';
	import {
		LAYERS,
		SEVERITY_COLORS,
		SEVERITY_LABELS,
		formatRange,
		severityLabel,
		timeAgo,
		type EventProps,
		type EventType,
		type SourceStatus
	} from '#lib/events.ts';

	const EVENTS_REFRESH_MS = 5 * 60_000;
	const STATUS_REFRESH_MS = 60_000;

	let data: Partial<Record<EventType, FeatureCollection>> = $state({});
	let visible = $state(
		Object.fromEntries(LAYERS.map((l) => [l.type, true])) as Record<EventType, boolean>
	);
	let status: SourceStatus[] = $state([]);
	let selected: EventProps[] = $state([]);
	let loadError = $state(false);
	let panelOpen = $state(false);
	let now = $state(Date.now());

	const statusOf = (source: string) => status.find((s) => s.source === source);
	const stale = $derived(status.filter((s) => s.stale));

	async function loadEvents() {
		const results = await Promise.allSettled(
			LAYERS.map(async (l) => {
				const r = await fetch(`/api/events?type=${l.type}`);
				if (!r.ok) throw new Error(`${r.status}`);
				data[l.type] = await r.json();
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
		loadEvents();
		loadStatus();
		const timers = [
			setInterval(loadEvents, EVENTS_REFRESH_MS),
			setInterval(loadStatus, STATUS_REFRESH_MS),
			setInterval(() => (now = Date.now()), 30_000)
		];
		return () => timers.forEach(clearInterval);
	});

	const layerLabel = (source: string) => LAYERS.find((l) => l.source === source)?.label ?? source;
	const sourceLabel = (source: string) =>
		LAYERS.find((l) => l.source === source)?.sourceName ?? source;
</script>

<svelte:head><title>Monitor sytuacyjny Polski – mapa</title></svelte:head>

<MapView {data} {visible} onselect={(events) => (selected = events)} />

<div class="banners" aria-live="polite">
	{#if loadError}
		<p class="banner">Nie udało się pobrać części danych. Spróbujemy ponownie za kilka minut.</p>
	{/if}
	{#if stale.length}
		<p class="banner">
			Dane mogą być nieaktualne:
			{#each stale as s, i (s.source)}
				{i ? ', ' : ''}{layerLabel(s.source)} ({sourceLabel(s.source)}) – ostatnia aktualizacja
				{timeAgo(s.last_success_at, now)}
			{/each}.
		</p>
	{/if}
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
		<fieldset>
			<legend class="sr-only">Widoczne warstwy</legend>
			{#each LAYERS as layer (layer.type)}
				{@const st = statusOf(layer.source)}
				<label class="layer">
					<input type="checkbox" bind:checked={visible[layer.type]} />
					<span>
						<strong>{layer.label}</strong>
						<span class="count">({data[layer.type]?.features.length ?? '…'})</span>
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
		<p class="hint">Kliknij obszar lub punkt, aby zobaczyć szczegóły.</p>
	</div>
</aside>

{#if selected.length}
	<section class="details" aria-label="Szczegóły zdarzeń" aria-live="polite">
		<button class="close" onclick={() => (selected = [])} aria-label="Zamknij szczegóły">✕</button>
		{#each selected as ev (ev.id)}
			<article>
				<p class="sev">
					<span class="swatch" style:background={SEVERITY_COLORS[ev.severity]}></span>
					{severityLabel(ev.severity)}
				</p>
				<h2>{ev.title}</h2>
				<p class="meta">Ważność: {formatRange(ev.valid_from, ev.valid_to)}</p>
				{#if ev.description}<p class="desc">{ev.description}</p>{/if}
				<p class="meta">
					Źródło: {sourceLabel(ev.source)}
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
					{#if ev.source_url}· <a href={ev.source_url} target="_blank" rel="noopener"
							>strona źródła</a
						>{/if}
					· aktualizacja {timeAgo(ev.updated_at, now)}
				</p>
			</article>
		{/each}
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
	.banner {
		margin: 0 0 0.5rem;
		padding: 0.5rem 0.75rem;
		background: var(--warn-bg);
		color: var(--warn-fg);
		border-radius: 8px;
		font-size: 0.9rem;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
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
	article + article {
		border-top: 1px solid var(--border);
	}
	article h2 {
		margin: 0.1rem 0 0.25rem;
		font-size: 1.05rem;
	}
	.sev {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 0.5rem 0 0;
		font-weight: 600;
		font-size: 0.9rem;
	}
	.meta {
		color: var(--muted);
		font-size: 0.85rem;
		margin: 0.25rem 0;
	}
	.desc {
		white-space: pre-line;
		margin: 0.25rem 0;
		font-size: 0.95rem;
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
