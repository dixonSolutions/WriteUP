<script>
	import { Label } from "$lib/components/ui/label/index.js";
	import * as Select from "$lib/components/ui/select/index.js";
	import Separator from "$lib/components/ui/separator/separator.svelte";
	import Slider from "$lib/components/ui/slider/slider.svelte";
	import Switch from "$lib/components/ui/switch/switch.svelte";
	import { Input } from "$lib/components/ui/input/index.js";
	import DicesIcon from "@lucide/svelte/icons/dices";

	let { settings = $bindable({}) } = $props();

	const INK_PRESETS = [
		{ name: "Ballpoint blue", rgb: [30, 30, 120] },
		{ name: "Black gel", rgb: [25, 25, 28] },
		{ name: "Pencil", rgb: [90, 90, 95] },
		{ name: "Fountain navy", rgb: [20, 35, 90] },
		{ name: "Red pen", rgb: [150, 25, 30] },
		{ name: "Forest ink", rgb: [25, 70, 45] },
	];

	function toHex([r, g, b]) {
		return "#" + [r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("");
	}
	function fromHex(hex) {
		const n = parseInt(hex.slice(1), 16);
		return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
	}

	let inkAuto = $derived(settings.ink_color === null);
	let slantAuto = $derived(settings.slant_deg === null);
</script>

{#snippet sliderRow(label, key, min, max, step, fmt, disabled = false)}
	<div class="space-y-1.5 {disabled ? 'pointer-events-none opacity-40' : ''}">
		<div class="flex items-center justify-between">
			<Label class="text-xs">{label}</Label>
			<span class="font-mono text-xs text-muted-foreground">{fmt(settings[key])}</span>
		</div>
		<Slider type="single" bind:value={settings[key]} {min} {max} {step} {disabled} />
	</div>
{/snippet}

<div class="space-y-5">
	<!-- Layout -->
	<div class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Layout</p>
		{@render sliderRow("Writing size", "font_size_rel", 0.01, 0.05, 0.001, (v) => `${(v * 100).toFixed(1)}%`)}
		{@render sliderRow("Line spacing", "line_spacing_mult", 0.6, 2.5, 0.05, (v) => `${v.toFixed(2)}×`)}
		<div class="grid grid-cols-2 gap-3">
			{@render sliderRow("Pad top", "padding_top", 0, 0.3, 0.005, (v) => `${(v * 100).toFixed(1)}%`)}
			{@render sliderRow("Pad bottom", "padding_bottom", 0, 0.3, 0.005, (v) => `${(v * 100).toFixed(1)}%`)}
			{@render sliderRow("Pad left", "padding_left", 0, 0.3, 0.005, (v) => `${(v * 100).toFixed(1)}%`)}
			{@render sliderRow("Pad right", "padding_right", 0, 0.3, 0.005, (v) => `${(v * 100).toFixed(1)}%`)}
		</div>
	</div>

	<Separator />

	<!-- Ink -->
	<div class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ink</p>
		<div class="flex items-center justify-between">
			<Label class="text-xs">Learned ink colour</Label>
			<Switch checked={inkAuto} onCheckedChange={(v) => (settings.ink_color = v ? null : [30, 30, 120])} />
		</div>
		{#if !inkAuto}
			<div class="flex items-center gap-2">
				<input type="color" value={toHex(settings.ink_color ?? [30, 30, 120])}
					oninput={(e) => (settings.ink_color = fromHex(e.target.value))}
					class="h-8 w-10 cursor-pointer rounded border" />
				<Select.Root type="single"
					value={toHex(settings.ink_color ?? [30, 30, 120])}
					onValueChange={(v) => (settings.ink_color = fromHex(v))}>
					<Select.Trigger class="h-8 flex-1"><Select.Value /></Select.Trigger>
					<Select.Content>
						{#each INK_PRESETS as p}
							<Select.Item value={toHex(p.rgb)}>{p.name}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>
		{/if}
		{@render sliderRow("Opacity", "opacity", 0.4, 1, 0.01, (v) => `${Math.round(v * 100)}%`)}
		{@render sliderRow("Softness (blur)", "blur", 0, 1.5, 0.05, (v) => `${v.toFixed(2)}px`)}
		{@render sliderRow("Ink grain", "grain", 0, 0.8, 0.02, (v) => `${Math.round(v * 100)}%`)}
	</div>

	<Separator />

	<!-- Hand -->
	<div class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Hand</p>
		<div class="flex items-center justify-between">
			<Label class="text-xs">Learned slant</Label>
			<Switch checked={slantAuto} onCheckedChange={(v) => (settings.slant_deg = v ? null : 6)} />
		</div>
		<div class="space-y-1.5 {slantAuto ? 'pointer-events-none opacity-40' : ''}">
			<div class="flex items-center justify-between">
				<Label class="text-xs">Slant</Label>
				<span class="font-mono text-xs text-muted-foreground">
					{slantAuto ? "auto" : `${settings.slant_deg.toFixed(1)}°`}
				</span>
			</div>
			<Slider type="single" value={settings.slant_deg ?? 0}
				onValueChange={(v) => (settings.slant_deg = v)}
				min={-25} max={25} step={0.5} disabled={slantAuto} />
		</div>
		{@render sliderRow("Rotation jitter", "jitter_rotation", 0, 6, 0.1, (v) => `±${v.toFixed(1)}°`)}
		{@render sliderRow("Size jitter", "jitter_scale", 0, 2.5, 0.05, (v) => `${v.toFixed(2)}×`)}
		{@render sliderRow("Baseline wander", "jitter_baseline", 0, 2.5, 0.05, (v) => `${v.toFixed(2)}×`)}
		{@render sliderRow("Spacing jitter", "jitter_spacing", 0, 2.5, 0.05, (v) => `${v.toFixed(2)}×`)}
	</div>

	<Separator />

	<!-- Variation seed -->
	<div class="space-y-2">
		<p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Variation</p>
		<div class="flex items-center gap-2">
			<Input type="number" bind:value={settings.seed} class="h-8 w-24" />
			<button type="button" title="Re-roll handwriting variation"
				class="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs hover:bg-accent"
				onclick={() => (settings.seed = Math.floor(Math.random() * 100000))}>
				<DicesIcon class="size-3.5" /> Re-roll
			</button>
			<span class="text-xs text-muted-foreground">same seed → same hand</span>
		</div>
	</div>
</div>
