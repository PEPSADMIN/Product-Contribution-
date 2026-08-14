"""
overrides_store.py — persists Commercial Rates % edits and MRP edits, which
until now only lived in the browser (reset on every reload). Same schema
style as bom_store.py's bom_override table: one row per key holding the
user's current value, layered on top of the JSON/Python baseline by the
caller (server.py's /api/config and /api/skus).

commercial_override is keyed by the same flat COMM keys the frontend's own
COMM_PATH already uses (e.g. 'peps_dealer', 'cirrus_scheme') — this module
doesn't need to know the nested FINANCE/COMMERCIAL structure those keys map
to, the frontend already owns that mapping and sends flat key/value pairs.

mrp_override is keyed by product name (sku_master.py has no id column,
and ~30% of SKUs have no item_code — product name is the identifier the
frontend already uses as a fallback match key, see applyServerSkus()).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as the other stores

_SCHEMA = """
CREATE TABLE IF NOT EXISTS commercial_override (
    key         TEXT PRIMARY KEY,
    value       REAL NOT NULL,
    updated_at  TEXT NOT NULL,
    updated_by  TEXT
);
CREATE TABLE IF NOT EXISTS mrp_override (
    product     TEXT PRIMARY KEY,
    mrp         REAL NOT NULL,
    updated_at  TEXT NOT NULL,
    updated_by  TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_commercial_overrides() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM commercial_override").fetchall()
        return {k: v for k, v in rows}


def set_commercial_override(key: str, value: float, username: str | None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO commercial_override (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (key, value, _now(), username)
        )


def clear_commercial_override(key: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM commercial_override WHERE key = ?", (key,))


def get_mrp_overrides() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT product, mrp FROM mrp_override").fetchall()
        return {p: m for p, m in rows}


def set_mrp_override(product: str, mrp: float, username: str | None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO mrp_override (product, mrp, updated_at, updated_by) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(product) DO UPDATE SET mrp=excluded.mrp, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (product, mrp, _now(), username)
        )


def clear_mrp_override(product: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM mrp_override WHERE product = ?", (product,))
