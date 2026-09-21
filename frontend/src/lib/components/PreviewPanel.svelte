<script>
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import DownloadIcon from "@lucide/svelte/icons/download";
	import ChevronLeftIcon from "@lucide/svelte/icons/chevron-left";
	import ChevronRightIcon from "@lucide/svelte/icons/chevron-right";
	import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
	import PenLineIcon from "@lucide/svelte/icons/pen-line";

	let { result = null, rendering = false } = $props();

	let pageIndex = $state(0);
	let pages = $derived(result?.pages ?? []);
	let current = $derived(pages[Math.min(pageIndex, pages.length - 1)]);

	$effect(() => {
		if (result) pageIndex = 0;
	});

	function download(url, name) {
		const a = document.createElement("a");
		a.href = url;
		a.download = name;
		a.click();
	}
</script>

<div class="flex h-full flex-col">
	{#if rendering}
		<div class="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
			<LoaderCircleIcon class="size-10 animate-spin" />
			<p class="text-sm">Writing by hand…</p>
		</div>
	{:else if current}
		<div class="flex items-center justify-between border-b px-4 py-2">
			<div class="flex items-center gap-2">
				<Button variant="outline" size="icon" class="size-7" disabled={pageIndex === 0}
					onclick={() => (pageIndex -= 1)}>
					<ChevronLeftIcon class="size-4" />
				</Button>
				<span class="text-sm text-muted-foreground">Page {pageIndex + 1} / {pages.length}</span>
				<Button variant="outline" size="icon" class="size-7" disabled={pageIndex >= pages.length - 1}
					onclick={() => (pageIndex += 1)}>
					<ChevronRightIcon class="size-4" />
				</Button>
				<Badge variant="secondary">{pages.length} page{pages.length > 1 ? "s" : ""}</Badge>
			</div>
			<div class="flex gap-2">
				<Button variant="outline" size="sm" onclick={() => download(current.url, current.output_file)}>
					<DownloadIcon class="mr-1.5 size-3.5" /> This page
				</Button>
				<Button variant="outline" size="sm"
					onclick={() => pages.forEach((p) => download(p.url, p.output_file))}>
					<DownloadIcon class="mr-1.5 size-3.5" /> All pages
				</Button>
			</div>
		</div>
		<div class="flex-1 overflow-auto bg-muted/40 p-6">
			<img src={current.url} alt="Handwritten page {pageIndex + 1}"
				class="mx-auto max-h-full max-w-full rounded-sm shadow-2xl" />
		</div>
	{:else}
		<div class="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
			<PenLineIcon class="size-10" />
			<p class="text-sm">Your handwritten pages will appear here</p>
			<p class="max-w-xs text-center text-xs">
				Paste text, pick paper and a handwriting style, then press <strong>Write it</strong>.
			</p>
		</div>
	{/if}
</div>
