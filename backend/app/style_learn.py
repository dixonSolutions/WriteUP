"""Learn a handwriting style profile from a sample image using computer vision.

No heavy ML — classical CV measurements that capture what makes handwriting
*look* like a specific person's hand:

- ink colour        — median colour of ink pixels
- slant             — shear angle maximising vertical-projection variance
- glyph height      — robust median of connected-component heights
- line spacing      — distance between text lines (projection profile)
- baseline wander   — how much glyph bottoms deviate from the line baseline
- size variance     — spread of glyph heights (→ per-glyph scale jitter)
- char spacing      — median gap between adjacent components on a line

All lengths are returned both in pixels and normalised relative to the sample
image height, so a style learned from a small phone photo transfers cleanly to
a page rendered at any resolution.
"""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_PARAMS: dict = {
    "ink_color": [30, 30, 120],          # BGR ballpoint blue
    "slant_deg": 0.0,
    "glyph_height_rel": 0.022,           # fraction of image height
    "line_spacing_ratio": 2.1,           # line pitch / glyph height
    "baseline_wander_ratio": 0.10,       # baseline std-dev / glyph height
    "size_variance": 0.08,               # glyph-height spread (std/mean)
    "char_spacing_ratio": 0.28,          # inter-char gap / glyph height
    "word_spacing_ratio": 0.85,          # inter-word gap / glyph height
}


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Binary mask of ink pixels (255 = ink)."""
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    mask = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=31, C=15)
    # Remove speckle noise.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return mask


def _estimate_slant(mask: np.ndarray) -> float:
    """Slant angle in degrees (positive = leans right).

    Classic approach: shear the ink mask by candidate angles and pick the one
    that maximises the variance of the vertical projection profile.
    """
    h, w = mask.shape
    best_angle, best_score = 0.0, -1.0
    ink = (mask > 0).astype(np.float32)
    for angle in np.linspace(-30, 30, 61):
        shear = np.tan(np.deg2rad(angle))
        M = np.float32([[1, shear, 0], [0, 1, 0]])
        sheared = cv2.warpAffine(ink, M, (int(w + abs(shear) * h), h))
        proj = sheared.sum(axis=0)
        score = float(proj.var())
        if score > best_score:
            best_score, best_angle = score, float(angle)
    return best_angle


def _line_pitch(mask: np.ndarray) -> float | None:
    """Median distance between text lines via the horizontal projection."""
    proj = (mask > 0).sum(axis=1).astype(np.float32)
    if proj.max() == 0:
        return None
    thresh = proj.max() * 0.08
    rows = proj > thresh
    # Find contiguous inked bands.
    bands, start = [], None
    for i, on in enumerate(rows):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 3:
                bands.append((start, i))
            start = None
    if start is not None:
        bands.append((start, len(rows)))
    if len(bands) < 2:
        return None
    centers = [(a + b) / 2 for a, b in bands]
    pitches = np.diff(centers)
    return float(np.median(pitches))


def measure_font_slant(font_path: str) -> float:
    """A font's built-in visual slant, measured by rendering reference text.

    Lets the renderer apply only the *difference* between a sample's measured
    slant and the font's natural lean, avoiding double-slanting.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", (1600, 320), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, 96)
    draw.text((60, 80), "Handwriting Slant Test Zz Yy Ll", font=font, fill=0)
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = _binarize(gray)
    return _estimate_slant(mask)


def learn_from_image(image_bgr: np.ndarray) -> dict:
    """Measure a handwriting sample and return a style parameter dict."""
    params = dict(DEFAULT_PARAMS)
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mask = _binarize(gray)

    ink_px = image_bgr[mask > 0]
    if len(ink_px) < 50:
        return params  # essentially blank sample → defaults

    # --- ink colour (median is robust to paper shadows caught in the mask)
    params["ink_color"] = [int(v) for v in np.median(ink_px, axis=0)]

    # --- connected components ≈ glyphs / glyph fragments
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    heights, widths, areas, xs, ys, bottoms = [], [], [], [], [], []
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        if area < 8 or ch < 4 or cw < 1:
            continue
        if ch > h * 0.5 or cw > w * 0.5:
            continue  # ruled lines / borders, not glyphs
        heights.append(ch); widths.append(cw); areas.append(area)
        xs.append(x); ys.append(y); bottoms.append(y + ch)
    if len(heights) < 10:
        return params

    heights_a = np.array(heights, dtype=np.float32)
    # Robust glyph height: median of the upper half (ascendered letters define
    # the visual size; tiny fragments like dots pull the plain median down).
    glyph_h = float(np.median(heights_a[heights_a >= np.median(heights_a)]))
    params["glyph_height_rel"] = round(glyph_h / h, 5)
    params["size_variance"] = round(
        float(np.std(heights_a) / max(np.mean(heights_a), 1e-6)) * 0.5, 4)

    # --- slant
    params["slant_deg"] = round(_estimate_slant(mask), 2)

    # --- line pitch → spacing ratio
    pitch = _line_pitch(mask)
    if pitch and pitch > glyph_h:
        params["line_spacing_ratio"] = round(pitch / glyph_h, 3)

    # --- baseline wander: std of component bottoms within each line band
    proj = (mask > 0).sum(axis=1).astype(np.float32)
    rows = proj > proj.max() * 0.08
    bands, start = [], None
    for i, on in enumerate(rows):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 3:
                bands.append((start, i))
            start = None
    if start is not None:
        bands.append((start, len(rows)))
    devs = []
    for a, b in bands:
        line_bottoms = [bt for y, bt in zip(ys, bottoms) if a - glyph_h < y < b + 2]
        if len(line_bottoms) >= 4:
            devs.append(np.std(line_bottoms))
    if devs:
        params["baseline_wander_ratio"] = round(
            min(float(np.mean(devs)) / glyph_h, 0.6), 4)

    # --- char / word spacing from horizontal gaps inside line bands
    gaps = []
    for a, b in bands[:8]:
        band = mask[a:b, :]
        col_has_ink = (band > 0).sum(axis=0) > 0
        gap, run = [], 0
        for on in col_has_ink:
            if not on:
                run += 1
            elif run:
                gap.append(run); run = 0
        gaps.extend(g for g in gap if g >= 1)
    if gaps:
        gaps_a = np.array(gaps, dtype=np.float32)
        small = gaps_a[gaps_a <= np.percentile(gaps_a, 60)]
        large = gaps_a[gaps_a > np.percentile(gaps_a, 60)]
        if len(small):
            params["char_spacing_ratio"] = round(
                min(float(np.median(small)) / glyph_h, 1.5), 4)
        if len(large):
            params["word_spacing_ratio"] = round(
                min(float(np.median(large)) / glyph_h, 3.0), 4)

    return params
