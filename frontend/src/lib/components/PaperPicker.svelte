<script>
	import { api } from "$lib/api.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import ScrollArea from "$lib/components/ui/scroll-area/scroll-area.svelte";
	import ImagePlusIcon from "@lucide/svelte/icons/image-plus";
	import RefreshCwIcon from "@lucide/svelte/icons/refresh-cw";
	import Trash2Icon from "@lucide/svelte/icons/trash-2";

	let { papers = [], selectedIds = $bindable([]), refresh } = $props();

	let uploading = $state(false);
	let error = $state("");

	function toggle(id) {
		selectedIds = selectedIds.includes(id)
			? selectedIds.filter((p) => p !== id)
			: [...selectedIds, id];
	}

	async function onUpload(event) {
		const file = event.target.files?.[0];
		if (!file) return;
		uploading = true;
		error = "";
		try {
			const paper = await api.uploadPaper(file, file.name.replace(/\.[^.]+$/, ""));
			selectedIds = [...selectedIds, paper.id];
			await refresh();
		} catch (e) {
			error = e.message;
		} finally {
			uploading = false;
			event.target.value = "";
		}
	}

	async function onDelete(id) {
		selectedIds = selectedIds.filter((p) => p !== id);
		await api.deletePaper(id);
		await refresh();
	}

	async function onRedetect(id) {
		await api.redetectPaper(id);
		await refresh();
	}
</script>

<div class="space-y-3">
	<ScrollArea class="h-64 rounded-md border">
		<div class="grid grid-cols-2 gap-2 p-2">
			{#each papers as paper (paper.id)}
				{@const order = selectedIds.indexOf(paper.id)}
				<div
					class="group relative cursor-pointer overflow-hidden rounded-md border-2 transition-all
						{order >= 0 ? 'border-primary ring-2 ring-primary/30' : 'border-transparent hover:border-muted-foreground/40'}"
					role="button"
					tabindex="0"
					onclick={() => toggle(paper.id)}
					onkeydown={(e) => e.key === "Enter" && toggle(paper.id)}
				>
					<img src={api.paperThumb(paper)} alt={paper.name} class="aspect-[3/4] w-full object-cover" />
					{#if order >= 0}
						<span class="absolute left-1.5 top-1.5 flex size-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground shadow">
							{order + 1}
						</span>
					{/if}
					<div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-1.5 pt-4">
						<p class="truncate text-[11px] font-medium text-white">{paper.name}</p>
						<Badge variant={paper.quad ? "default" : "secondary"} class="mt-0.5 h-4 px-1 text-[9px]">
							{paper.quad ? "page detected" : "full frame"}
						</Badge>
					</div>
					<div class="absolute right-1 top-1 hidden gap-1 group-hover:flex">
						<Button variant="secondary" size="icon" class="size-6" title="Re-detect page"
							onclick={(e) => { e.stopPropagation(); onRedetect(paper.id); }}>
							<RefreshCwIcon class="size-3" />
						</Button>
						<Button variant="destructive" size="icon" class="size-6" title="Delete"
							onclick={(e) => { e.stopPropagation(); onDelete(paper.id); }}>
							<Trash2Icon class="size-3" />
						</Button>
					</div>
				</div>
			{/each}
		</div>
	</ScrollArea>

	<label class="block">
		<input type="file" accept="image/*" class="hidden" onchange={onUpload} disabled={uploading} />
		<Button variant="outline" class="w-full" disabled={uploading} type="button"
			onclick={(e) => e.currentTarget.parentElement.querySelector("input").click()}>
			<ImagePlusIcon class="mr-2 size-4" />
			{uploading ? "Uploading…" : "Upload paper photo"}
		</Button>
	</label>
	{#if error}<p class="text-xs text-destructive">{error}</p>{/if}
	<p class="text-xs text-muted-foreground">
		Click to assign papers to pages in order — page 1 uses paper 1, and so on (selection repeats if text needs more pages).
	</p>
</div>
