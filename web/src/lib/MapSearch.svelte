<script lang="ts">
	import { searchPlaces, type PlaceHit, type PlacesIndex } from '#lib/search.ts';

	let { onpick }: { onpick: (hit: PlaceHit) => void } = $props();

	let query = $state('');
	let index: PlacesIndex | null = $state(null);
	let open = $state(false);
	let active = $state(0);
	const hits = $derived(index ? searchPlaces(index, query, 6) : []);

	async function ensureIndex() {
		index ??= await (await fetch('/places-index.json')).json();
	}

	function pick(hit: PlaceHit) {
		query = hit.name;
		open = false;
		onpick(hit);
	}

	function onkeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown' && hits.length) {
			e.preventDefault();
			open = true;
			active = (active + 1) % hits.length;
		} else if (e.key === 'ArrowUp' && hits.length) {
			e.preventDefault();
			active = (active - 1 + hits.length) % hits.length;
		} else if (e.key === 'Enter' && open && hits[active]) {
			e.preventDefault();
			pick(hits[active]);
		} else if (e.key === 'Escape') {
			open = false;
		}
	}
</script>

<div class="search">
	<label class="sr-only" for="map-search">Szukaj miejscowości, gminy lub powiatu</label>
	<input
		id="map-search"
		type="search"
		placeholder="Szukaj miejscowości…"
		autocomplete="off"
		role="combobox"
		aria-expanded={open && hits.length > 0}
		aria-controls="map-search-results"
		aria-activedescendant={open && hits[active] ? `map-hit-${active}` : undefined}
		bind:value={query}
		onfocus={ensureIndex}
		oninput={() => {
			open = true;
			active = 0;
		}}
		onblur={() => setTimeout(() => (open = false), 150)}
		{onkeydown}
	/>
	{#if open && hits.length}
		<ul id="map-search-results" role="listbox">
			{#each hits as hit, i (hit.name + hit.detail)}
				<li id="map-hit-{i}" role="option" aria-selected={i === active}>
					<button type="button" tabindex="-1" onmousedown={() => pick(hit)}>
						<strong>{hit.name}</strong><small>{hit.detail}</small>
					</button>
				</li>
			{/each}
		</ul>
	{:else if open && index && query.trim().length >= 2}
		<p class="none">Nic nie znaleziono.</p>
	{/if}
</div>

<style>
	.search {
		position: relative;
		padding: 0.5rem 0.75rem 0;
	}
	input {
		width: 100%;
		min-height: 40px;
		padding: 0.45rem 0.7rem;
		font: inherit;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--panel-solid);
		color: var(--fg);
	}
	ul {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--panel-solid);
	}
	li + li {
		border-top: 1px solid var(--border);
	}
	li[aria-selected='true'] button {
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}
	button {
		display: grid;
		width: 100%;
		text-align: left;
		padding: 0.45rem 0.7rem;
		border: 0;
		background: none;
		color: var(--fg);
		font: inherit;
		cursor: pointer;
	}
	small,
	.none {
		color: var(--muted);
		font-size: 0.8rem;
	}
	.none {
		margin: 0.25rem 0 0;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
