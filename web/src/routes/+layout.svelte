<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { connection } from '#lib/offline.svelte.ts';
	import { formatDate } from '#lib/events.ts';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	onMount(() => {
		const update = () => (connection.online = navigator.onLine);
		update();
		addEventListener('online', update);
		addEventListener('offline', update);
		return () => {
			removeEventListener('online', update);
			removeEventListener('offline', update);
		};
	});

	const links = [
		{ path: '/', label: 'Mapa' },
		{ path: '/moja-okolica', label: 'Moja okolica' },
		{ path: '/zrodla', label: 'Źródła' },
		{ path: '/o-projekcie', label: 'O projekcie' }
	] as const;
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<meta
		name="description"
		content="Mapa ostrzeżeń meteo i hydro, jakości powietrza i pożarów w Polsce z otwartych danych publicznych."
	/>
</svelte:head>

<header>
	<a class="brand" href={resolve('/')}>Monitor <span class="wide">sytuacyjny</span></a>
	<nav aria-label="Główna nawigacja">
		{#each links as link (link.path)}
			<a
				href={resolve(link.path)}
				aria-current={page.url.pathname === link.path ? 'page' : undefined}
			>
				{link.label}
			</a>
		{/each}
	</nav>
</header>

{#if !connection.online || connection.cachedAt}
	<p class="offline" role="status">
		<strong>Offline</strong> –
		{connection.cachedAt
			? `pokazujemy ostatni zapisany stan z ${formatDate(connection.cachedAt)}`
			: 'brak połączenia, dane mogą być nieaktualne'}
	</p>
{/if}

{@render children()}

{#if page.url.pathname !== '/'}
	<footer>
		<a href={resolve('/status')}>Status źródeł</a> ·
		<a href={resolve('/zrodla')}>Źródła i licencje</a> ·
		<a href={resolve('/o-projekcie')}>O projekcie</a>
	</footer>
{/if}

<style>
	.offline {
		position: fixed;
		top: var(--header-h);
		left: 0;
		right: 0;
		z-index: 9;
		margin: 0;
		padding: 0.35rem 0.75rem;
		text-align: center;
		font-size: 0.85rem;
		background: #3b3f45;
		color: #fff;
	}
	footer {
		max-width: 46rem;
		margin: 0 auto;
		padding: 1rem 1rem 2rem;
		border-top: 1px solid var(--border);
		font-size: 0.85rem;
		color: var(--muted);
	}
	header {
		position: fixed;
		inset: 0 0 auto 0;
		z-index: 10;
		height: var(--header-h);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0 0.75rem;
		background: var(--panel);
		border-bottom: 1px solid var(--border);
	}
	.brand {
		font-weight: 700;
		color: var(--fg);
		text-decoration: none;
		white-space: nowrap;
	}
	nav {
		display: flex;
		gap: 0.25rem;
	}
	@media (max-width: 560px) {
		.wide {
			display: none;
		}
	}
	nav a {
		white-space: nowrap;
		padding: 0.5rem 0.5rem;
		color: var(--fg);
		text-decoration: none;
		border-radius: 6px;
		font-size: 0.95rem;
	}
	nav a[aria-current='page'] {
		background: color-mix(in srgb, var(--accent) 15%, transparent);
		color: var(--accent);
	}
	/* Phones: four links need the whole width; "Mapa" already leads home. */
	@media (max-width: 440px) {
		.brand {
			display: none;
		}
		nav {
			width: 100%;
			justify-content: space-between;
		}
		nav a {
			padding: 0.5rem 0.35rem;
			font-size: 0.9rem;
		}
	}
</style>
