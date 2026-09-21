<script>
	import { onMount } from "svelte";
	import { api } from "$lib/api.js";
	import PaperPicker from "$lib/components/PaperPicker.svelte";
	import StylePicker from "$lib/components/StylePicker.svelte";
	import TunePanel from "$lib/components/TunePanel.svelte";
	import PreviewPanel from "$lib/components/PreviewPanel.svelte";
	import { Button } from "$lib/components/ui/button/index.js";
	import * as Card from "$lib/components/ui/card/index.js";
	import { Textarea } from "$lib/components/ui/textarea/index.js";
	import * as Tabs from "$lib/components/ui/tabs/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import ScrollArea from "$lib/components/ui/scroll-area/scroll-area.svelte";
	import Separator from "$lib/components/ui/separator/separator.svelte";
	import MoonIcon from "@lucide/svelte/icons/moon";
	import SunIcon from "@lucide/svelte/icons/sun";
	import PenLineIcon from "@lucide/svelte/icons/pen-line";
	import HistoryIcon from "@lucide/svelte/icons/history";
	import Trash2Icon from "@lucide/svelte/icons/trash-2";

	const DEFAULT_SETTINGS = {
		font_size_rel: 0.021,
		line_spacing_mult: 1.0,
		padding_top: 0.10,
		padding_bottom: 0.09,
		padding_left: 0.10,
		padding_right: 0.09,
		ink_color: null,
		slant_deg: null,
		jitter_rotation: 1.6,
		jitter_scale: 1.0,
		jitter_baseline: 1.0,
		jitter_spacing: 1.0,
		opacity: 0.92,
		blur: 0.45,
		grain: 0.30,
		seed: 7,
	};

	let text = $state("");
	let papers = $state([]);
	let styles = $state([]);
	let fonts = $state([]);
	let renders = $state([]);
	let selectedPaperIds = $state([]);
	let selectedStyleId = $state("");
	let settings = $state({ ...DEFAULT_SETTINGS });
	let result = $state(null);
	let rendering = $state(false);
	let error = $state("");
	let dark = $state(false);

	$effect(() => {
		document.documentElement.classList.toggle("dark", dark);
	});

	async function refreshPapers() { papers = await api.papers(); }
	async function refreshStyles() { styles = await api.styles(); }
	async function refreshRenders() { renders = await api.renders(); }

	onMount(async () => {
		try {
			[papers, styles, fonts, renders] = await Promise.all([
				api.papers(), api.styles(), api.fonts(), api.renders(),
			]);
			if (papers.length) selectedPaperIds = [papers[0].id];
			if (styles.length) selectedStyleId = styles[0].id;
		} catch (e) {
			error = `Cannot reach the WriteUP API — is the backend running? (${e.message})`;
		}
	});

	async function generate() {
		error = "";
		if (!text.trim()) { error = "Paste or type some text first."; return; }
		if (!selectedPaperIds.length) { error = "Select at least one paper."; return; }
		if (!selectedStyleId) { error = "Select a handwriting style."; return; }
		rendering = true;
		try {
			result = await api.render(text, selectedPaperIds, selectedStyleId, settings);
			await refreshRenders();
		} catch (e) {
			error = e.message;
		} finally {
			rendering = false;
		}
	}

	async function loadRender(r) {
		result = r;
		text = r.text;
		if (r.style_id) selectedStyleId = r.style_id;
		settings = { ...DEFAULT_SETTINGS, ...r.settings };
		selectedPaperIds = r.pages.map((p) => p.paper_id)
			.filter((v, i, a) => a.indexOf(v) === i);
	}

	async function deleteRender(id) {
		await api.deleteRender(id);
		if (result?.id === id) result = null;
		await refreshRenders();
	}
</script>

<div class="flex h-screen flex-col bg-background">
	<!-- Header -->
	<header class="flex items-center justify-between border-b px-5 py-3">
		<div class="flex items-center gap-2.5">
			<div class="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
				<PenLineIcon class="size-4.5" />
			</div>
			<div>
				<h1 class="text-lg font-bold leading-none tracking-tight">WriteUP</h1>
				<p class="text-xs text-muted-foreground">Realistic handwritten pages from plain text</p>
			</div>
		</div>
		<Button variant="ghost" size="icon" onclick={() => (dark = !dark)} title="Toggle theme">
			{#if dark}<SunIcon class="size-4" />{:else}<MoonIcon class="size-4" />{/if}
		</Button>
	</header>

	<div class="flex min-h-0 flex-1">
		<!-- Control sidebar -->
		<aside class="w-[400px] shrink-0 border-r">
			<ScrollArea class="h-full">
				<div class="space-y-4 p-4">
					{#if error}
						<div class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
							{error}
						</div>
					{/if}

					<Card.Root>
						<Card.Header class="pb-3">
							<Card.Title class="text-sm">Your text</Card.Title>
							<Card.Description>Paste anything — it flows across pages automatically.</Card.Description>
						</Card.Header>
						<Card.Content>
							<Textarea bind:value={text} rows={7} placeholder="Dear Diary, …" class="resize-y" />
							<p class="mt-1.5 text-right text-xs text-muted-foreground">{text.length} chars</p>
						</Card.Content>
					</Card.Root>

					<Card.Root>
						<Card.Header class="pb-3">
							<Card.Title class="text-sm">Paper</Card.Title>
							<Card.Description>Photos of paper — the page is found by computer vision.</Card.Description>
						</Card.Header>
						<Card.Content>
							<PaperPicker {papers} bind:selectedIds={selectedPaperIds} refresh={refreshPapers} />
						</Card.Content>
					</Card.Root>

					<Card.Root>
						<Card.Header class="pb-3">
							<Card.Title class="text-sm">Handwriting style</Card.Title>
							<Card.Description>Learned from real samples, or font presets.</Card.Description>
						</Card.Header>
						<Card.Content>
							<StylePicker {styles} {fonts} bind:selectedId={selectedStyleId} refresh={refreshStyles} />
						</Card.Content>
					</Card.Root>

					<Card.Root>
						<Card.Header class="pb-3">
							<Card.Title class="text-sm">Fine-tune</Card.Title>
							<Card.Description>Everything is adjustable.</Card.Description>
						</Card.Header>
						<Card.Content>
							<TunePanel bind:settings />
						</Card.Content>
					</Card.Root>

					<Button class="w-full" size="lg" onclick={generate} disabled={rendering}>
						<PenLineIcon class="mr-2 size-4" />
						{rendering ? "Writing…" : "Write it"}
					</Button>

					{#if renders.length}
						<Separator />
						<div class="space-y-2 pb-4">
							<div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
								<HistoryIcon class="size-3.5" /> Recent renders
							</div>
							{#each renders.slice(0, 8) as r (r.id)}
								<div class="group flex items-center justify-between rounded-md border px-3 py-2 text-xs hover:bg-accent/50">
									<button type="button" class="min-w-0 flex-1 cursor-pointer text-left" onclick={() => loadRender(r)}>
										<p class="truncate font-medium">{r.text.slice(0, 60) || "(blank)"}</p>
										<p class="text-muted-foreground">
											{new Date(r.created_at * 1000).toLocaleString()} · {r.pages.length}p
										</p>
									</button>
									<Button variant="ghost" size="icon" class="size-6 opacity-0 group-hover:opacity-100"
										onclick={() => deleteRender(r.id)}>
										<Trash2Icon class="size-3" />
									</Button>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</ScrollArea>
		</aside>

		<!-- Preview -->
		<main class="min-w-0 flex-1">
			<PreviewPanel {result} {rendering} />
		</main>
	</div>
</div>
