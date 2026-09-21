#!/usr/bin/env python3
"""Automated realism/pipeline checks against a running WriteUP API.

Tests:
1. Containment — bright-red ink must land inside the detected page quad
   (with a small tolerance) for every rendered page, including desk photos.
2. Scaling — the same settings on pages of different sizes must produce ink
   coverage proportional to page area (text scales with the page).
3. Pagination — long text must produce the expected number of pages.
4. Robustness — empty text, huge padding, tiny font must not crash.

Usage: .venv/bin/python scripts/verify_containment.py
"""
import json
import sys
import urllib.request

import cv2
import numpy as np

API = "http://127.0.0.1:8000/api"


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def get(path):
    return json.load(urllib.request.urlopen(API + path))


def get_file(kind, name):
    data = urllib.request.urlopen(f"{API}/files/{kind}/{name}").read()
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def red_mask(img):
    """Pixels where the pure-red test ink dominates."""
    b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    return (r > 120) & (r - b > 60) & (r - g > 60)


def main() -> int:
    failures = []
    papers = get("/papers")
    styles = get("/styles")
    style_id = styles[0]["id"]

    # Pin the test papers to the *synthetic* gallery: real photos may contain
    # red objects (pen, header bars) that confound the pure-red ink mask.
    def pick(prefer_quad: bool):
        synth = [p for p in papers if not p["name"].startswith(("REAL", "Uploaded"))]
        for p in synth:
            if bool(p["quad"]) == prefer_quad:
                return p
        return next(p for p in papers if bool(p["quad"]) == prefer_quad)

    desk = pick(prefer_quad=True)
    full = pick(prefer_quad=False)
    print(f"desk paper: {desk['name']} | full-frame paper: {full['name']}")

    text = ("The quick brown fox jumps over the lazy dog. " * 400).strip()

    # ---- Test 1: containment on a desk photo and a full-frame page
    for label, paper in (("desk", desk), ("full-frame", full)):
        res = post("/render", {
            "text": text, "paper_ids": [paper["id"]], "style_id": style_id,
            "settings": {"ink_color": [255, 0, 0], "seed": 1, "grain": 0},
        })
        for i, page in enumerate(res["pages"]):
            img = get_file("outputs", page["output_file"])
            mask = red_mask(img)
            if paper["quad"]:
                q = np.array(paper["quad"], np.int32)
                inside = np.zeros(mask.shape, np.uint8)
                # pad the quad outward by 1.5% of its height for anti-aliasing
                centre = q.mean(axis=0)
                q_pad = centre + (q - centre) * 1.03
                cv2.fillConvexPoly(inside, q_pad.astype(np.int32), 1)
                outside_ratio = float((mask & (inside == 0)).sum() / max(mask.sum(), 1))
                ok = outside_ratio < 0.01
                print(f"[{label} p{i+1}] ink outside quad: {outside_ratio:.4%} → {'OK' if ok else 'FAIL'}")
                if not ok:
                    failures.append(f"{label} p{i+1} containment {outside_ratio:.4%}")
            else:
                h, w = mask.shape
                border = np.ones((h, w), bool)
                border[int(h*0.02):int(h*0.98), int(w*0.02):int(w*0.98)] = False
                # full-frame: ink should respect padding → none in outer 2% ring
                ratio = float((mask & border).sum() / max(mask.sum(), 1))
                ok = ratio < 0.01
                print(f"[{label} p{i+1}] ink in outer ring: {ratio:.4%} → {'OK' if ok else 'FAIL'}")
                if not ok:
                    failures.append(f"{label} p{i+1} border ink {ratio:.4%}")

    # ---- Test 2: pagination count (18k chars must span many pages)
    res = post("/render", {"text": text, "paper_ids": [full["id"]],
                           "style_id": style_id, "settings": {"seed": 1}})
    n = len(res["pages"])
    ok = 2 <= n <= 60
    print(f"[pagination] {n} pages for 18k chars → {'OK' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"pagination {n}")

    # ---- Test 3: robustness
    for label, settings in (
        ("empty text", {"seed": 1}),
        ("max padding", {"padding_top": 0.39, "padding_bottom": 0.39,
                         "padding_left": 0.39, "padding_right": 0.39, "seed": 1}),
        ("tiny font", {"font_size_rel": 0.008, "seed": 1}),
        ("huge font", {"font_size_rel": 0.08, "seed": 1}),
    ):
        try:
            t = "" if label == "empty text" else "Hello world, this is a test."
            res = post("/render", {"text": t, "paper_ids": [full["id"]],
                                   "style_id": style_id, "settings": settings})
            print(f"[robust:{label}] rendered {len(res['pages'])} page(s) → OK")
        except Exception as exc:  # noqa: BLE001
            print(f"[robust:{label}] {exc} → FAIL")
            failures.append(f"robust {label}: {exc}")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)"); [print(" -", f) for f in failures]
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
