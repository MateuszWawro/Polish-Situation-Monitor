import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { poll } from './poll';

function fakeDocument() {
	const listeners = new Set<() => void>();
	return {
		hidden: false,
		addEventListener: (_: string, fn: () => void) => listeners.add(fn),
		removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
		show() {
			this.hidden = false;
			listeners.forEach((fn) => fn());
		},
		listeners
	};
}

describe('poll', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('runs on schedule while visible and sleeps while hidden', () => {
		const doc = fakeDocument();
		const run = vi.fn();
		poll([{ run, everyMs: 60_000 }], doc as unknown as Document);
		vi.advanceTimersByTime(120_000);
		expect(run).toHaveBeenCalledTimes(2);
		doc.hidden = true;
		vi.advanceTimersByTime(600_000);
		expect(run).toHaveBeenCalledTimes(2);
	});

	it('catches up only overdue tasks when the tab comes back', () => {
		const doc = fakeDocument();
		const fast = vi.fn();
		const slow = vi.fn();
		poll(
			[
				{ run: fast, everyMs: 60_000 },
				{ run: slow, everyMs: 3_600_000 }
			],
			doc as unknown as Document
		);
		doc.hidden = true;
		vi.advanceTimersByTime(300_000);
		doc.show();
		expect(fast).toHaveBeenCalledTimes(1); // overdue → refreshed at once
		expect(slow).not.toHaveBeenCalled(); // hourly task not due yet
	});

	it('stops cleanly', () => {
		const doc = fakeDocument();
		const run = vi.fn();
		const stop = poll([{ run, everyMs: 1000 }], doc as unknown as Document);
		stop();
		vi.advanceTimersByTime(10_000);
		expect(run).not.toHaveBeenCalled();
		expect(doc.listeners.size).toBe(0);
	});
});
