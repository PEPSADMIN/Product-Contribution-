"""
rd_store.py — persist R&D drafts: sandbox BOM experiments that never touch
the real, live sku_master.py catalog. Same schema style as bom_store.py/
costing_store.py.

A draft is either:
  - "existing": forked from a real, live product (base_item_code is a real
    tracked SKU) — the real product's own BOM/cost is never modified, only
    this draft's own copy.
  - "new": a from-scratch product idea, identified by a user-typed name and
    dummy item code (never a real Ramco code), still seeded from a copied
    real BOM (base_item_code) since nothing starts from a blank page.

Each draft can have multiple variants (for side-by-side fabric/material
comparison) — every draft always has at least one variant ("Original").

Nothing here ever writes to sku_master.py. "Approved" is just a status
label the user sets by hand once their admin signs off outside this tool
(their own BOMAT Tool workflow) — it does not trigger anything automatic.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as the other stores

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rd_draft (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    mode            TEXT NOT NULL,   -- 'existing' | 'new'
    dummy_item_code TEXT,            -- only set for mode='new'
    base_item_code  TEXT NOT NULL,   -- the real SKU whose BOM/financials seeded this draft
    status          TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'pending_review' | 'approved'
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rd_variant (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id    INTEGER NOT NULL REFERENCES rd_draft(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    json_data   TEXT NOT NULL,   -- the variant's full BOM line tree, as JSON
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.execute("PRAGMA foreign_keys = ON")
    # Migrate existing DBs: rd_draft predates the login system, so older
    # rows have no submitter — added once login/CMS/notifications came in.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(rd_draft)").fetchall()}
    if "created_by" not in cols:
        conn.execute("ALTER TABLE rd_draft ADD COLUMN created_by TEXT")
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_draft(name: str, mode: str, base_item_code: str, base_bom_lines: list,
                  dummy_item_code: str | None = None, created_by: str | None = None) -> int:
    """Creates a draft plus its first variant ("Original"), seeded with a
    copy of the base product's real BOM. Returns the new draft's id."""
    now = _now()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO rd_draft (name, mode, dummy_item_code, base_item_code, status, created_at, updated_at, created_by) "
            "VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)",
            (name, mode, dummy_item_code, base_item_code, now, now, created_by)
        )
        draft_id = cur.lastrowid
        conn.execute(
            "INSERT INTO rd_variant (draft_id, name, json_data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (draft_id, "Original", json.dumps(base_bom_lines), now, now)
        )
        return draft_id


def list_drafts() -> list:
    """Every draft with a variant count, newest-updated first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT d.id, d.name, d.mode, d.dummy_item_code, d.base_item_code, d.status, "
            "d.created_at, d.updated_at, COUNT(v.id) as variant_count, d.created_by "
            "FROM rd_draft d LEFT JOIN rd_variant v ON v.draft_id = d.id "
            "GROUP BY d.id ORDER BY d.updated_at DESC"
        ).fetchall()
        cols = ["id", "name", "mode", "dummy_item_code", "base_item_code", "status",
                "created_at", "updated_at", "variant_count", "created_by"]
        return [dict(zip(cols, r)) for r in rows]


def get_draft(draft_id: int):
    """Full draft detail plus all its variants (each with parsed BOM lines)."""
    with _conn() as conn:
        drow = conn.execute(
            "SELECT id, name, mode, dummy_item_code, base_item_code, status, created_at, updated_at, created_by "
            "FROM rd_draft WHERE id = ?", (draft_id,)
        ).fetchone()
        if not drow:
            return None
        dcols = ["id", "name", "mode", "dummy_item_code", "base_item_code", "status", "created_at", "updated_at", "created_by"]
        draft = dict(zip(dcols, drow))
        vrows = conn.execute(
            "SELECT id, name, json_data, created_at, updated_at FROM rd_variant "
            "WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()
        draft["variants"] = [
            {"id": v[0], "name": v[1], "lines": json.loads(v[2]), "created_at": v[3], "updated_at": v[4]}
            for v in vrows
        ]
        return draft


def update_draft(draft_id: int, name: str | None = None, status: str | None = None) -> None:
    with _conn() as conn:
        if name is not None:
            conn.execute("UPDATE rd_draft SET name=?, updated_at=? WHERE id=?", (name, _now(), draft_id))
        if status is not None:
            conn.execute("UPDATE rd_draft SET status=?, updated_at=? WHERE id=?", (status, _now(), draft_id))


def delete_draft(draft_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM rd_draft WHERE id = ?", (draft_id,))


def add_variant(draft_id: int, name: str, lines: list) -> int:
    now = _now()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO rd_variant (draft_id, name, json_data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (draft_id, name, json.dumps(lines), now, now)
        )
        conn.execute("UPDATE rd_draft SET updated_at=? WHERE id=?", (now, draft_id))
        return cur.lastrowid


def save_variant(variant_id: int, lines: list, name: str | None = None) -> None:
    with _conn() as conn:
        if name is not None:
            conn.execute("UPDATE rd_variant SET json_data=?, name=?, updated_at=? WHERE id=?",
                         (json.dumps(lines), name, _now(), variant_id))
        else:
            conn.execute("UPDATE rd_variant SET json_data=?, updated_at=? WHERE id=?",
                         (json.dumps(lines), _now(), variant_id))
        row = conn.execute("SELECT draft_id FROM rd_variant WHERE id=?", (variant_id,)).fetchone()
        if row:
            conn.execute("UPDATE rd_draft SET updated_at=? WHERE id=?", (_now(), row[0]))


def delete_variant(variant_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM rd_variant WHERE id = ?", (variant_id,))
