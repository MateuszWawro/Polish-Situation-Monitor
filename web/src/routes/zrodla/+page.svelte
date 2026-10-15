<script lang="ts">
	const sources = [
		{
			anchor: 'imgw',
			name: 'IMGW-PIB – ostrzeżenia meteorologiczne i hydrologiczne, stany wód',
			url: 'https://danepubliczne.imgw.pl/',
			terms: 'https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf',
			termsLabel: 'Regulamin udostępniania danych IMGW-PIB',
			attribution: [
				'Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy.',
				'Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone.'
			],
			notes:
				'Przetworzenie: ujednolicenie stopni (susza hydrologiczna = stopień 1), przypisanie ostrzeżeń hydro do całych województw, stany wód tylko powyżej stanu ostrzegawczego.'
		},
		{
			anchor: 'gios',
			name: 'GIOŚ – indeks jakości powietrza',
			url: 'https://powietrze.gios.gov.pl/',
			terms: 'https://powietrze.gios.gov.pl/pjp/content/api',
			termsLabel: 'Warunki korzystania z API portalu Jakość Powietrza',
			attribution: ['Źródło: Główny Inspektorat Ochrony Środowiska, portal „Jakość Powietrza”.'],
			notes:
				'Indeks 0–5 przeliczony na stopnie 0–3 (bardzo dobry/dobry → 0, umiarkowany → 1, dostateczny → 2, zły/bardzo zły → 3). Dane GIOŚ nie są na bieżąco weryfikowane.'
		},
		{
			anchor: 'firms',
			name: 'NASA FIRMS – satelitarne wykrycia punktów cieplnych (VIIRS NOAA-20, NOAA-21)',
			url: 'https://firms.modaps.eosdis.nasa.gov/',
			terms: 'https://www.earthdata.nasa.gov/data/tools/firms/faq',
			termsLabel: 'NASA FIRMS FAQ – zasady korzystania',
			attribution: ['NASA FIRMS (NASA LANCE, ESDIS).'],
			notes:
				'Punkt cieplny to wykrycie satelitarne – nie każdy jest pożarem (np. instalacje przemysłowe). Pewność wykrycia niska/średnia/wysoka → stopień 1/2/3.'
		},
		{
			anchor: 'gddkia',
			name: 'GDDKiA – utrudnienia na drogach krajowych',
			url: 'https://www.gov.pl/web/gddkia',
			terms: 'https://dane.gov.pl/pl/dataset/2752',
			termsLabel: 'Zbiór „Utrudnienia na drogach” w dane.gov.pl (licencja CC0 1.0)',
			attribution: ['Źródło: Generalna Dyrekcja Dróg Krajowych i Autostrad.'],
			notes:
				'Stopnie: zamknięcie drogi → 3, ruch wahadłowy / sygnalizacja / ruch dwukierunkowy na jednej jezdni / awaria mostu / zdarzenie → 2, roboty i ograniczenia → 1. „Zamknięcie” pochodzi z flagi źródła i może dotyczyć tylko jednej jezdni lub części pojazdów.'
		},
		{
			anchor: 'adsb',
			name: 'adsb.lol – dane ADS-B samolotów (zakłócenia GPS)',
			url: 'https://adsb.lol/',
			terms: 'https://opendatacommons.org/licenses/odbl/1-0/',
			termsLabel: 'Licencja ODbL 1.0',
			attribution: ['Dane lotnicze: adsb.lol (społecznościowa sieć odbiorników ADS-B), ODbL 1.0.'],
			notes:
				'Jedyne nieoficjalne źródło na mapie. Samoloty nadają, jak dokładna jest ich pozycja GPS (NACp). Liczymy, jaki odsetek samolotów w kwadracie ok. 55 × 50 km zgłaszał w ostatniej godzinie obniżoną dokładność (NACp < 8), metodą serwisu gpsjam.org: co najmniej 8 samolotów, wynik (złe − 1) / wszystkie. 2–10% → stopień 1, 10–30% → 2, od 30% → 3. To szacunek: wskazuje prawdopodobne zakłócenia, ale ich nie potwierdza – niską dokładność mogą też zgłaszać pojedyncze samoloty z powodu awarii lub starszego sprzętu. Brak kwadratu oznacza brak zakłóceń albo za mało samolotów.'
		},
		{
			anchor: 'prg',
			name: 'GUGiK – Państwowy Rejestr Granic (granice województw i powiatów)',
			url: 'https://www.geoportal.gov.pl/',
			terms: null,
			termsLabel: null,
			attribution: ['Źródło: Główny Urząd Geodezji i Kartografii, PRG.'],
			notes: 'Geometrie uproszczone na potrzeby mapy (tolerancja ok. 200 m).'
		},
		{
			anchor: 'osm',
			name: 'OpenStreetMap – podkład mapy',
			url: 'https://www.openstreetmap.org/',
			terms: 'https://www.openstreetmap.org/copyright',
			termsLabel: 'Licencja ODbL',
			attribution: ['© współtwórcy OpenStreetMap.'],
			notes: null
		}
	];
</script>

<svelte:head><title>Źródła danych – Monitor sytuacyjny Polski</title></svelte:head>

<main class="page">
	<h1>Źródła danych i licencje</h1>
	<p>
		Aplikacja pobiera dane wyłącznie na swoim serwerze – Twoja przeglądarka nie łączy się
		bezpośrednio ze źródłami. Wszystkie dane są otwarte i wykorzystywane w celach niekomercyjnych.
	</p>

	{#each sources as source (source.name)}
		<section id={source.anchor}>
			<h2>{source.name}</h2>
			{#each source.attribution as line (line)}
				<p class="attribution">{line}</p>
			{/each}
			{#if source.notes}<p>{source.notes}</p>{/if}
			<ul>
				<!-- external links: nothing to resolve -->
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
				<li><a href={source.url} rel="noopener">Strona źródła</a></li>
				{#if source.terms}
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
					<li><a href={source.terms} rel="noopener">{source.termsLabel}</a></li>
				{/if}
			</ul>
		</section>
	{/each}

	<p>
		Kod źródłowy: licencja MIT. Szczegóły techniczne źródeł znajdziesz w pliku
		<code>docs/SOURCES.md</code> w repozytorium.
	</p>
</main>

<style>
	section {
		border-top: 1px solid var(--border);
		padding-top: 0.5rem;
	}
	h2 {
		font-size: 1.1rem;
	}
	.attribution {
		font-style: italic;
	}
</style>
