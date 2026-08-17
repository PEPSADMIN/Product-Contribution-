"""
waterfall_store.py — persists a product's per-line Net Margin overrides
(the % / ₹ edits in Material Costing's waterfall table — dealer margin,
dist margin, sales deductions, overheads, etc.), keyed by item_code.
Same "whole tree, not a diff" pattern as bom_store.py's bom_override:
simpler than tracking individual field changes, and there's at most one
override row per item_code so the simplicity costs nothing.

RM cost is deliberately never part of this override — it's always
derived from the Bill of Materials (bom_store.py), pinned automatically
on every BOM save; the frontend excludes that key before saving here.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as the other stores

_SCHEMA = """
CREATE TABLE IF NOT EXISTS waterfall_override (
    item_code   TEXT NOT NULL PRIMARY KEY,
    json_data   TEXT NOT NULL,   -- the user's current {key: {kind, value}} overrides, as JSON
    updated_at  TEXT NOT NULL,
    updated_by  TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def get_override(item_code: str):
    """Return the saved overrides dict for this item_code, or None if never saved."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT json_data FROM waterfall_override WHERE item_code = ?",
            (item_code,)
        ).fetchone()
        return json.loads(row[0]) if row else None


def save_override(item_code: str, overrides: dict, username: str | None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO waterfall_override (item_code, json_data, updated_at, updated_by) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(item_code) DO UPDATE SET "
            "json_data=excluded.json_data, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (item_code, json.dumps(overrides), datetime.now(timezone.utc).isoformat(), username)
        )


def clear_override(item_code: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM waterfall_override WHERE item_code = ?", (item_code,))
