"""Computer-vision page detection and perspective rectification.

Finds the paper quadrilateral inside a photo (the paper may fill the whole
frame or lie on a desk/background), orders its corners, and provides the
forward/inverse homographies used to rectify the page and warp rendered ink
back into the photo.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import CANONICAL_PAGE_HEIGHT

# A detected quad must cover at least this fraction of the photo to be trusted.
MIN_AREA_FRACTION = 0.18


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]      # TL: smallest x+y
    ordered[2] = pts[np.argmax(s)]      # BR: largest x+y
    ordered[1] = pts[np.argmin(diff)]   # TR: smallest x-y
    ordered[3] = pts[np.argmax(diff)]   # BL: largest x-y
    return ordered


def _largest_quad_from_mask(mask: np.ndarray) -> np.ndarray | None:
    """Find the largest 4-point contour in a binary mask."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    img_area = mask.shape[0] * mask.shape[1]
    for cnt in contours[:5]:
        area = cv2.contourArea(cnt)
        if area < img_area * MIN_AREA_FRACTION:
            continue
        peri = cv2.arcLength(cnt, True)
        # Progressively simplify the polygon until we get 4 corners.
        for eps_factor in (0.01, 0.02, 0.03, 0.05, 0.08):
            approx = cv2.approxPolyDP(cnt, eps_factor * peri, True)
            if len(approx) == 4:
                return _order_quad(approx)
        # Fallback: minimum-area rectangle of the biggest contour.
        rect = cv2.minAreaRect(contours[0])
        box = cv2.boxPoints(rect)
        if cv2.contourArea(box.astype(np.int32)) >= img_area * MIN_AREA_FRACTION:
            return _order_quad(box)
    return None


def detect_page_quad(image_bgr: np.ndarray) -> tuple[np.ndarray | None, bool]:
    """Detect the paper quad in a BGR photo.

    Returns (quad, has_background). quad is a 4x2 float array in original
    image coordinates (TL,TR,BR,BL), or None when the whole frame is the page.
    has_background tells whether the paper sits inside a larger scene.
    """
    h, w = image_bgr.shape[:2]
    scale = 1000.0 / max(h, w)
    small = cv2.resize(image_bgr, (int(w * scale), int(h * scale))) if scale < 1 else image_bgr.copy()

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 60, 60)

    quad = None

    # Strategy A: paper is usually the brightest large region → Otsu on blur.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    quad = _largest_quad_from_mask(thresh)

    # Strategy B: edge-based (handles lower-contrast desks).
    if quad is None:
        edges = cv2.Canny(blurred, 40, 120)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        quad = _largest_quad_from_mask(edges)

    if quad is None:
        return None, False

    # Rescale quad back to original image coordinates.
    if scale < 1:
        quad = quad / scale

    # If the quad covers nearly the whole frame, treat the photo as borderless.
    if cv2.contourArea(quad.astype(np.float32)) > 0.92 * (h * w):
        return None, False

    # Border-brightness check: if the ring *outside* the detected quad is
    # nearly as bright as the page interior, the "background" is actually
    # more paper (e.g. a full-frame page whose corners were darkened only by
    # lens vignette) → treat the whole frame as the page.
    full_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    quad_mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(quad_mask, quad.astype(np.int32), 255)
    ring = cv2.copyMakeBorder(
        np.ones((h - 2 * int(h * 0.03), w - 2 * int(w * 0.03)), np.uint8) * 0,
        int(h * 0.03), int(h * 0.03), int(w * 0.03), int(w * 0.03),
        cv2.BORDER_CONSTANT, value=255)
    outside = (quad_mask == 0) & (ring > 0)
    inside = quad_mask > 0
    if outside.sum() > 500 and inside.sum() > 500:
        ratio = float(full_gray[outside].mean() / max(full_gray[inside].mean(), 1e-6))
        if ratio > 0.72:
            return None, False
    return quad, True


def canonical_page_size(quad: np.ndarray | None, img_w: int, img_h: int) -> tuple[int, int]:
    """Canonical rectified page size (width, height) preserving aspect ratio."""
    if quad is None:
        aspect = img_w / img_h
    else:
        width_top = np.linalg.norm(quad[1] - quad[0])
        width_bot = np.linalg.norm(quad[2] - quad[3])
        height_left = np.linalg.norm(quad[3] - quad[0])
        height_right = np.linalg.norm(quad[2] - quad[1])
        aspect = ((width_top + width_bot) / 2) / max((height_left + height_right) / 2, 1e-6)
    height = CANONICAL_PAGE_HEIGHT
    width = int(round(height * aspect))
    return width, height


def homographies(quad: np.ndarray | None, img_w: int, img_h: int,
                 canon_w: int, canon_h: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (M, Minv): photo→canonical and canonical→photo homographies."""
    dst = np.array([[0, 0], [canon_w - 1, 0],
                    [canon_w - 1, canon_h - 1], [0, canon_h - 1]], dtype=np.float32)
    if quad is None:
        src = np.array([[0, 0], [img_w - 1, 0],
                        [img_w - 1, img_h - 1], [0, img_h - 1]], dtype=np.float32)
    else:
        src = quad.astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    Minv = cv2.getPerspectiveTransform(dst, src)
    return M, Minv
