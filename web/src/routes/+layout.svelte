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

	let clock = $state('');
	// Same zone as every timestamp on the site (events.ts formatDate).
	const clockFormat = new Intl.DateTimeFormat('pl-PL', {
		timeZone: 'Europe/Warsaw',
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		timeZoneName: 'short'
	});

	onMount(() => {
		const tick = () => (clock = clockFormat.format(new Date()));
		tick();
		const timer = setInterval(tick, 1000);
		const update = () => (connection.online = navigator.onLine);
		update();
		addEventListener('online', update);
		addEventListener('offline', update);
		return () => {
			clearInterval(timer);
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
	<a class="brand" href={resolve('/')}>
		<span class="mark" aria-hidden="true"></span>
		<span class="code">PSM</span>
		<span class="name">Monitor <span class="wide">sytuacyjny</span></span>
	</a>
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
	<time class="clock" aria-hidden="true">{clock}</time>
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
		padding: 0.3rem 0.75rem;
		text-align: center;
		font-size: 0.8rem;
		background: var(--warn-bg);
		color: var(--warn-fg);
		border-bottom: 1px solid color-mix(in srgb, var(--warn-fg) 35%, transparent);
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
		gap: 1rem;
		padding: 0 0.75rem;
		background: var(--panel-solid);
		border-bottom: 1px solid var(--border);
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--fg);
		text-decoration: none;
		white-space: nowrap;
		font-size: 0.9rem;
	}
	/* Pulsing dot: the page refreshes itself, it is "live". */
	.mark {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--accent);
		box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 60%, transparent);
		animation: pulse 2.4s ease-out infinite;
	}
	@keyframes pulse {
		70% {
			box-shadow: 0 0 0 6px transparent;
		}
		100% {
			box-shadow: 0 0 0 0 transparent;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.mark {
			animation: none;
		}
	}
	.code {
		font-family: var(--mono);
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--accent);
	}
	.name {
		color: var(--muted);
		padding-left: 0.5rem;
		border-left: 1px solid var(--border-strong);
	}
	nav {
		display: flex;
		gap: 0.15rem;
		margin-left: auto;
	}
	.clock {
		font-family: var(--mono);
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		padding-left: 1rem;
		border-left: 1px solid var(--border);
		white-space: nowrap;
	}
	@media (max-width: 900px) {
		.clock {
			display: none;
		}
	}
	@media (max-width: 560px) {
		.wide {
			display: none;
		}
	}
	@media (max-width: 680px) {
		.name {
			display: none;
		}
	}
	nav a {
		white-space: nowrap;
		padding: 0.4rem 0.6rem;
		color: var(--muted);
		text-decoration: none;
		border-radius: var(--radius);
		font-family: var(--mono);
		font-size: 0.75rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	nav a:hover {
		color: var(--fg);
	}
	nav a[aria-current='page'] {
		color: var(--accent);
		box-shadow: inset 0 -2px 0 var(--accent);
		border-radius: 0;
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
			padding: 0.5rem 0.3rem;
			font-size: 0.68rem;
			letter-spacing: 0.04em;
		}
	}
</style>
