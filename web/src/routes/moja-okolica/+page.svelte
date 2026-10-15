<script lang="ts">
	import { onMount } from 'svelte';
	import type { FeatureCollection } from 'geojson';
	import EventGroups from '#lib/EventGroups.svelte';
	import StaleBanner from '#lib/StaleBanner.svelte';
	import { formatDate, type EventProps, type SourceStatus } from '#lib/events.ts';
	import { findPowiat } from '#lib/geo.ts';
	import { MAX_PLACES, deletePlace, loadPlaces, savePlace, type Place } from '#lib/places.ts';
	import { searchPlaces, type PlaceHit, type PlacesIndex } from '#lib/search.ts';

	const REFRESH_MS = 5 * 60_000;

	let places: Place[] = $state([]);
	let summary: Record<string, EventProps[]> = $state({});
	let status: SourceStatus[] = $state([]);
	let now = $state(Date.now());
	let ready = $state(false);
	let loadError = $state(false);
	let storageError = $state(false);

	// "Add place" form
	let adding = $state(false);
	let name = $state('');
	let query = $state('');
	let index: PlacesIndex | null = $state(null);
	let chosen: (PlaceHit & { point?: [number, number] }) | null = $state(null);
	let locating = $state(false);
	let locateError = $state('');
	const hits = $derived(index && !chosen ? searchPlaces(index, query) : []);

	const lastUpdate = $derived(
		status
			.map((s) => s.last_success_at)
			.filter((t): t is string => !!t)
			.sort()
			.at(-1) ?? null
	);

	async function refresh() {
		const codes = [...new Set(places.map((p) => p.teryt))];
		if (!codes.length) return;
		try {
			const r = await fetch(`/api/areas/summary?teryt=${codes.join(',')}`);
			if (!r.ok) throw new Error(`${r.status}`);
			summary = await r.json();
			loadError = false;
		} catch {
			loadError = true; // keep showing the last summary
		}
		try {
			const r = await fetch('/api/sources/status');
			if (r.ok) status = await r.json();
		} catch {
			// covered by loadError
		}
	}

	async function reloadPlaces() {
		try {
			places = await loadPlaces();
		} catch {
			storageError = true;
		}
	}

	async function ensureIndex() {
		index ??= await (await fetch('/places-index.json')).json();
	}

	function locate() {
		locateError = '';
		if (!('geolocation' in navigator)) {
			locateError = 'Ta przeglądarka nie udostępnia lokalizacji. Wyszukaj miejsce poniżej.';
			return;
		}
		locating = true;
		navigator.geolocation.getCurrentPosition(
			async ({ coords }) => {
				try {
					// The position is matched against powiat boundaries here, on the device.
					const point: [number, number] = [coords.longitude, coords.latitude];
					const [powiaty] = await Promise.all([
						fetch('/api/admin-units?level=powiat').then(
							(r) => r.json() as Promise<FeatureCollection>
						),
						ensureIndex()
					]);
					const teryt = findPowiat(point, powiaty);
					if (!teryt || !index) {
						locateError = 'Twoja lokalizacja jest poza Polską. Wyszukaj miejsce poniżej.';
						return;
					}
					chosen = {
						teryt,
						name: 'Moja lokalizacja',
						detail: `${index.powiaty[teryt]}, woj. ${index.voivodeships[teryt.slice(0, 2)]}`,
						point
					};
					name ||= 'Tutaj';
				} catch {
					locateError = 'Nie udało się ustalić powiatu. Wyszukaj miejsce poniżej.';
				} finally {
					locating = false;
				}
			},
			(err) => {
				locating = false;
				locateError =
					err.code === err.PERMISSION_DENIED
						? 'Brak zgody na lokalizację – to w porządku, wyszukaj miejsce poniżej.'
						: 'Nie udało się pobrać lokalizacji. Wyszukaj miejsce poniżej.';
			},
			{ timeout: 15_000, maximumAge: 10 * 60_000 }
		);
	}

	function choose(hit: PlaceHit) {
		chosen = hit;
		name ||= hit.name;
	}

	function resetForm() {
		adding = false;
		name = query = locateError = '';
		chosen = null;
	}

	async function addPlace(e: SubmitEvent) {
		e.preventDefault();
		if (!chosen || places.length >= MAX_PLACES) return;
		const place: Place = {
			id: crypto.randomUUID(),
			name: name.trim() || chosen.name,
			teryt: chosen.teryt,
			area: chosen.point ? chosen.detail : `${chosen.name}, ${chosen.detail}`,
			point: chosen.point,
			createdAt: new Date().toISOString()
		};
		try {
			await savePlace($state.snapshot(place) as Place);
		} catch {
			storageError = true;
			return;
		}
		resetForm();
		await reloadPlaces();
		await refresh();
	}

	async function removePlace(place: Place) {
		await deletePlace(place.id);
		await reloadPlaces();
	}

	onMount(() => {
		reloadPlaces().then(async () => {
			adding = places.length === 0;
			await refresh();
			ready = true;
		});
		const timers = [
			setInterval(refresh, REFRESH_MS),
			setInterval(() => (now = Date.now()), 30_000)
		];
		return () => timers.forEach(clearInterval);
	});
</script>

<svelte:head><title>Moja okolica – Monitor sytuacyjny Polski</title></svelte:head>

