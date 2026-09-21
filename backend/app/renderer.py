"""Realistic handwriting renderer.

Renders text as handwriting onto photographed paper:

1. Rectify the page (canonical space) using the detected quad.
2. Lay out text with word-wrap inside the padded writable area; the font size
   is a fraction of page height, so text scales with the page.
3. Draw every glyph individually with per-character rotation, scale, baseline
   offset and spacing jitter sampled from the learned style profile.
4. Apply slant, micro-blur, ink grain and opacity.
5. Warp the ink layer back into the photo's perspective and composite with a
   multiply blend so the ink darkens the paper fibres like a real pen.
"""
from __future__ import annotations

import math
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import cv_page

DEFAULT_SETTINGS: dict = {
    "font_size_rel": 0.021,      # glyph height as a fraction of page height
    "line_spacing_mult": 1.0,    # multiplies the style's line-spacing ratio
    "padding_top": 0.10,         # fractions of page height/width
    "padding_bottom": 0.09,
    "padding_left": 0.10,
    "padding_right": 0.09,
    "ink_color": None,           # [r,g,b] override; None → learned from sample
    "slant_deg": None,           # override; None → learned
    "jitter_rotation": 1.6,      # per-glyph rotation std-dev (degrees)
    "jitter_scale": 1.0,         # multiplies learned size variance
    "jitter_baseline": 1.0,      # multiplies learned baseline wander
    "jitter_spacing": 1.0,       # multiplies learned spacing variance
    "opacity": 0.92,
    "blur": 0.45,                # gaussian blur radius on ink layer (px)
    "grain": 0.30,               # alpha noise amount (ink soak/grain)
    "seed": 7,
}

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_NOTDEF_CACHE: dict[int, bytes] = {}

# Common Unicode punctuation → ASCII lookalikes when a font lacks the glyph.
_CHAR_FALLBACKS = str.maketrans({
    "—": "-", "–": "-", "―": "-",
    "“": '"', "”": '"', "„": '"',
    "‘": "'", "’": "'", "‚": "'",
    "…": "...", "•": "*", "·": ".",
    "×": "x", "÷": "/", "−": "-",
})


