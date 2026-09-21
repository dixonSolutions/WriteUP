#!/usr/bin/env python3
"""Generate handwriting sample images for style-learning validation.

Each sample is rendered with a known font/slant/spacing recipe, then the CV
learner measures it back — a closed-loop test that the style learner recovers
sensible parameters. Samples live in data/samples/ and are also registered as
learned styles via the API.
"""
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "data" / "fonts"
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

SAMPLE_TEXT = [
    "The quick brown fox jumps over",
    "the lazy dog near the riverbank.",
    "Every letter carries a little of",
    "the writer's hand: a lean, a loop,",
    "a pause. 0123456789!",
]

RECIPES = [
    # (name, font, slant_deg, ink_bgr)
    ("sample_caveat", "Caveat.ttf", 8.0, (45, 45, 45)),
    ("sample_kalam", "Kalam.ttf", 1.0, (110, 40, 25)),
    ("sample_labelle", "LaBelleAurore.ttf", 5.0, (90, 30, 20)),
]


def render_sample(font_file: str, slant: float, ink_bgr: tuple[int, int, int]) -> np.ndarray:
    W, H = 1400, 900
    img = np.full((H, W, 3), (252, 251, 248), np.uint8)
    rng = np.random.default_rng(5)
    img = np.clip(img.astype(np.float32) + rng.normal(0, 2.5, img.shape), 0, 255).astype(np.uint8)

    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    font = ImageFont.truetype(str(FONTS / font_file), 64)
    y = 90
    for line in SAMPLE_TEXT:
        draw.text((110, y), line, font=font, fill=(ink_bgr[2], ink_bgr[1], ink_bgr[0]))
        y += 140
    arr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    if abs(slant) > 0.1:
        shear = math.tan(math.radians(slant))
        M = np.float32([[1, shear, -shear * H / 2], [0, 1, 0]])
        arr = cv2.warpAffine(arr, M, (W, H), borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(252, 251, 248))
    return arr


def main() -> int:
    for name, font, slant, ink in RECIPES:
        if not (FONTS / font).exists():
            print(f"skip {name}: missing {font}")
            continue
        img = render_sample(font, slant, ink)
        path = OUT / f"{name}.jpg"
        cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
