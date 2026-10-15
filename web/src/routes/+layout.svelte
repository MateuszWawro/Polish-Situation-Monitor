<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const links = [
		{ path: '/', label: 'Mapa' },
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

{@render children()}

<style>
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
	@media (max-width: 420px) {
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
</style>
