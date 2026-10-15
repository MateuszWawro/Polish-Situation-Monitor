/** Native share sheet on phones, clipboard elsewhere. */
export async function shareLink(
	url: string,
	title: string
): Promise<'shared' | 'copied' | 'failed'> {
	try {
		if (navigator.share && matchMedia('(pointer: coarse)').matches) {
			await navigator.share({ title, url });
			return 'shared';
		}
		await navigator.clipboard.writeText(url);
		return 'copied';
	} catch (err) {
		// The user closing the share sheet is not an error worth showing.
		return err instanceof DOMException && err.name === 'AbortError' ? 'shared' : 'failed';
	}
}
