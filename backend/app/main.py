"""WriteUP FastAPI application.

REST API for papers, handwriting styles, fonts and rendering, plus static
file serving for the data store. Security note: all writes/validations happen
here at the API level — the frontend is only a view.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import cv_page, db, paper_gen, renderer, style_learn
from .config import (FONTS_DIR, OUTPUTS_DIR, PAPERS_DIR, SAMPLES_DIR,
                     THUMBS_DIR)

app = FastAPI(title="WriteUP API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_MB = 25


# ------------------------------------------------------------------ models
class FontStyleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    font_file: str


class RenderRequest(BaseModel):
    text: str = Field(max_length=100_000)
    paper_ids: list[str] = Field(min_length=1)
    style_id: str
    settings: dict = Field(default_factory=dict)


# ------------------------------------------------------------------ helpers
def _read_upload(data: bytes) -> np.ndarray:
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB)")
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Could not decode image")
    return img


def _safe_name(name: str) -> str:
    keep = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(c for c in name if c in keep).strip() or "untitled"


def _save_thumb(img: np.ndarray, name: str) -> str:
    h, w = img.shape[:2]
    scale = 420 / max(h, w)
    thumb = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
    fname = f"{name}.jpg"
    cv2.imwrite(str(THUMBS_DIR / fname), thumb, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return fname


def _merged_settings(raw: dict) -> dict:
    """Merge user settings over defaults; clamp to sane ranges (API-level
    validation so the backend — not the UI — enforces safety)."""
    s = dict(renderer.DEFAULT_SETTINGS)
    for key, value in (raw or {}).items():
        if key in s and value is not None:
            s[key] = value
    s["font_size_rel"] = float(np.clip(s["font_size_rel"], 0.008, 0.08))
    s["line_spacing_mult"] = float(np.clip(s["line_spacing_mult"], 0.5, 3.0))
    for side in ("padding_top", "padding_bottom", "padding_left", "padding_right"):
        s[side] = float(np.clip(s[side], 0.0, 0.4))
    s["jitter_rotation"] = float(np.clip(s["jitter_rotation"], 0.0, 8.0))
    s["jitter_scale"] = float(np.clip(s["jitter_scale"], 0.0, 3.0))
    s["jitter_baseline"] = float(np.clip(s["jitter_baseline"], 0.0, 3.0))
    s["jitter_spacing"] = float(np.clip(s["jitter_spacing"], 0.0, 3.0))
    s["opacity"] = float(np.clip(s["opacity"], 0.2, 1.0))
    s["blur"] = float(np.clip(s["blur"], 0.0, 2.5))
    s["grain"] = float(np.clip(s["grain"], 0.0, 0.9))
    s["seed"] = int(s["seed"])
    if s["ink_color"] is not None:
        if not (isinstance(s["ink_color"], list) and len(s["ink_color"]) == 3):
            raise HTTPException(422, "ink_color must be [r,g,b]")
        s["ink_color"] = [int(np.clip(c, 0, 255)) for c in s["ink_color"]]
    if s["slant_deg"] is not None:
        s["slant_deg"] = float(np.clip(s["slant_deg"], -35, 35))
    return s


# ------------------------------------------------------------------ startup
@app.on_event("startup")
def startup() -> None:
    db.init_db()
    _seed_defaults()


def _seed_defaults() -> None:
    """First run: generate the paper gallery and a few font-based styles."""
    if not db.list_papers():
        for i, (name, img, has_bg) in enumerate(paper_gen.generate_gallery()):
            fname = f"gallery_{i}.jpg"
            cv2.imwrite(str(PAPERS_DIR / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            quad, has_background = cv_page.detect_page_quad(img)
            db.add_paper(name, fname, img.shape[1], img.shape[0],
                         quad.tolist() if quad is not None else None,
                         has_background or has_bg)
            _save_thumb(img, Path(fname).stem)
    if not db.list_styles():
        presets = [
            ("Casual print", "Kalam.ttf", {"slant_deg": 2.0}),
            ("Flowing cursive", "Caveat.ttf", {"slant_deg": 8.0,
                                               "ink_color": [40, 40, 40]}),
            ("Light sketch", "ShadowsIntoLight.ttf", {"slant_deg": -2.0,
                                                      "ink_color": [60, 60, 60]}),
            ("Neat cursive", "LaBelleAurore.ttf", {"slant_deg": 6.0}),
        ]
        for name, font, overrides in presets:
            if (FONTS_DIR / font).exists():
                params = dict(style_learn.DEFAULT_PARAMS)
                params.update(overrides)
                db.add_style(name, "font", font, params)


# ------------------------------------------------------------------ health
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": time.time()}


# ------------------------------------------------------------------ fonts
@app.get("/api/fonts")
def list_fonts() -> list[str]:
    return sorted(f.name for f in FONTS_DIR.glob("*.ttf"))


# ------------------------------------------------------------------ papers
@app.get("/api/papers")
def papers() -> list[dict]:
    return db.list_papers()


@app.post("/api/papers")
async def upload_paper(file: UploadFile = File(...), name: str = Form("")) -> dict:
    img = _read_upload(await file.read())
    pname = _safe_name(name or Path(file.filename or "paper").stem)
    fname = f"{int(time.time()*1000)}_{pname}.jpg"
    cv2.imwrite(str(PAPERS_DIR / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    quad, has_bg = cv_page.detect_page_quad(img)
    paper = db.add_paper(pname, fname, img.shape[1], img.shape[0],
                         quad.tolist() if quad is not None else None, has_bg)
    _save_thumb(img, Path(fname).stem)
    return paper


@app.post("/api/papers/{paper_id}/redetect")
def redetect_paper(paper_id: str) -> dict:
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    img = cv2.imread(str(PAPERS_DIR / paper["filename"]))
    quad, has_bg = cv_page.detect_page_quad(img)
    db.update_paper_quad(paper_id, quad.tolist() if quad is not None else None)
    return db.get_paper(paper_id)


@app.delete("/api/papers/{paper_id}")
def remove_paper(paper_id: str) -> dict:
    paper = db.delete_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    (PAPERS_DIR / paper["filename"]).unlink(missing_ok=True)
    (THUMBS_DIR / f"{Path(paper['filename']).stem}.jpg").unlink(missing_ok=True)
    return {"deleted": paper_id}


@app.get("/api/papers/{paper_id}/overlay")
def paper_overlay(paper_id: str) -> FileResponse:
    """Preview image with the detected page quad drawn on it."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    img = cv2.imread(str(PAPERS_DIR / paper["filename"]))
    if paper["quad"]:
        q = np.array(paper["quad"], np.int32)
        cv2.polylines(img, [q], True, (0, 220, 80), 6, cv2.LINE_AA)
        for pt in q:
            cv2.circle(img, tuple(pt), 14, (0, 120, 255), -1, cv2.LINE_AA)
    out = OUTPUTS_DIR / f"_overlay_{paper_id}.jpg"
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return FileResponse(out)


