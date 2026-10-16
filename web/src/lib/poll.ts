export interface PollTask {
	run: () => unknown;
	everyMs: number;
}

/**
 * Periodic refresh that sleeps while the tab is hidden (no network, no battery) and, when the
 * tab comes back, immediately re-runs every task that is overdue. Returns a stop function.
 */
export function poll(
	tasks: PollTask[],
	doc: Pick<Document, 'hidden' | 'addEventListener' | 'removeEventListener'> = document
) {
	const lastRun = tasks.map(() => Date.now());
	const runIfDue = (i: number, force = false) => {
		if (doc.hidden) return;
		if (!force && Date.now() - lastRun[i] < tasks[i].everyMs) return;
		lastRun[i] = Date.now();
		tasks[i].run();
	};
	const timers = tasks.map((t, i) => setInterval(() => runIfDue(i, true), t.everyMs));
	const onVisibility = () => tasks.forEach((_, i) => runIfDue(i));
	doc.addEventListener('visibilitychange', onVisibility);
	return () => {
		timers.forEach(clearInterval);
		doc.removeEventListener('visibilitychange', onVisibility);
	};
}
