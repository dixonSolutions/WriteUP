# WriteUP — Functionality & How It Works

## User flow

1. **Paste text** — any length; WriteUP word-wraps and paginates automatically.
2. **Choose paper image(s)** — from the built-in gallery or upload a photo.
   Multiple selections map to pages in order (1st pick → page 1, …, repeating).
3. **Choose a handwriting style** — a preset, or one *learned from a photo of
   real handwriting*.
4. **Fine-tune** (optional) — every rendering parameter is adjustable.
5. **Write it** — pages render server-side and appear in the preview;
   download individually or all at once. Renders are kept in history.

## Settings reference

| Setting | Range | Meaning |
|---|---|---|
| Writing size | 0.8–8 % of page height | Visible cap-height of glyphs; scales with the page |
| Line spacing | 0.6–2.5 × | Multiplies the style's learned line pitch |
| Padding (4 sides) | 0–30 % | Writable-area margins inside the page |
| Ink colour | auto / RGB | `auto` uses the colour learned from the sample |
| Opacity | 40–100 % | Ink alpha |
| Softness | 0–1.5 px | Gaussian blur on the ink layer |
| Ink grain | 0–80 % | Per-pixel alpha noise (ink soaking into fibres) |
| Slant | auto / −25…25° | `auto` uses the learned slant |
| Rotation jitter | 0–6° | Per-glyph rotation std-dev |
| Size jitter | 0–2.5 × | Multiplies learned glyph-size variance |
| Baseline wander | 0–2.5 × | Multiplies learned baseline deviation |
| Spacing jitter | 0–2.5 × | Randomness in inter-character gaps |
| Seed | integer | Same seed + settings → identical handwriting |

## How the CV works

### Page detection (`backend/app/cv_page.py`)

1. Downscale to ≤1000 px, grayscale, bilateral filter.
2. **Strategy A** — Otsu threshold (paper is usually the brightest large
   region) → morphological close → largest 4-point contour.
3. **Strategy B** — Canny edges → dilate/close → largest 4-point contour.
4. Fallback — minimum-area rectangle of the largest contour; if that fails or
   the quad covers >92 % of the frame, the photo is treated as borderless.
5. **Border-brightness heuristic** — if the ring outside the quad is ≥72 % as
   bright as the interior, the "background" is really more paper (vignette on
   a full-frame shot) → treat the whole frame as the page.
6. Corners are ordered TL, TR, BR, BL via sum/difference of coordinates.

### Style learning (`backend/app/style_learn.py`)

From a sample photo: adaptive binarisation → connected components (glyphs) →
robust statistics. Slant is the shear angle maximising vertical-projection
variance. The chosen base font's *natural* slant is measured the same way and
subtracted, so only the sample's *extra* lean is applied at render time.
All lengths are stored relative to image height → resolution-independent.

### Rendering (`backend/app/renderer.py`)

1. Rectify page to a canonical 1600 px-tall space (homography from the quad).
2. Word-wrap with calibrated font metrics (PIL size chosen so the visible cap
   height equals `font_size_rel × page height`).
3. Draw each glyph on its own tile → random scale/rotate → alpha-composite at
   the pen position with baseline wander and spacing jitter.
4. Whole-block slant shear, ink grain, micro-blur, opacity.
5. Inverse-warp into the photo; multiply-composite (`base·ink/255`) so ink
   darkens paper fibres instead of painting over them.

## Data store

Everything lives in `data/`:

```
data/writeup.db   SQLite: papers, styles, renders, settings
data/papers/      paper photos (gallery_*.jpg are generated on first run)
data/samples/     handwriting samples used for learning
data/fonts/       12 OFL handwriting fonts
data/outputs/     rendered pages (<render_id>_p<n>.jpg)
data/thumbs/      paper thumbnails for the UI
```

## Security

- All validation/clamping server-side (`_merged_settings`); the UI is a view.
- Uploads size-limited (25 MB) and decoded through OpenCV (no raw file writes).
- Static file serving resolves paths and verifies directory containment.
- CORS restricted to the Vite dev origin.
