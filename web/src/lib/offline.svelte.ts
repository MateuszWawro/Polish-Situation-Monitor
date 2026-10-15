// Shared offline state: set by getJson when the service worker answers from its cache.
export const connection = $state({ online: true, cachedAt: null as string | null });

const CACHED_AT = 'x-psm-cached-at';

/** fetch + JSON that records whether the answer came from the offline cache. */
export async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
	const r = await fetch(url, init);
	if (!r.ok) throw new Error(`${r.status}`);
	// A fresh network answer has no marker header; a cached one carries its fetch time.
	const cachedAt = r.headers.get(CACHED_AT);
	connection.cachedAt = navigator.onLine && !cachedAt ? null : (cachedAt ?? connection.cachedAt);
	return r.json() as Promise<T>;
}
