<script>
	import { api } from "$lib/api.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import * as Dialog from "$lib/components/ui/dialog/index.js";
	import { Input } from "$lib/components/ui/input/index.js";
	import { Label } from "$lib/components/ui/label/index.js";
	import * as Select from "$lib/components/ui/select/index.js";
	import ScrollArea from "$lib/components/ui/scroll-area/scroll-area.svelte";
	import PenLineIcon from "@lucide/svelte/icons/pen-line";
	import ScanTextIcon from "@lucide/svelte/icons/scan-text";
	import Trash2Icon from "@lucide/svelte/icons/trash-2";

	let { styles = [], fonts = [], selectedId = $bindable(""), refresh } = $props();

	let dialogOpen = $state(false);
	let mode = $state("sample"); // 'sample' | 'font'
	let newName = $state("");
	let fontFile = $state("");
	let sampleFile = $state(null);
	let busy = $state(false);
	let error = $state("");

	async function createStyle() {
		if (!newName.trim()) { error = "Give the style a name"; return; }
		if (mode === "sample" && !sampleFile) { error = "Choose a handwriting sample image"; return; }
		if (mode === "font" && !fontFile) { error = "Pick a base font"; return; }
		busy = true;
		error = "";
		try {
			const style = mode === "sample"
				? await api.styleFromSample(sampleFile, newName.trim(), fontFile || "Caveat.ttf")
				: await api.styleFromFont(newName.trim(), fontFile);
			selectedId = style.id;
			dialogOpen = false;
			newName = ""; sampleFile = null;
			await refresh();
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	async function onDelete(id) {
		if (selectedId === id) selectedId = "";
		await api.deleteStyle(id);
		await refresh();
	}
</script>

<div class="space-y-3">
	<ScrollArea class="h-52 rounded-md border">
		<div class="space-y-1 p-2">
			{#each styles as style (style.id)}
				<div
					class="group flex cursor-pointer items-center justify-between rounded-md border-2 px-3 py-2 transition-all
						{selectedId === style.id ? 'border-primary bg-accent/50' : 'border-transparent hover:border-muted-foreground/40'}"
					role="button" tabindex="0"
					onclick={() => (selectedId = style.id)}
					onkeydown={(e) => e.key === "Enter" && (selectedId = style.id)}
				>
					<div class="min-w-0">
						<p class="truncate text-sm font-medium">{style.name}</p>
						<p class="truncate text-xs text-muted-foreground">
							{style.font_file.replace(".ttf", "")} · slant {style.params.slant_deg}°
						</p>
					</div>
					<div class="flex items-center gap-1">
						<Badge variant={style.source === "sample" ? "default" : "secondary"} class="text-[9px]">
							{style.source === "sample" ? "learned" : "preset"}
						</Badge>
						<Button variant="ghost" size="icon" class="size-6 opacity-0 group-hover:opacity-100"
							onclick={(e) => { e.stopPropagation(); onDelete(style.id); }}>
							<Trash2Icon class="size-3" />
						</Button>
					</div>
				</div>
			{/each}
		</div>
	</ScrollArea>

	<Dialog.Root bind:open={dialogOpen}>
		<Button variant="outline" class="w-full" onclick={() => (dialogOpen = true)}>
			<PenLineIcon class="mr-2 size-4" /> New handwriting style
		</Button>
		<Dialog.Content class="sm:max-w-md">
			<Dialog.Header>
				<Dialog.Title>Create a handwriting style</Dialog.Title>
				<Dialog.Description>
					Learn from a photo of real handwriting, or start from a font preset.
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-4 py-2">
				<div class="flex gap-2">
					<Button variant={mode === "sample" ? "default" : "outline"} class="flex-1" onclick={() => (mode = "sample")}>
						<ScanTextIcon class="mr-2 size-4" /> From sample
					</Button>
					<Button variant={mode === "font" ? "default" : "outline"} class="flex-1" onclick={() => (mode = "font")}>
						<PenLineIcon class="mr-2 size-4" /> From font
					</Button>
				</div>
				<div class="space-y-2">
					<Label for="style-name">Style name</Label>
					<Input id="style-name" bind:value={newName} placeholder="e.g. My cursive" />
				</div>
				{#if mode === "sample"}
					<div class="space-y-2">
						<Label for="sample-file">Handwriting sample photo</Label>
						<Input id="sample-file" type="file" accept="image/*"
							onchange={(e) => (sampleFile = e.target.files?.[0] ?? null)} />
						<p class="text-xs text-muted-foreground">
							A clear photo of handwriting on plain paper works best — a few lines of text.
						</p>
					</div>
				{/if}
				<div class="space-y-2">
					<Label>Base font {mode === "sample" ? "(glyph shapes)" : ""}</Label>
					<Select.Root type="single" bind:value={fontFile}>
						<Select.Trigger class="w-full">
							<Select.Value placeholder="Choose a font" />
						</Select.Trigger>
						<Select.Content>
							{#each fonts as f}
								<Select.Item value={f}>{f.replace(".ttf", "")}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>
				{#if error}<p class="text-xs text-destructive">{error}</p>{/if}
			</div>
			<Dialog.Footer>
				<Button onclick={createStyle} disabled={busy}>
					{busy ? "Learning…" : mode === "sample" ? "Learn style" : "Create style"}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
</div>
