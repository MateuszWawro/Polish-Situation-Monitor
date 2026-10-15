<script lang="ts">
	import { resolve } from '$app/paths';
	import { LAYERS, timeAgo, type SourceStatus } from '#lib/events.ts';

	let { status, now }: { status: SourceStatus[]; now: number } = $props();

	const stale = $derived(status.filter((s) => s.stale));
	const layerLabel = (source: string) => LAYERS.find((l) => l.source === source)?.label ?? source;
	const sourceName = (source: string) =>
		LAYERS.find((l) => l.source === source)?.sourceName ?? source;
</script>

{#if stale.length}
	<p class="banner">
		Dane mogą być nieaktualne:
		{#each stale as s, i (s.source)}
			{i ? ', ' : ''}{layerLabel(s.source)} ({sourceName(s.source)}) – ostatnia aktualizacja
			{timeAgo(s.last_success_at, now)}
		{/each}.
		<a href={resolve('/status')}>Szczegóły</a>
	</p>
{/if}
