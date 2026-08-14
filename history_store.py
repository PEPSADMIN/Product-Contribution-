"""
history_store.py — a single, sequentially-numbered audit trail across every
kind of edit this tool persists (Commercial Rates, MRP, Material Costing BOM
edits, R&D drafts, CMS user management), same schema style as the other
*_store.py modules.

One flat table, not one-table-per-action-type: every entry gets the same
autoincrement id (the "History #" shown in the UI), so there's one real
sequence to scroll through instead of BOM Tool's several independently-
numbered tables. Each entry carries a full before/after JSON snapshot of
whatever changed — not a diff — so a rollback just needs to write
`before_data` back, no reconstruction logic per field.

Real, working rollback (POST /api/history/<id>/rollback in server.py) is
only wired up for the three action types where "write the old blob back"
is unambiguous and safe: commercial_rate, mrp, bom_line. rd_draft and
user_mgmt entries are still fully logged and visible here for audit, but
have no rollback handler — the same asymmetry BOM Tool itself has (it only
ever restores real data for global_replace; run/approval "rollback" there
is just a status flip). Restoring an R&D draft's edit history or reversing
someone's role/tab changes safely needs more than a blob-overwrite, so
that's left as a follow-up rather than half-built here.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as the other stores

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    username    TEXT NOT NULL,
    action      TEXT NOT NULL,   -- 'commercial_rate' | 'mrp' | 'bom_line' | 'rd_draft' | 'user_mgmt' | 'user_password_reset'
    entity      TEXT NOT NULL,   -- human label: group title / product name / item_code / draft name / username
    summary     TEXT NOT NULL,   -- one-line human-readable description of what changed
    before_data TEXT,            -- JSON, or NULL if this action had no prior state (e.g. a create)
    after_data  TEXT,            -- JSON, or NULL if this action removed the state entirely (e.g. a delete)
    status      TEXT NOT NULL DEFAULT 'active'   -- 'active' | 'rolled_back'
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def record(username: str, action: str, entity: str, summary: str,
           before: dict | None, after: dict | None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO app_history (created_at, username, action, entity, summary, before_data, after_data, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'active')",
            (_now(), username or 'unknown', action, entity, summary,
             json.dumps(before) if before is not None else None,
             json.dumps(after) if after is not None else None)
        )
        return cur.lastrowid


_COLS = ["id", "created_at", "username", "action", "entity", "summary", "before_data", "after_data", "status"]


def _row_to_dict(row) -> dict:
    d = dict(zip(_COLS, row))
    d["before_data"] = json.loads(d["before_data"]) if d["before_data"] else None
    d["after_data"] = json.loads(d["after_data"]) if d["after_data"] else None
    return d


def list_history(limit: int = 300) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at, username, action, entity, summary, before_data, after_data, status "
            "FROM app_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get(history_id: int):
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, created_at, username, action, entity, summary, before_data, after_data, status "
            "FROM app_history WHERE id = ?",
            (history_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None


def mark_rolled_back(history_id: int) -> None:
    with _conn() as conn:
        conn.execute("UPDATE app_history SET status = 'rolled_back' WHERE id = ?", (history_id,))
