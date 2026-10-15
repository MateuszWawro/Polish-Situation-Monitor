<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import { getJson } from '#lib/offline.svelte.ts';
	import {
		LAYERS,
		formatDate,
		formatInterval,
		sourceHealth,
		timeAgo,
		type Health,
		type SourceHistory,
		type SourceStatus
	} from '#lib/events.ts';

	let status: SourceStatus[] = $state([]);
	let history: SourceHistory[] = $state([]);
	let now = $state(Date.now());
	let loadError = $state(false);

	const HEALTH: Record<Health, { icon: string; label: string }> = {
		ok: { icon: '✓', label: 'Działa' },
		delayed: { icon: '⏱', label: 'Opóźnione' },
		down: { icon: '✕', label: 'Niedostępne' }
	};
	const weekday = new Intl.DateTimeFormat('pl-PL', { weekday: 'short', timeZone: 'UTC' });

	// One row per source; a source feeding several layers (IMGW hydro) is listed once.
	const rows = $derived(
		status.map((st) => {
			const layers = LAYERS.filter((l) => l.source === st.source);
			const h = history.find((x) => x.source === st.source);
			const days = h?.days ?? [];
			const attempts = days.reduce((n, d) => n + d.attempts, 0);
			const ok = days.reduce((n, d) => n + d.ok, 0);
			return {
				st,
				layer: layers[0],
				label: layers.map((l) => l.label).join(', ') || st.source,
				health: sourceHealth(st, h?.last_attempt?.ok ?? null),
				last: h?.last_attempt ?? null,
				days,
				availability: attempts ? Math.floor((ok / attempts) * 1000) / 10 : null
			};
		})
	);
	const problems = $derived(rows.filter((r) => r.health !== 'ok').length);

	function dayClass(d: { attempts: number; ok: number }) {
		if (!d.attempts) return 'none';
		const share = d.ok / d.attempts;
		return share >= 0.99 ? 'good' : share >= 0.9 ? 'fair' : share > 0 ? 'poor' : 'bad';
	}

	async function load() {
		try {
			const [s, h] = await Promise.all([
				getJson<SourceStatus[]>('/api/sources/status', { cache: 'no-cache' }),
				getJson<SourceHistory[]>('/api/sources/history', { cache: 'no-cache' })
			]);
			status = s;
			history = h;
			loadError = false;
		} catch {
			loadError = true;
		}
	}

	onMount(() => {
		load();
		const timers = [setInterval(load, 60_000), setInterval(() => (now = Date.now()), 30_000)];
		return () => timers.forEach(clearInterval);
	});
</script>

<svelte:head><title>Status źródeł – Monitor sytuacyjny Polski</title></svelte:head>

