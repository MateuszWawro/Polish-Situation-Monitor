<script lang="ts">
	import { onMount } from 'svelte';
	import { formatDate } from '#lib/events.ts';
	import { describeTrend, trend, yRange, type WaterLevels } from '#lib/hydro.ts';

	let { stationId, hours = 72 }: { stationId: string; hours?: number } = $props();

	let data: WaterLevels | null = $state(null);
	let failed = $state(false);

	const W = 600;
	const H = 220;
	const PAD = { l: 58, r: 12, t: 12, b: 26 };
	const dayFmt = new Intl.DateTimeFormat('pl-PL', {
		weekday: 'short',
		day: 'numeric',
		timeZone: 'Europe/Warsaw'
	});
	const warsawDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Warsaw' });

	const chart = $derived.by(() => {
		if (!data || data.levels.length < 2) return null;
		const t0 = Date.now() - hours * 3600_000;
		const t1 = Date.now();
		const [y0, y1] = yRange(data);
		const x = (t: number) => PAD.l + ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r);
		const y = (cm: number) => PAD.t + (1 - (cm - y0) / (y1 - y0)) * (H - PAD.t - PAD.b);
		const pts = data.levels.map(([at, cm]) => [x(Date.parse(at)), y(cm)] as const);
		const line = pts
			.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`)
			.join('');
		const area = `${line}L${pts.at(-1)![0].toFixed(1)},${H - PAD.b}L${pts[0][0].toFixed(1)},${H - PAD.b}Z`;
		// Round tick step (10, 20, 25, 50, 100… cm) giving at most ~5 lines.
		const step = [10, 20, 25, 50, 100, 200, 500].find((s) => (y1 - y0) / s <= 5) ?? 1000;
		const yTicks: number[] = [];
		for (let t = Math.ceil(y0 / step) * step; t <= y1; t += step) yTicks.push(t);
		// Midnights in Warsaw time within the window → day labels.
		const days: { x: number; label: string }[] = [];
		let last = '';
		for (let t = t0; t <= t1; t += 3600_000) {
			const d = warsawDay.format(t);
			if (last && d !== last) days.push({ x: x(t), label: dayFmt.format(t) });
			last = d;
		}
		const [lastAt, lastCm] = data.levels.at(-1)!;
		return {
			x,
			y,
			line,
			area,
			yTicks,
			days,
			last: { x: pts.at(-1)![0], y: pts.at(-1)![1], at: lastAt, cm: lastCm }
		};
	});

	const summary = $derived.by(() => {
		if (!data?.levels.length) return '';
		const [at, cm] = data.levels.at(-1)!;
		const limits = [
			data.warning_cm !== null ? `ostrzegawczy ${data.warning_cm} cm` : null,
			data.alarm_cm !== null ? `alarmowy ${data.alarm_cm} cm` : null
		].filter(Boolean);
		return `Stan wody ${Math.round(cm)} cm (pomiar ${formatDate(at)}), ${describeTrend(trend(data.levels)).replace(/\.$/, '')}.${limits.length ? ` Stany: ${limits.join(', ')}.` : ''}`;
	});

	onMount(async () => {
		try {
			const r = await fetch(`/api/hydro/stations/${stationId}/levels?hours=${hours}`);
			if (!r.ok) throw new Error(`${r.status}`);
			data = await r.json();
		} catch {
			failed = true;
		}
	});
</script>

<figure>
	{#if failed}
		<figcaption class="muted">Nie udało się pobrać historii stanu wody.</figcaption>
	{:else if !data}
		<figcaption class="muted">Ładowanie wykresu…</figcaption>
	{:else if !chart}
		<figcaption class="muted">
			{summary || 'Brak pomiarów.'} Historia pomiarów dopiero się zbiera – wykres pojawi się po kolejnych
			odczytach.
		</figcaption>
	{:else}
		<svg viewBox="0 0 {W} {H}" role="img" aria-label={summary}>
			{#each chart.yTicks as t (t)}
				<line class="grid" x1={PAD.l} x2={W - PAD.r} y1={chart.y(t)} y2={chart.y(t)} />
				<text class="axis" x={PAD.l - 6} y={chart.y(t) + 4} text-anchor="end">{t} cm</text>
			{/each}
			{#each chart.days as d (d.label)}
				<line class="grid" x1={d.x} x2={d.x} y1={PAD.t} y2={H - PAD.b} />
				<text class="axis" x={d.x + 4} y={H - 8}>{d.label}</text>
			{/each}
			{#if data.warning_cm !== null}
				<line
					class="warning"
					x1={PAD.l}
					x2={W - PAD.r}
					y1={chart.y(data.warning_cm)}
					y2={chart.y(data.warning_cm)}
				/>
				<text class="label warning-text" x={PAD.l + 6} y={chart.y(data.warning_cm) - 5}
					>ostrzegawczy</text
				>
			{/if}
			{#if data.alarm_cm !== null}
				<line
					class="alarm"
					x1={PAD.l}
					x2={W - PAD.r}
					y1={chart.y(data.alarm_cm)}
					y2={chart.y(data.alarm_cm)}
				/>
				<text class="label alarm-text" x={PAD.l + 6} y={chart.y(data.alarm_cm) - 5}>alarmowy</text>
			{/if}
			<path class="area" d={chart.area} />
			<path class="line" d={chart.line} />
			<circle class="dot" cx={chart.last.x} cy={chart.last.y} r="4" />
		</svg>
		<figcaption>{summary}</figcaption>
	{/if}
</figure>

<style>
	figure {
		margin: 0.5rem 0;
	}
	svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.grid {
		stroke: var(--border);
		stroke-width: 1;
	}
	.axis {
		fill: var(--muted);
		font-size: 12px;
	}
	.label {
		font-size: 12px;
		fill: var(--muted);
	}
	.warning {
		stroke: #ef7d1a;
		stroke-width: 1.5;
		stroke-dasharray: 6 4;
	}
	.alarm {
		stroke: #d1242f;
		stroke-width: 1.5;
		stroke-dasharray: 6 4;
	}
	.warning-text {
		fill: #b85a00;
	}
	.alarm-text {
		fill: #d1242f;
	}
	.area {
		fill: color-mix(in srgb, var(--accent) 14%, transparent);
	}
	.line {
		fill: none;
		stroke: var(--accent);
		stroke-width: 2.5;
		stroke-linejoin: round;
	}
	.dot {
		fill: var(--accent);
		stroke: var(--bg);
		stroke-width: 2;
	}
	figcaption {
		font-size: 0.85rem;
		margin-top: 0.25rem;
	}
	.muted {
		color: var(--muted);
	}
</style>
