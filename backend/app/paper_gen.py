"""Synthetic paper-photo generator.

Produces realistic paper images for the built-in gallery:

- plain / ruled / graph paper
- borderless (page fills the frame) or lying on a desk background
- perspective tilt, drop shadows, lighting gradients, stains, sensor noise

These exist so the app works out of the box and the CV pipeline has varied
test material; users normally upload their own photos too.
"""
from __future__ import annotations

import cv2
import numpy as np


def _noise(rng: np.random.Generator, shape, sigma: float) -> np.ndarray:
    return rng.normal(0, sigma, shape).astype(np.float32)


def _paper_texture(rng: np.random.Generator, w: int, h: int,
                   base_bgr: tuple[int, int, int]) -> np.ndarray:
    """Paper surface: base colour + fibre noise + soft lighting gradient."""
    img = np.full((h, w, 3), base_bgr, dtype=np.float32)
    # fibre noise (blurred speckle)
    fibres = _noise(rng, (h, w), 6)
    fibres = cv2.GaussianBlur(fibres, (0, 0), 1.2)
    img += fibres[..., None]
    # lighting gradient
    gx = np.linspace(-6, 8, w, dtype=np.float32)[None, :]
    gy = np.linspace(4, -7, h, dtype=np.float32)[:, None]
    img += (gx + gy)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _add_ruled_lines(img: np.ndarray, spacing: int,
                     color=(180, 170, 200), margin_top: int | None = None) -> None:
    h, w = img.shape[:2]
    y = margin_top if margin_top is not None else spacing
    while y < h - spacing // 2:
        cv2.line(img, (int(w * 0.04), y), (int(w * 0.96), y), color, 2, cv2.LINE_AA)
        y += spacing


def _add_graph(img: np.ndarray, spacing: int, color=(190, 200, 215)) -> None:
    h, w = img.shape[:2]
    for x in range(0, w, spacing):
        cv2.line(img, (x, 0), (x, h), color, 1, cv2.LINE_AA)
    for y in range(0, h, spacing):
        cv2.line(img, (0, y), (w, y), color, 1, cv2.LINE_AA)


def _add_stain(rng: np.random.Generator, img: np.ndarray) -> None:
    """Coffee-ring style stain."""
    h, w = img.shape[:2]
    cx, cy = int(rng.uniform(0.55, 0.85) * w), int(rng.uniform(0.15, 0.5) * h)
    r = int(rng.uniform(0.05, 0.10) * w)
    overlay = img.copy()
    cv2.circle(overlay, (cx, cy), r, (120, 150, 190), 10, cv2.LINE_AA)
    cv2.circle(overlay, (cx, cy), r - 14, (150, 175, 205), -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.35, img, 0.65, 0, img)