<main class="page">
	<h1>Moja okolica</h1>
	<p class="lead">
		Aktywne ostrzeżenia dla Twoich miejsc (do {MAX_PLACES}). Miejsca zapisują się
		<strong>tylko na tym urządzeniu</strong>.
	</p>

	<div aria-live="polite">
		<StaleBanner {status} {now} />
		{#if loadError}
			<p class="banner">Nie udało się pobrać danych. Pokazujemy ostatni znany stan.</p>
		{/if}
		{#if storageError}
			<p class="banner">
				Przeglądarka blokuje zapis danych (np. tryb prywatny), więc miejsca nie zostaną zapamiętane.
			</p>
		{/if}
	</div>

	{#each places as place (place.id)}
		{@const events = summary[place.teryt]}
		{@const warnings = events?.filter((e) => e.severity > 0).length ?? 0}
		<section class="place" aria-labelledby="place-{place.id}">
			<header>
				<div>
					<h2 id="place-{place.id}">{place.name}</h2>
					<p class="area">{place.area}</p>
				</div>
				<button
					class="remove"
					onclick={() => removePlace(place)}
					aria-label="Usuń miejsce {place.name}">Usuń</button
				>
			</header>
			{#if !events}
				<p class="muted">{ready ? 'Brak danych.' : 'Ładowanie…'}</p>
			{:else}
				{#if !warnings}
					<p class="empty">
						✓ Brak aktywnych ostrzeżeń.
						<span class="muted">Ostatnia aktualizacja źródeł: {formatDate(lastUpdate)}</span>
					</p>
				{/if}
				{#if events.length}
					<EventGroups {events} {now} />
				{/if}
			{/if}
		</section>
	{/each}

	{#if adding}
		<form class="add" onsubmit={addPlace} aria-labelledby="add-title">
			<h2 id="add-title">Dodaj miejsce</h2>
			<button type="button" class="secondary" onclick={locate} disabled={locating}>
				{locating ? 'Ustalanie…' : '📍 Użyj mojej lokalizacji'}
			</button>
			<p class="hint">
				Opcjonalne. Pozycja jest porównywana z granicami powiatów na Twoim urządzeniu i nigdy nie
				jest wysyłana na serwer.
			</p>
			{#if locateError}<p class="error" role="alert">{locateError}</p>{/if}

			{#if chosen}
				<p class="chosen">
					<strong>{chosen.name}</strong> – {chosen.detail}
					<button type="button" class="link" onclick={() => (chosen = null)}>zmień</button>
				</p>
			{:else}
				<label for="place-search">…albo wyszukaj gminę, miasto lub powiat</label>
				<input
					id="place-search"
					type="search"
					autocomplete="off"
					placeholder="np. Krosno"
					bind:value={query}
					onfocus={ensureIndex}
				/>
				{#if hits.length}
					<ul class="hits" aria-label="Wyniki wyszukiwania">
						{#each hits as hit (hit.name + hit.detail)}
							<li>
								<button type="button" onclick={() => choose(hit)}>
									<strong>{hit.name}</strong><small>{hit.detail}</small>
								</button>
							</li>
						{/each}
					</ul>
				{:else if query.trim().length >= 2 && index}
					<p class="muted">Nic nie znaleziono.</p>
				{/if}
			{/if}

			<label for="place-name">Twoja nazwa (np. Dom, Praca)</label>
			<input id="place-name" bind:value={name} maxlength="40" />

			<div class="actions">
				<button type="submit" disabled={!chosen}>Zapisz miejsce</button>
				{#if places.length}
					<button type="button" class="link" onclick={resetForm}>Anuluj</button>
				{/if}
			</div>
		</form>
	{:else if places.length < MAX_PLACES}
		<button class="secondary" onclick={() => (adding = true)}>+ Dodaj miejsce</button>
	{:else}
		<p class="muted">Masz już {MAX_PLACES} miejsc – usuń któreś, aby dodać nowe.</p>
	{/if}

	<p class="disclaimer">Narzędzie pomocnicze – nie zastępuje Alertów RCB ani komunikatów służb.</p>
</main>

<style>
	.lead {
		color: var(--muted);
	}
	.place {
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.75rem 1rem;
		margin: 1rem 0;
	}
	.place header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.place h2 {
		margin: 0;
		font-size: 1.15rem;
	}
	.area {
		margin: 0;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.empty {
		margin: 0.5rem 0;
	}
	.muted,
	.hint {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.empty .muted {
		display: block;
	}
	.add {
		border: 1px dashed var(--border);
		border-radius: 10px;
		padding: 0.75rem 1rem;
		margin: 1rem 0;
		display: grid;
		gap: 0.4rem;
	}
	.add h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	label {
		font-size: 0.9rem;
		margin-top: 0.5rem;
	}
	input {
		font: inherit;
		padding: 0.6rem 0.7rem;
		min-height: 44px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg);
		color: var(--fg);
	}
	button {
		font: inherit;
		min-height: 44px;
		padding: 0.5rem 1rem;
		border-radius: 8px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--bg);
		font-weight: 600;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	button.secondary {
		background: transparent;
		color: var(--accent);
	}
	button.link,
	button.remove {
		background: none;
		border: 0;
		color: var(--accent);
		font-weight: 400;
		padding: 0.25rem 0.5rem;
		min-height: 44px;
	}
	.hits {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
	}
	.hits button {
		width: 100%;
		text-align: left;
		background: none;
		border: 0;
		border-radius: 0;
		color: var(--fg);
		font-weight: 400;
		display: grid;
	}
	.hits li + li button {
		border-top: 1px solid var(--border);
	}
	.hits small {
		color: var(--muted);
	}
	.chosen {
		margin: 0.5rem 0 0;
	}
	.error {
		color: var(--warn-fg);
		background: var(--warn-bg);
		padding: 0.4rem 0.6rem;
		border-radius: 6px;
		margin: 0;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}
	.disclaimer {
		font-size: 0.8rem;
		color: var(--muted);
		margin-top: 2rem;
	}
</style>