<main class="page">
	<h1>Status źródeł danych</h1>
	{#if loadError}
		<p class="banner">Nie udało się pobrać statusu. Serwer może być chwilowo niedostępny.</p>
	{:else if rows.length}
		<p class="summary" class:bad={problems > 0}>
			{problems === 0
				? '✓ Wszystkie źródła działają.'
				: `${problems} z ${rows.length} źródeł ma problem – dane z nich mogą być nieaktualne.`}
		</p>
	{:else}
		<p class="muted">Ładowanie…</p>
	{/if}

	{#each rows as row (row.st.source)}
		<section class="source health-{row.health}" aria-labelledby="src-{row.st.source}">
			<header>
				<div>
					<h2 id="src-{row.st.source}">{row.label}</h2>
					<p class="provider">{row.layer?.sourceName ?? ''}</p>
				</div>
				<span class="state"
					><span aria-hidden="true">{HEALTH[row.health].icon}</span>
					{HEALTH[row.health].label}</span
				>
			</header>

			<dl>
				<div>
					<dt>Ostatnia udana aktualizacja</dt>
					<dd>
						{timeAgo(row.st.last_success_at, now)}
						{#if row.st.last_success_at}<span class="muted"
								>({formatDate(row.st.last_success_at)})</span
							>{/if}
					</dd>
				</div>
				<div>
					<dt>Odświeżanie</dt>
					<dd>{formatInterval(row.st.expected_interval_s)}</dd>
				</div>
			</dl>

			{#if row.last && !row.last.ok}
				<p class="error">
					Ostatnia próba ({timeAgo(row.last.at, now)}) nie powiodła się: {row.last.error ??
						'nieznany błąd'}
				</p>
			{/if}

			<div class="week">
				<p class="week-title">
					Dostępność, 7 dni{row.availability !== null ? `: ${row.availability}%` : ''}
				</p>
				<ol>
					{#each row.days as d (d.date)}
						<li class={dayClass(d)}>
							<span class="cell" aria-hidden="true"></span>
							<span class="day">{weekday.format(new Date(d.date))}</span>
							<span class="sr-only"
								>{d.date}: {d.attempts
									? `${d.ok} z ${d.attempts} pobrań udanych`
									: 'brak danych'}</span
							>
						</li>
					{/each}
				</ol>
			</div>

			{#if row.layer}
				<p class="links">
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
					<a href={row.layer.sourceUrl} rel="noopener">Strona źródła</a> ·
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- resolved path + anchor -->
					<a href={`${resolve('/zrodla')}#${row.layer.sourceAnchor}`}>licencja i atrybucja</a>
				</p>
			{/if}
		</section>
	{/each}

	<p class="muted note">
		„Opóźnione” – ostatnie pobranie się nie udało albo dane są starsze niż 1,5 interwału.
		„Niedostępne” – brak udanej aktualizacji dłużej niż 3 interwały. Historia prób jest zbierana od
		uruchomienia tej funkcji, więc starsze dni mogą być puste.
	</p>
</main>

<style>
	.summary {
		font-weight: 600;
		padding: 0.6rem 0.8rem;
		border-radius: var(--radius);
		background: color-mix(in srgb, #2e9d4e 15%, transparent);
	}
	.summary.bad {
		background: var(--warn-bg);
		color: var(--warn-fg);
	}
	.source {
		border: 1px solid var(--border);
		border-left: 3px solid #2e9d4e;
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 1rem 0;
	}
	.source.health-delayed {
		border-left-color: #ef7d1a;
	}
	.source.health-down {
		border-left-color: #d1242f;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
	}
	h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	.provider {
		margin: 0;
		color: var(--muted);
		font-size: 0.85rem;
	}
	.state {
		flex: none;
		font-weight: 700;
		padding: 0.15rem 0.55rem;
		border-radius: var(--radius);
		font-family: var(--mono);
		font-size: 0.72rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		background: color-mix(in srgb, #2e9d4e 18%, transparent);
	}
	.health-delayed .state {
		background: color-mix(in srgb, #ef7d1a 22%, transparent);
	}
	.health-down .state {
		background: color-mix(in srgb, #d1242f 22%, transparent);
	}
	dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
		gap: 0.25rem 1rem;
		margin: 0.6rem 0;
	}
	dt {
		font-size: 0.8rem;
		color: var(--muted);
	}
	dd {
		margin: 0;
	}
	.error {
		font-size: 0.85rem;
		background: var(--warn-bg);
		color: var(--warn-fg);
		padding: 0.4rem 0.6rem;
		border-radius: var(--radius);
		overflow-wrap: anywhere;
	}
	.week-title {
		margin: 0.25rem 0;
		font-size: 0.85rem;
		color: var(--muted);
	}
	ol {
		list-style: none;
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 4px;
		margin: 0;
		padding: 0;
	}
	li {
		display: grid;
		gap: 2px;
		text-align: center;
	}
	.cell {
		height: 1.6rem;
		border-radius: 4px;
		background: var(--border);
	}
	.good .cell {
		background: #2e9d4e;
	}
	.fair .cell {
		background: #e8b420;
	}
	.poor .cell {
		background: #ef7d1a;
	}
	.bad .cell {
		background: #d1242f;
	}
	.day {
		font-size: 0.75rem;
		color: var(--muted);
	}
	.links {
		margin: 0.6rem 0 0;
		font-size: 0.9rem;
	}
	.muted {
		color: var(--muted);
	}
	.note {
		font-size: 0.85rem;
		margin-top: 1.5rem;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
