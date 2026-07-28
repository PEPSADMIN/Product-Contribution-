"""
costing_store.py — persist monthly RM-cost snapshots.

Without this, every run recomputes (or hardcodes) RM cost from whatever
source file happens to be on disk, and there is no way to see "what was
July's costing" once that month's source ledger is archived or overwritten.
This gives each month's parsed RM cost a permanent, queryable record.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rm_cost_snapshot (
    item_code   TEXT NOT NULL,
    product     TEXT NOT NULL,
    month       TEXT NOT NULL,   -- 'YYYY-MM'
    rm_cost     REAL NOT NULL,
    line_count  INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (item_code, month)
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def save(item_code: str, product: str, month: str, rm_cost: float,
         line_count: int, source_file: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO rm_cost_snapshot "
            "(item_code, product, month, rm_cost, line_count, source_file, computed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(item_code, month) DO UPDATE SET "
            "rm_cost=excluded.rm_cost, line_count=excluded.line_count, "
            "source_file=excluded.source_file, computed_at=excluded.computed_at",
            (item_code, product, month, rm_cost, line_count, source_file,
             datetime.now(timezone.utc).isoformat())
        )


def latest(item_code: str):
    """Return (month, rm_cost, source_file) for the most recent snapshot, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT month, rm_cost, source_file FROM rm_cost_snapshot "
            "WHERE item_code = ? ORDER BY month DESC LIMIT 1",
            (item_code,)
        ).fetchone()
        return row


def history(item_code: str):
    with _conn() as conn:
        return conn.execute(
            "SELECT month, rm_cost, line_count, source_file FROM rm_cost_snapshot "
            "WHERE item_code = ? ORDER BY month",
            (item_code,)
        ).fetchall()


def all_latest() -> dict:
    """Return {item_code: (month, rm_cost, source_file)} for every tracked item, most recent month each."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT item_code, month, rm_cost, source_file FROM rm_cost_snapshot r "
            "WHERE month = (SELECT MAX(month) FROM rm_cost_snapshot WHERE item_code = r.item_code)"
        ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}
