<script lang="ts">
	import { resolve } from '$app/paths';
	import { shareLink } from '#lib/share.ts';
	import WaterChart from '#lib/WaterChart.svelte';
	import {
		LAYERS,
		SEVERITY_COLORS,
		formatDate,
		formatRange,
		groupEvents,
		severityLabel,
		timeAgo,
		type EventProps
	} from '#lib/events.ts';

	interface Props {
		events: EventProps[];
		/** Clock for "X min temu", ticked by the page. */
		now: number;
		/** Expand every row (e.g. when there is a single event). */
		openAll?: boolean;
	}
	let { events, now, openAll = false }: Props = $props();

	const groups = $derived(groupEvents(events));

	let shared: string | null = $state(null);
	async function share(ev: EventProps) {
		const url = `${location.origin}${resolve('/e/[id]', { id: ev.id })}`;
		if ((await shareLink(url, ev.title)) === 'copied') {
			shared = ev.id;
			setTimeout(() => (shared = null), 2500);
		}
	}
	const sourceLabel = (source: string) =>
		LAYERS.find((l) => l.source === source)?.sourceName ?? source;
</script>

{#each groups as group (group.layer.id)}
	<section class="group" aria-label={group.layer.label}>
		<h3>{group.layer.label} <span class="count">({group.count})</span></h3>
		{#each group.rows as row (row.key)}
			{@const single = row.events.length === 1 ? row.events[0] : null}
			<details open={openAll}>
				<summary>
					<span class="badge" style:background={SEVERITY_COLORS[row.severity]}>{row.severity}</span>
					<span class="row-title">{row.title}</span>
					{#if single}
						<span class="row-until"
							>{single.valid_to ? `do ${formatDate(single.valid_to)}` : ''}</span
						>
					{:else}
						<span class="row-until">×{row.events.length}</span>
					{/if}
				</summary>
				<div class="body">
					<p class="sev">{severityLabel(row.severity)}</p>
					{#each row.events as ev (ev.id)}
						<div class="item">
							<p class="meta">Ważność: {formatRange(ev.valid_from, ev.valid_to)}</p>
							{#if ev.description}<p class="desc">{ev.description}</p>{/if}
							{#if ev.source_event_id?.startsWith('station:')}
								<WaterChart stationId={ev.source_event_id.slice('station:'.length)} />
							{/if}
							<p class="meta">
								Źródło: {sourceLabel(ev.source)}
								<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external link -->
								{#if ev.source_url}· <a href={ev.source_url} target="_blank" rel="noopener"
										>strona źródła</a
									>{/if}
								· aktualizacja {timeAgo(ev.updated_at, now)}
							</p>
							<p class="actions">
								<a href={resolve('/e/[id]', { id: ev.id })}>Szczegóły</a>
								<button type="button" onclick={() => share(ev)}>🔗 Udostępnij</button>
								<span role="status">{shared === ev.id ? 'Skopiowano link' : ''}</span>
							</p>
						</div>
					{/each}
				</div>
			</details>
		{/each}
	</section>
{/each}

<style>
	.group h3 {
		margin: 0.75rem 0 0.25rem;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--muted);
	}
	details {
		border-top: 1px solid var(--border);
	}
	summary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		padding: 0.35rem 0;
		cursor: pointer;
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary::after {
		content: '▸';
		color: var(--muted);
		flex: none;
	}
	details[open] summary::after {
		content: '▾';
	}
	.badge {
		flex: none;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 4px;
		display: grid;
		place-items: center;
		font-size: 0.8rem;
		font-weight: 700;
		color: #1b1f24;
		border: 1px solid rgba(0, 0, 0, 0.3);
	}
	.row-title {
		flex: 1;
		min-width: 0;
		font-size: 0.95rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	details[open] .row-title {
		white-space: normal;
		font-weight: 600;
	}
	.row-until {
		flex: none;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.body {
		padding: 0 0 0.5rem 1.9rem;
	}
	.item + .item {
		border-top: 1px dashed var(--border);
		margin-top: 0.4rem;
	}
	.sev {
		margin: 0;
		font-weight: 600;
		font-size: 0.85rem;
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
	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 0.25rem 0 0;
		font-size: 0.85rem;
	}
	.actions a,
	.actions button {
		color: var(--accent);
		background: none;
		border: 0;
		padding: 0.4rem 0;
		min-height: 36px;
		font: inherit;
		cursor: pointer;
	}
	.actions [role='status'] {
		color: var(--muted);
	}
</style>