def _font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (font_path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(font_path, size)
    return _FONT_CACHE[key]


def _supported(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    """True when the font has a real glyph for ch (not the .notdef box)."""
    key = id(font)
    if key not in _NOTDEF_CACHE:
        _NOTDEF_CACHE[key] = font.getbbox("￾")  # U+FFFE → .notdef glyph
    return font.getbbox(ch) != _NOTDEF_CACHE[key]


def _sanitize(text: str, font: ImageFont.FreeTypeFont) -> str:
    """Replace glyphs the font cannot draw with close ASCII equivalents."""
    text = text.translate(_CHAR_FALLBACKS)
    return "".join(ch if ch in "\n " or _supported(font, ch) else "-" for ch in text)


def _calibrated_size(font_path: str, target_ink_h: float) -> int:
    """PIL point size whose *visible cap height* equals target_ink_h pixels."""
    ref = 100
    f = _font(font_path, ref)
    bbox = f.getbbox("X")
    ink_h = max(bbox[3] - bbox[1], 1)
    return max(6, int(round(ref * target_ink_h / ink_h)))


# ------------------------------------------------------------------ layout
def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float,
               char_space: float, word_space: float) -> list[str]:
    """Greedy word-wrap; returns the flat list of lines for all pages."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            width = font.getlength(candidate) + char_space * len(candidate)
            if current and width > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)  # keeps intentional blank lines
    return lines


def paginate(lines: list[str], lines_per_page: int) -> list[list[str]]:
    return [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]


# ------------------------------------------------------------------ render
def _render_ink_layer(lines: list[str], font_path: str, params: dict,
                      settings: dict, page_w: int, page_h: int) -> np.ndarray:
    """Draw one page of handwriting; returns an RGBA uint8 layer."""
    rng = random.Random(settings["seed"])
    np_rng = np.random.default_rng(settings["seed"])

    glyph_h = settings["font_size_rel"] * page_h
    font = _font(font_path, _calibrated_size(font_path, glyph_h))
    ascent, _ = font.getmetrics()

    line_pitch = glyph_h * params["line_spacing_ratio"] * settings["line_spacing_mult"]
    char_space = params["char_spacing_ratio"] * glyph_h
    word_space = params["word_spacing_ratio"] * glyph_h
    baseline_wander = params["baseline_wander_ratio"] * glyph_h * settings["jitter_baseline"]
    scale_var = params["size_variance"] * settings["jitter_scale"]

    left = settings["padding_left"] * page_w
    top = settings["padding_top"] * page_h

    ink_rgb = settings["ink_color"] or [params["ink_color"][2],
                                        params["ink_color"][1],
                                        params["ink_color"][0]]  # BGR→RGB

    layer = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))

    for li, line in enumerate(lines):
        y_line = top + li * line_pitch
        pen_x = left
        for ch in line:
            if ch == " ":
                pen_x += word_space
                continue
            bbox = font.getbbox(ch)
            if bbox is None:
                pen_x += font.getlength(ch) + char_space
                continue
            x0, y0, x1, y1 = bbox
            pad = max(4, int(glyph_h * 0.25))
            tile_w, tile_h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad

            # per-glyph colour variation (subtle pressure changes)
            dv = rng.randint(-14, 14)
            color = tuple(max(0, min(255, c + dv)) for c in ink_rgb) + (255,)

            tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
            ImageDraw.Draw(tile).text((pad - x0, pad - y0), ch, font=font, fill=color)

            # per-glyph scale jitter
            if scale_var > 0:
                s = 1.0 + rng.gauss(0, scale_var)
                s = min(max(s, 0.7), 1.4)
                tile = tile.resize((max(1, int(tile_w * s)), max(1, int(tile_h * s))),
                                   Image.LANCZOS)

            # per-glyph rotation jitter
            angle = rng.gauss(0, settings["jitter_rotation"])
            if abs(angle) > 0.05:
                tile = tile.rotate(angle, expand=True, resample=Image.BICUBIC)

            # per-glyph baseline wander
            dy = rng.gauss(0, baseline_wander) if baseline_wander > 0 else 0
            cx = pen_x + x0 - pad + tile_w / 2
            cy = y_line + y0 - pad + tile_h / 2 + dy
            layer.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))

            spacing_jit = rng.gauss(0, char_space * 0.25 * settings["jitter_spacing"])
            pen_x += font.getlength(ch) + char_space + spacing_jit

    arr = np.array(layer)

    # ---- slant (shear the whole writing block around its centre)
    # Positive slant = rightward lean. In image coordinates (y down) that is a
    # negative shear coefficient: tops of glyphs shift right.
    slant = settings["slant_deg"] if settings["slant_deg"] is not None else params["slant_deg"]
    if abs(slant) > 0.1:
        shear = -math.tan(math.radians(slant))
        M = np.float32([[1, shear, -shear * page_h / 2], [0, 1, 0]])
        arr = cv2.warpAffine(arr, M, (page_w, page_h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # ---- ink grain: per-pixel alpha noise mimics ink soaking into fibres
    if settings["grain"] > 0:
        noise = np_rng.uniform(1 - settings["grain"], 1.0, size=(page_h, page_w))
        arr[..., 3] = (arr[..., 3].astype(np.float32) * noise).astype(np.uint8)

    # ---- micro-blur takes the digital edge off
    if settings["blur"] > 0:
        k = max(1, int(settings["blur"] * 2) * 2 + 1)
        arr = cv2.GaussianBlur(arr, (k, k), settings["blur"])

    # ---- opacity
    if settings["opacity"] < 1.0:
        arr[..., 3] = (arr[..., 3].astype(np.float32) * settings["opacity"]).astype(np.uint8)

    return arr


def composite(photo_bgr: np.ndarray, ink_rgba: np.ndarray) -> np.ndarray:
    """Multiply-blend the ink layer onto the photo (pen-on-paper darkening)."""
    base = photo_bgr.astype(np.float32)
    ink_bgr = cv2.cvtColor(ink_rgba, cv2.COLOR_RGBA2BGR).astype(np.float32)
    alpha = (ink_rgba[..., 3].astype(np.float32) / 255.0)[..., None]
    multiplied = base * (ink_bgr / 255.0)
    out = base * (1 - alpha) + multiplied * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def render_page(photo_bgr: np.ndarray, quad: np.ndarray | None, lines: list[str],
                font_path: str, params: dict, settings: dict) -> np.ndarray:
    """Render one page of handwriting onto one paper photo."""
    img_h, img_w = photo_bgr.shape[:2]
    canon_w, canon_h = cv_page.canonical_page_size(quad, img_w, img_h)
    _, Minv = cv_page.homographies(quad, img_w, img_h, canon_w, canon_h)

    ink = _render_ink_layer(lines, font_path, params, settings, canon_w, canon_h)
    warped = cv2.warpPerspective(ink, Minv, (img_w, img_h), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return composite(photo_bgr, warped)


def layout_metrics(params: dict, settings: dict, canon_h: int) -> dict:
    """Derived layout numbers shared by pagination and rendering."""
    glyph_h = settings["font_size_rel"] * canon_h
    return {
        "glyph_h": glyph_h,
        "line_pitch": glyph_h * params["line_spacing_ratio"] * settings["line_spacing_mult"],
        "char_space": params["char_spacing_ratio"] * glyph_h,
        "word_space": params["word_spacing_ratio"] * glyph_h,
    }
