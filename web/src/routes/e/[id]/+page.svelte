<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { describeArea } from '#lib/area.ts';
	import {
		LAYERS,
		ROAD_ICONS,
		SEVERITY_COLORS,
		formatDate,
		formatRange,
		inLayer,
		severityLabel,
		timeAgo,
		type EventProps
	} from '#lib/events.ts';
	import type { PlacesIndex } from '#lib/search.ts';
	import { shareLink } from '#lib/share.ts';
	import WaterChart from '#lib/WaterChart.svelte';

	let ev: EventProps | null = $state(null);
	let area: string[] = $state([]);
	let notFound = $state(false);
	let loadError = $state(false);
	let shareNote = $state('');
	let now = $state(Date.now());

	const layer = $derived.by(() => {
		const e = ev;
		return e ? LAYERS.find((l) => inLayer(l, e)) : undefined;
	});
	const phase = $derived.by(() => {
		if (!ev) return null;
		if (ev.valid_to && Date.parse(ev.valid_to) <= now) return 'ended';
		if (ev.valid_from && Date.parse(ev.valid_from) > now) return 'upcoming';
		return 'active';
	});
	const roadIcon = $derived.by(() => {
		const e = ev;
		return e?.type === 'road_incident'
			? ROAD_ICONS.find((i) => i.severity === e.severity)
			: undefined;
	});

	async function load(id: string) {
		try {
			const r = await fetch(`/api/events/${id}`);
			if (r.status === 404 || r.status === 422) {
				notFound = true;
				return;
			}
			if (!r.ok) throw new Error(`${r.status}`);
			ev = (await r.json()).properties as EventProps;
			if (ev.teryt_powiat?.length) {
				const index: PlacesIndex = await (await fetch('/places-index.json')).json();
				area = describeArea(ev.teryt_powiat, index);
			}
		} catch {
			loadError = true;
		}
	}

	async function share() {
		if (!ev) return;
		const result = await shareLink(location.href, ev.title);
		shareNote =
			result === 'copied' ? 'Skopiowano link' : result === 'failed' ? 'Nie udało się' : '';
		setTimeout(() => (shareNote = ''), 2500);
	}

	onMount(() => {
		load(page.params.id ?? '');
		const timer = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(timer);
	});
</script>

<svelte:head>
	<title
		>{ev
			? `${ev.title} – Monitor sytuacyjny Polski`
			: 'Zdarzenie – Monitor sytuacyjny Polski'}</title
	>
</svelte:head>

<main class="page">
	<p class="back"><a href={resolve('/')}>← Mapa</a></p>

	{#if notFound}
		<h1>Nie znaleziono zdarzenia</h1>
		<p>Link może być niepełny albo zdarzenie zostało usunięte ze źródła.</p>
	{:else if loadError}
		<p class="banner">Nie udało się pobrać zdarzenia. Spróbuj ponownie za chwilę.</p>
	{:else if !ev}
		<p class="muted">Ładowanie…</p>
	{:else}
		<article class:ended={phase === 'ended'}>
			<p class="band" style:--sev={SEVERITY_COLORS[ev.severity]}>
				{#if roadIcon}
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- static SVG constant -->
					<span class="icon" aria-hidden="true">{@html roadIcon.svg}</span>
				{:else}
					<span class="badge" aria-hidden="true">{ev.severity}</span>
				{/if}
				{severityLabel(ev.severity)}
			</p>
			<p class="kind">{layer?.label ?? ''} · {layer?.sourceName ?? ''}</p>
			<h1>{ev.title}</h1>

			{#if phase === 'ended'}
				<p class="state ended-note">Nieaktualne od {formatDate(ev.valid_to)}</p>
			{:else if phase === 'upcoming'}
				<p class="state">Zacznie obowiązywać {formatDate(ev.valid_from)}</p>
			{:else}
				<p class="state">
					{ev.valid_to
						? `Obowiązuje do ${formatDate(ev.valid_to)}`
						: 'Obowiązuje (bez określonego końca)'}
				</p>
			{/if}

			<dl>
				<div>
					<dt>Ważność</dt>
					<dd>{formatRange(ev.valid_from, ev.valid_to)}</dd>
				</div>
				{#if area.length}
					<div>
						<dt>Obszar</dt>
						<dd>
							{#each area as line (line)}<span class="area-line">{line}</span>{/each}
						</dd>
					</div>
				{/if}
				<div>
					<dt>Ostatnia zmiana</dt>
					<dd>{timeAgo(ev.updated_at, now)}</dd>
				</div>
			</dl>

			{#if ev.description}<p class="desc">{ev.description}</p>{/if}

			{#if ev.source_event_id?.startsWith('station:')}
				<h2 class="chart-title">Stan wody – ostatnie 3 doby</h2>
				<WaterChart stationId={ev.source_event_id.slice('station:'.length)} />
			{/if}

			<div class="actions">
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- resolved path + query -->
				<a class="primary" href={`${resolve('/')}?e=${ev.id}`}>Pokaż na mapie</a>
				<button type="button" onclick={share}>🔗 Udostępnij</button>
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
				{#if ev.source_url}<a href={ev.source_url} rel="noopener">Strona źródła ↗</a>{/if}
				<span role="status">{shareNote}</span>
			</div>

			<p class="disclaimer">
				Dane: {layer?.sourceName ?? 'źródło publiczne'} (przetworzone). Narzędzie pomocnicze – nie zastępuje
				Alertów RCB ani komunikatów służb.
			</p>
		</article>
	{/if}
</main>

<style>
	.back {
		margin: 0 0 0.5rem;
	}
	.band {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
		font-weight: 700;
		background: color-mix(in srgb, var(--sev) 22%, transparent);
		border-left: 6px solid var(--sev);
	}
	.ended .band {
		filter: grayscale(1);
	}
	.badge {
		width: 1.6rem;
		height: 1.6rem;
		display: grid;
		place-items: center;
		border-radius: 4px;
		background: var(--sev);
		color: #1b1f24;
	}
	.icon {
		display: inline-flex;
		width: 1.6rem;
		height: 1.6rem;
	}
	.kind {
		margin: 0.75rem 0 0;
		color: var(--muted);
		font-size: 0.9rem;
	}
	h1 {
		margin: 0.1rem 0 0.25rem;
		font-size: 1.5rem;
		line-height: 1.25;
	}
	.state {
		margin: 0;
		font-weight: 600;
	}
	.ended-note {
		display: inline-block;
		margin-top: 0.25rem;
		padding: 0.25rem 0.6rem;
		border-radius: var(--radius);
		background: var(--warn-bg);
		color: var(--warn-fg);
	}
	dl {
		display: grid;
		gap: 0.5rem;
		margin: 1rem 0;
	}
	dt {
		font-size: 0.8rem;
		color: var(--muted);
	}
	dd {
		margin: 0;
	}
	.area-line {
		display: block;
	}
	.desc {
		white-space: pre-line;
		border-top: 1px solid var(--border);
		padding-top: 0.75rem;
	}
	.chart-title {
		font-size: 1rem;
		margin: 1rem 0 0;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
		margin: 1rem 0;
	}
	.actions a,
	.actions button {
		min-height: 44px;
		display: inline-flex;
		align-items: center;
		color: var(--accent);
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		cursor: pointer;
	}
	.actions .primary {
		padding: 0 1rem;
		border-radius: var(--radius);
		background: var(--accent);
		color: var(--bg);
		font-weight: 600;
		text-decoration: none;
	}
	.actions [role='status'] {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.disclaimer,
	.muted {
		color: var(--muted);
		font-size: 0.85rem;
	}
</style>
