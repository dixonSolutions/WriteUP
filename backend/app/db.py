"""SQLite persistence layer.

Plain sqlite3 with a tiny helper — no ORM, keeping dependencies light and
queries explicit. All rows are returned as dicts. JSON columns are stored as
TEXT and (de)serialised at the boundary.
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,          -- file inside data/papers/
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    quad TEXT,                       -- JSON [[x,y]x4] in original image px, or NULL
    has_background INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS styles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'font' | 'sample'
    font_file TEXT NOT NULL,         -- file inside data/fonts/
    sample_image TEXT,               -- file inside data/samples/ (if source='sample')
    params TEXT NOT NULL,            -- JSON learned/default style parameters
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS renders (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    style_id TEXT,
    settings TEXT NOT NULL,          -- JSON render settings
    pages TEXT NOT NULL,             -- JSON [{paper_id, output_file}]
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- papers
def add_paper(name: str, filename: str, width: int, height: int,
              quad: list | None, has_background: bool) -> dict:
    row = {
        "id": _new_id(), "name": name, "filename": filename,
        "width": width, "height": height,
        "quad": json.dumps(quad) if quad else None,
        "has_background": int(has_background),
        "created_at": time.time(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO papers (id,name,filename,width,height,quad,has_background,created_at)"
            " VALUES (:id,:name,:filename,:width,:height,:quad,:has_background,:created_at)", row)
    return get_paper(row["id"])


def get_paper(paper_id: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    return _paper_dict(r) if r else None


def list_papers() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM papers ORDER BY created_at DESC").fetchall()
    return [_paper_dict(r) for r in rows]


def update_paper_quad(paper_id: str, quad: list | None) -> None:
    with _connect() as conn:
        conn.execute("UPDATE papers SET quad=? WHERE id=?",
                     (json.dumps(quad) if quad else None, paper_id))


def delete_paper(paper_id: str) -> dict | None:
    paper = get_paper(paper_id)
    if paper:
        with _connect() as conn:
            conn.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    return paper


def _paper_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["quad"] = json.loads(d["quad"]) if d["quad"] else None
    d["has_background"] = bool(d["has_background"])
    return d


# ---------------------------------------------------------------- styles
def add_style(name: str, source: str, font_file: str,
              params: dict, sample_image: str | None = None) -> dict:
    row = {
        "id": _new_id(), "name": name, "source": source, "font_file": font_file,
        "sample_image": sample_image, "params": json.dumps(params),
        "created_at": time.time(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO styles (id,name,source,font_file,sample_image,params,created_at)"
            " VALUES (:id,:name,:source,:font_file,:sample_image,:params,:created_at)", row)
    return get_style(row["id"])


def get_style(style_id: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM styles WHERE id=?", (style_id,)).fetchone()
    return _style_dict(r) if r else None


def list_styles() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM styles ORDER BY created_at DESC").fetchall()
    return [_style_dict(r) for r in rows]


def delete_style(style_id: str) -> dict | None:
    style = get_style(style_id)
    if style:
        with _connect() as conn:
            conn.execute("DELETE FROM styles WHERE id=?", (style_id,))
    return style


def _style_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["params"] = json.loads(d["params"])
    return d


# ---------------------------------------------------------------- renders
def add_render(text: str, style_id: str | None, settings: dict, pages: list[dict]) -> dict:
    row = {
        "id": _new_id(), "text": text, "style_id": style_id,
        "settings": json.dumps(settings), "pages": json.dumps(pages),
        "created_at": time.time(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO renders (id,text,style_id,settings,pages,created_at)"
            " VALUES (:id,:text,:style_id,:settings,:pages,:created_at)", row)
    return get_render(row["id"])


def get_render(render_id: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM renders WHERE id=?", (render_id,)).fetchone()
    return _render_dict(r) if r else None


def list_renders(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM renders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_render_dict(r) for r in rows]


def _render_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["settings"] = json.loads(d["settings"])
    d["pages"] = json.loads(d["pages"])
    return d


def delete_render(render_id: str) -> dict | None:
    render = get_render(render_id)
    if render:
        with _connect() as conn:
            conn.execute("DELETE FROM renders WHERE id=?", (render_id,))
        for p in render["pages"]:
            f = p.get("output_file")
            if f:
                (Path(__file__).resolve().parent.parent.parent
                 / "data" / "outputs" / f).unlink(missing_ok=True)
    return render
