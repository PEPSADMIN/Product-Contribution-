"""
bom_store.py — persist itemized BOMs: the ledger-extracted baseline, and
any user edits layered on top.

Two tables, same schema style as costing_store.py:
  bom_snapshot — the real, ledger-extracted BOM for (item_code, month).
                 Rebuilt by refresh_bom_data.py; never edited by users.
  bom_override — the user's current edited BOM for an item_code, if they've
                 changed anything (added/deleted/modified a line). Stored
                 as the *whole* edited tree, not a per-line diff — simpler
                 and avoids stable-line-id/merge complexity for Phase 1.
                 GET /api/bom/<item_code> returns this when present,
                 falling back to the latest bom_snapshot otherwise.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as costing_store.py

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bom_snapshot (
    item_code   TEXT NOT NULL,
    month       TEXT NOT NULL,   -- 'YYYY-MM'
    json_data   TEXT NOT NULL,   -- extract_boms()'s per-item_code list, as JSON
    line_count  INTEGER NOT NULL,
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (item_code, month)
);
CREATE TABLE IF NOT EXISTS bom_override (
    item_code   TEXT NOT NULL PRIMARY KEY,
    json_data   TEXT NOT NULL,   -- the user's full current edited BOM tree, as JSON
    updated_at  TEXT NOT NULL
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def save_snapshot(item_code: str, month: str, lines: list) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO bom_snapshot (item_code, month, json_data, line_count, extracted_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(item_code, month) DO UPDATE SET "
            "json_data=excluded.json_data, line_count=excluded.line_count, "
            "extracted_at=excluded.extracted_at",
            (item_code, month, json.dumps(lines), len(lines),
             datetime.now(timezone.utc).isoformat())
        )


def latest_snapshot(item_code: str):
    """Return (month, lines) for the most recent extracted BOM, or None if never extracted."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT month, json_data FROM bom_snapshot "
            "WHERE item_code = ? ORDER BY month DESC LIMIT 1",
            (item_code,)
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else None


def get_snapshot(item_code: str, month: str):
    """Return the lines for one specific (item_code, month) snapshot, or None
    if that month was never extracted for this item — used by the History
    tab's drill-down, which needs a past month's real BOM, not just the latest."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT json_data FROM bom_snapshot WHERE item_code = ? AND month = ?",
            (item_code, month)
        ).fetchone()
        return json.loads(row[0]) if row else None


def save_override(item_code: str, lines: list) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO bom_override (item_code, json_data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(item_code) DO UPDATE SET "
            "json_data=excluded.json_data, updated_at=excluded.updated_at",
            (item_code, json.dumps(lines), datetime.now(timezone.utc).isoformat())
        )


def get_override(item_code: str):
    """Return the user's edited BOM lines for this item_code, or None if never edited."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT json_data FROM bom_override WHERE item_code = ?",
            (item_code,)
        ).fetchone()
        return json.loads(row[0]) if row else None


def clear_override(item_code: str) -> None:
    """Discard the user's edits, reverting to the ledger-extracted baseline."""
    with _conn() as conn:
        conn.execute("DELETE FROM bom_override WHERE item_code = ?", (item_code,))


def months_matched(item_code: str) -> list:
    """Every month this item_code was found in the FG ledger (sorted), for
    coverage reporting — see export_sku_list.py."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT month FROM bom_snapshot WHERE item_code = ? ORDER BY month",
            (item_code,)
        ).fetchall()
        return [r[0] for r in rows]


def all_referenced_sfg_codes() -> set:
    """Every SFG code (wh == 'SFG') that appears anywhere across every
    saved bom_snapshot — i.e. every sub-assembly this tool's extracted
    BOMs actually reference, for SFG coverage reporting (see
    export_full_fg_coverage.py). Reads bom_snapshot only, not
    bom_override, since overrides are per-user edits, not ledger fact."""
    import json
    codes = set()
    with _conn() as conn:
        for (json_data,) in conn.execute("SELECT json_data FROM bom_snapshot"):
            for line in json.loads(json_data):
                if line.get('wh') == 'SFG' and line.get('code'):
                    codes.add(line['code'])
    return codes


def get_bom(item_code: str):
    """
    The one function the API route needs: user's edited version if one
    exists, else the latest ledger snapshot, else None (never extracted —
    caller should show the "not yet extracted" placeholder).
    Returns (lines, source) where source is 'override' or 'ledger:<month>' or None.
    """
    override = get_override(item_code)
    if override is not None:
        return override, 'override'
    snap = latest_snapshot(item_code)
    if snap is not None:
        month, lines = snap
        return lines, f'ledger:{month}'
    return None, None
