// User's places ("Moja okolica"), stored only on this device in IndexedDB (privacy rule:
// the server never learns place names or coordinates – only powiat codes when asked).

export const MAX_PLACES = 5;

export interface Place {
	id: string;
	/** User's own name, e.g. "Dom". */
	name: string;
	/** 4-digit powiat TERYT. */
	teryt: string;
	/** Human description of the area, e.g. "Krosno, powiat Krosno, woj. podkarpackie". */
	area: string;
	/** Optional [lon, lat] from "use my location"; never sent anywhere. */
	point?: [number, number];
	createdAt: string;
}

const DB = 'psm';
const STORE = 'places';

function open(): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		const req = indexedDB.open(DB, 1);
		req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id' });
		req.onsuccess = () => resolve(req.result);
		req.onerror = () => reject(req.error);
	});
}

async function run<T>(mode: IDBTransactionMode, op: (s: IDBObjectStore) => IDBRequest<T>) {
	const db = await open();
	try {
		return await new Promise<T>((resolve, reject) => {
			const req = op(db.transaction(STORE, mode).objectStore(STORE));
			req.onsuccess = () => resolve(req.result);
			req.onerror = () => reject(req.error);
		});
	} finally {
		db.close();
	}
}

export async function loadPlaces(): Promise<Place[]> {
	const places = await run<Place[]>('readonly', (s) => s.getAll());
	return places.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export const savePlace = (place: Place) => run('readwrite', (s) => s.put(place));
export const deletePlace = (id: string) => run('readwrite', (s) => s.delete(id));