# ------------------------------------------------------------------ styles
@app.get("/api/styles")
def styles() -> list[dict]:
    return db.list_styles()


@app.post("/api/styles/from-font")
def style_from_font(req: FontStyleRequest) -> dict:
    if not (FONTS_DIR / req.font_file).exists():
        raise HTTPException(404, "Font not found")
    params = dict(style_learn.DEFAULT_PARAMS)
    return db.add_style(_safe_name(req.name), "font", req.font_file, params)


@app.post("/api/styles/from-sample")
async def style_from_sample(file: UploadFile = File(...), name: str = Form(""),
                            font_file: str = Form("")) -> dict:
    img = _read_upload(await file.read())
    sname = _safe_name(name or Path(file.filename or "style").stem)
    if not font_file or not (FONTS_DIR / font_file).exists():
        font_file = "Caveat.ttf"
    fname = f"{int(time.time()*1000)}_{sname}.jpg"
    cv2.imwrite(str(SAMPLES_DIR / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    params = style_learn.learn_from_image(img)
    # Store only the *extra* slant beyond the font's natural lean, so the
    # renderer reproduces the sample's visual slant instead of doubling it.
    natural = style_learn.measure_font_slant(str(FONTS_DIR / font_file))
    params["font_natural_slant"] = round(natural, 2)
    params["slant_deg"] = round(params["slant_deg"] - natural, 2)
    return db.add_style(sname, "sample", font_file, params, sample_image=fname)


@app.delete("/api/styles/{style_id}")
def remove_style(style_id: str) -> dict:
    style = db.delete_style(style_id)
    if not style:
        raise HTTPException(404, "Style not found")
    return {"deleted": style_id}


# ------------------------------------------------------------------ render
@app.post("/api/render")
def render(req: RenderRequest) -> dict:
    style = db.get_style(req.style_id)
    if not style:
        raise HTTPException(404, "Style not found")
    font_path = FONTS_DIR / style["font_file"]
    if not font_path.exists():
        raise HTTPException(404, f"Font file missing: {style['font_file']}")

    papers = []
    for pid in req.paper_ids:
        p = db.get_paper(pid)
        if not p:
            raise HTTPException(404, f"Paper not found: {pid}")
        papers.append(p)

    settings = _merged_settings(req.settings)
    params = style["params"]

    # Layout uses the most conservative writable area across all selected
    # papers, so text that fits the smallest page fits every page and line
    # breaks stay consistent.
    from .renderer import _calibrated_size, _font, _sanitize, _wrap_text
    canon_sizes = []
    for p in papers:
        img0 = cv2.imread(str(PAPERS_DIR / p["filename"]))
        q0 = np.array(p["quad"], np.float32) if p["quad"] else None
        canon_sizes.append(cv_page.canonical_page_size(q0, img0.shape[1], img0.shape[0]))
    canon_h = min(h for _, h in canon_sizes)
    m = renderer.layout_metrics(params, settings, canon_h)
    font = _font(str(font_path), _calibrated_size(str(font_path), m["glyph_h"]))
    text = _sanitize(req.text, font)
    writable_w = min(w * (1 - settings["padding_left"] - settings["padding_right"])
                     for w, _ in canon_sizes)
    writable_h = canon_h * (1 - settings["padding_top"] - settings["padding_bottom"])
    lines = _wrap_text(text, font, writable_w, m["char_space"], m["word_space"])
    lines_per_page = max(1, int(writable_h // m["line_pitch"]))
    pages_lines = renderer.paginate(lines, lines_per_page)

    # Persist a render row first so outputs are named by id.
    render_row = db.add_render(req.text, style["id"], settings, pages=[])
    out_pages = []
    for i, page_lines in enumerate(pages_lines):
        paper = papers[i % len(papers)]
        img = cv2.imread(str(PAPERS_DIR / paper["filename"]))
        quad = np.array(paper["quad"], np.float32) if paper["quad"] else None
        result = renderer.render_page(img, quad, page_lines, str(font_path),
                                      params, settings)
        fname = f"{render_row['id']}_p{i+1}.jpg"
        cv2.imwrite(str(OUTPUTS_DIR / fname), result, [cv2.IMWRITE_JPEG_QUALITY, 93])
        out_pages.append({"paper_id": paper["id"], "output_file": fname,
                          "url": f"/api/files/outputs/{fname}"})

    # Update the row with the produced pages.
    import json as _json
    from .db import _connect
    with _connect() as conn:
        conn.execute("UPDATE renders SET pages=? WHERE id=?",
                     (_json.dumps(out_pages), render_row["id"]))
    return db.get_render(render_row["id"])


@app.get("/api/renders")
def renders() -> list[dict]:
    return db.list_renders()


@app.delete("/api/renders/{render_id}")
def remove_render(render_id: str) -> dict:
    render = db.delete_render(render_id)
    if not render:
        raise HTTPException(404, "Render not found")
    return {"deleted": render_id}


# ------------------------------------------------------------------ files
@app.get("/api/files/{kind}/{filename}")
def files(kind: str, filename: str) -> FileResponse:
    roots = {"papers": PAPERS_DIR, "samples": SAMPLES_DIR,
             "outputs": OUTPUTS_DIR, "thumbs": THUMBS_DIR, "fonts": FONTS_DIR}
    if kind not in roots:
        raise HTTPException(404, "Unknown file kind")
    # Prevent path traversal — resolve and verify containment.
    path = (roots[kind] / filename).resolve()
    if roots[kind].resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


# ------------------------------------------------------------- production SPA
# When the frontend has been built (`npm run build`), serve it from the API
# port too — registered after every /api route so the API always wins.
from .config import PROJECT_ROOT  # noqa: E402

_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
