<script lang="ts">
	import { resolve } from '$app/paths';
</script>

<svelte:head><title>O projekcie – Monitor sytuacyjny Polski</title></svelte:head>

<main class="page">
	<h1>O projekcie</h1>

	<section class="disclaimer" aria-labelledby="disclaimer-title">
		<h2 id="disclaimer-title">Ważne</h2>
		<p>
			To <strong>narzędzie pomocnicze</strong>. Nie zastępuje
			<a href="https://www.gov.pl/web/rcb/alert-rcb" rel="noopener">Alertów RCB</a> ani komunikatów
			służb, instytutów i władz. Dane mogą być opóźnione, niepełne lub chwilowo niedostępne. W
			sytuacji zagrożenia życia dzwoń pod <strong>112</strong>.
		</p>
	</section>

	<p>
		Monitor sytuacyjny Polski to hobbystyczny, niekomercyjny projekt open source (licencja MIT).
		Zbiera otwarte dane publiczne – ostrzeżenia meteorologiczne i hydrologiczne, jakość powietrza i
		satelitarne wykrycia pożarów – i pokazuje je na jednej mapie.
	</p>
	<p>
		Projekt nie jest związany z żadną instytucją państwową. Dane pochodzą z oficjalnych źródeł
		opisanych na stronie <a href={resolve('/zrodla')}>Źródła</a>, są automatycznie pobierane co
		kilka–kilkadziesiąt minut i przetwarzane (ujednolicenie stopni zagrożenia, przypisanie do
		powiatów).
	</p>
	<p>Strona nie zbiera danych osobowych, nie używa kont ani analityki śledzącej.</p>
</main>

<style>
	.disclaimer {
		border: 2px solid #d1242f;
		border-radius: 8px;
		padding: 0 1rem;
		margin: 1rem 0 1.5rem;
	}
</style>
