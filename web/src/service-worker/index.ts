// Offline support: app shell cache-first, API network-first with the last good response kept.
// Map tiles are NOT cached here: the OSM tile policy discourages bulk caching.
import { self } from '$app/service-worker';
import { assets, immutable, prerendered } from '$app/manifest';

// Manifest paths are relative ("_app/…", "" for the home page): make them absolute.
const SHELL_FILES = [...immutable, ...assets, ...prerendered].map((f) => `/${f.path}`);
/** SPA fallback for dynamic pages (/e/{id}); optional – not every server exposes it. */
const SPA_FALLBACK = '/200.html';
// New build → new file names → new cache; old ones are dropped on activate.
const SHELL = `shell-${hash(SHELL_FILES.join('|'))}`;
const DATA = 'api-v1';
/** Header added to API responses served from the cache: when they were fetched. */
const CACHED_AT = 'x-psm-cached-at';

// Only what the screens need offline; never anything user-specific beyond powiat codes.
const OFFLINE_API = [
	/^\/api\/events(\/|\?|$)/,
	/^\/api\/sources\/(status|history)$/,
	/^\/api\/areas\/summary\?/,
	/^\/api\/admin-units/,
	/^\/api\/hydro\/stations\//
];

self.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(SHELL)
			.then(async (c) => {
				await c.addAll(SHELL_FILES);
				await c.add(SPA_FALLBACK).catch(() => {});
			})
			.then(() => self.skipWaiting())
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys.filter((k) => k.startsWith('shell-') && k !== SHELL).map((k) => caches.delete(k))
				)
			)
			.then(() => self.clients.claim())
	);
});

self.addEventListener('fetch', (event) => {
	const req = event.request;
	const url = new URL(req.url);
	if (req.method !== 'GET' || url.origin !== self.location.origin) return; // tiles etc.: browser default

	if (url.pathname.startsWith('/api/')) {
		if (OFFLINE_API.some((re) => re.test(url.pathname + url.search)))
			event.respondWith(networkFirstApi(req));
		return;
	}
	if (req.mode === 'navigate') {
		event.respondWith(
			fetch(req).catch(
				async () =>
					(await shellMatch(url.pathname)) ?? (await shellMatch(SPA_FALLBACK)) ?? Response.error()
			)
		);
		return;
	}
	if (SHELL_FILES.includes(url.pathname))
		event.respondWith(shellMatch(url.pathname).then((hit) => hit ?? fetch(req)));
});

/** Look up by path only: module-script requests differ in headers (Origin, mode) from the
 * install-time requests, and the server answers with `Vary: Origin`. */
function shellMatch(path: string): Promise<Response | undefined> {
	return caches.match(path, { ignoreVary: true });
}

async function networkFirstApi(req: Request): Promise<Response> {
	const cache = await caches.open(DATA);
	try {
		const res = await fetch(req);
		// API down behind the reverse proxy (502/503/504): treat like no network.
		if (res.status >= 500) throw new Error(`HTTP ${res.status}`);
		if (res.ok) {
			const headers = new Headers(res.headers);
			headers.set(CACHED_AT, new Date().toISOString());
			await cache.put(req, new Response(await res.clone().blob(), { status: 200, headers }));
		}
		return res;
	} catch {
		const hit = await cache.match(req, { ignoreVary: true });
		return (
			hit ??
			new Response(JSON.stringify({ detail: 'offline' }), {
				status: 503,
				headers: { 'content-type': 'application/json' }
			})
		);
	}
}

function hash(text: string): string {
	let h = 0;
	for (let i = 0; i < text.length; i++) h = (Math.imul(31, h) + text.charCodeAt(i)) | 0;
	return (h >>> 0).toString(36);
}