def _wood_desk(rng: np.random.Generator, w: int, h: int,
               dark: bool) -> np.ndarray:
    base = (35, 45, 70) if dark else (90, 130, 175)
    img = np.full((h, w, 3), base, dtype=np.float32)
    # wood grain: stretched noise
    grain = _noise(rng, (h, w // 8 + 1), 22)
    grain = cv2.resize(grain, (w, h), interpolation=cv2.INTER_CUBIC)
    grain = cv2.GaussianBlur(grain, (0, 0), 3)
    img += grain[..., None]
    img += _noise(rng, (h, w, 1), 4)
    return np.clip(img, 0, 255).astype(np.uint8)


def _place_on_background(rng: np.random.Generator, paper: np.ndarray,
                         bg: np.ndarray) -> np.ndarray:
    """Perspective-place the paper onto a background with a drop shadow."""
    bh, bw = bg.shape[:2]
    ph, pw = paper.shape[:2]
    scale = min(bw * 0.78 / pw, bh * 0.78 / ph)
    pw2, ph2 = int(pw * scale), int(ph * scale)
    paper = cv2.resize(paper, (pw2, ph2))

    cx, cy = bw / 2 + rng.uniform(-0.04, 0.04) * bw, bh / 2 + rng.uniform(-0.04, 0.04) * bh
    src = np.float32([[0, 0], [pw2, 0], [pw2, ph2], [0, ph2]])
    jitter = lambda: rng.uniform(-0.06, 0.06)  # noqa: E731
    dst = np.float32([
        [cx - pw2 / 2 + jitter() * bw, cy - ph2 / 2 + jitter() * bh],
        [cx + pw2 / 2 + jitter() * bw, cy - ph2 / 2 + jitter() * bh],
        [cx + pw2 / 2 + jitter() * bw, cy + ph2 / 2 + jitter() * bh],
        [cx - pw2 / 2 + jitter() * bw, cy + ph2 / 2 + jitter() * bh],
    ])
    M = cv2.getPerspectiveTransform(src, dst)

    # shadow: warp a dark silhouette, blur, darken bg
    silhouette = np.full((ph2, pw2), 255, np.uint8)
    shadow = cv2.warpPerspective(silhouette, M, (bw, bh))
    shadow = cv2.GaussianBlur(shadow, (0, 0), 18)
    bg = bg.astype(np.float32)
    bg -= (shadow[..., None].astype(np.float32) * 0.45)
    bg = np.clip(bg, 0, 255).astype(np.uint8)

    warped = cv2.warpPerspective(paper, M, (bw, bh))
    mask = cv2.warpPerspective(silhouette, M, (bw, bh)) > 0
    out = bg.copy()
    out[mask] = warped[mask]
    return out


def _finish_photo(rng: np.random.Generator, img: np.ndarray) -> np.ndarray:
    """Vignette + sensor noise + slight softness → looks like a phone photo."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)
    vignette = 1 - np.clip(dist - 0.35, 0, None) * 0.55
    img = (img.astype(np.float32) * vignette[..., None]).astype(np.uint8)
    img = img + _noise(rng, img.shape, 2.5).astype(np.uint8)
    return cv2.GaussianBlur(img, (0, 0), 0.6)


def generate_gallery() -> list[tuple[str, np.ndarray, bool]]:
    """Return [(name, image_bgr, has_background), ...] built-in papers."""
    rng = np.random.default_rng(20260921)
    gallery: list[tuple[str, np.ndarray, bool]] = []
    W, H = 1240, 1754  # A-series aspect

    # 1 — borderless plain
    p = _paper_texture(rng, W, H, (248, 248, 245))
    gallery.append(("Plain white (full frame)", _finish_photo(rng, p), False))

    # 2 — borderless ruled
    p = _paper_texture(rng, W, H, (250, 249, 246))
    _add_ruled_lines(p, spacing=88, margin_top=140)
    gallery.append(("Ruled (full frame)", _finish_photo(rng, p), False))

    # 3 — borderless graph
    p = _paper_texture(rng, W, H, (249, 250, 250))
    _add_graph(p, spacing=64)
    gallery.append(("Graph (full frame)", _finish_photo(rng, p), False))

    # 4 — plain on light wood desk
    p = _paper_texture(rng, W, H, (247, 247, 243))
    bg = _wood_desk(rng, 1800, 1400, dark=False)
    gallery.append(("Plain on light desk", _finish_photo(rng, _place_on_background(rng, p, bg)), True))

    # 5 — ruled on dark desk
    p = _paper_texture(rng, W, H, (248, 248, 244))
    _add_ruled_lines(p, spacing=88, margin_top=140)
    bg = _wood_desk(rng, 1800, 1400, dark=True)
    gallery.append(("Ruled on dark desk", _finish_photo(rng, _place_on_background(rng, p, bg)), True))

    # 6 — stained plain on dark desk
    p = _paper_texture(rng, W, H, (246, 245, 240))
    _add_stain(rng, p)
    bg = _wood_desk(rng, 1800, 1400, dark=True)
    gallery.append(("Coffee-stained on desk", _finish_photo(rng, _place_on_background(rng, p, bg)), True))

    # 7 — yellow legal pad, full frame
    p = _paper_texture(rng, W, H, (190, 220, 240))  # BGR → warm yellow
    _add_ruled_lines(p, spacing=80, color=(170, 160, 210), margin_top=120)
    gallery.append(("Legal pad (full frame)", _finish_photo(rng, p), False))

    return gallery
