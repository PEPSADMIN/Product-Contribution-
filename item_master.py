"""
item_master.py — search the full Ramco Item Master (201,688 rows / 57MB CSV)
for the "Add line" picker on the Material Costing tab.

Loading the whole CSV into an in-memory SQLite table once (at server
startup) and querying it with an indexed LIKE is the only sane approach
here — re-scanning a 57MB CSV on every keystroke would be far too slow for
a live search box, and 201,688 rows is trivial for SQLite to hold and index
in memory.
"""
from __future__ import annotations
import csv
import sqlite3
import threading

CSV_PATH = r"C:\Users\ADMIN\Downloads\Product Contribution\Item Master\Item Master.csv"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _build_index() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("""
        CREATE TABLE items (
            code TEXT, desc TEXT, uom TEXT, rate REAL,
            item_type TEXT, status TEXT
        )
    """)
    rows = []
    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            code = (row.get("Item Code") or "").strip()
            if not code:
                continue
            desc = (row.get("Item Variant Desc.") or "").strip() or (row.get("Short Description") or "").strip()
            uom = (row.get("Mfg UOM") or "").strip() or (row.get("Stock UOM") or "").strip()
            try:
                rate = round(float(row.get("Standard Cost") or 0), 4)
            except ValueError:
                rate = 0.0
            rows.append((code, desc, uom, rate,
                         (row.get("Item Type") or "").strip(),
                         (row.get("Item Status") or "").strip()))
    conn.executemany("INSERT INTO items VALUES (?,?,?,?,?,?)", rows)
    # LIKE on an indexed column still requires a scan for leading-wildcard
    # patterns, but 200K rows is fast enough in-memory either way; the
    # index mainly helps the exact/prefix-heavy searches users actually type.
    conn.execute("CREATE INDEX idx_code ON items(code)")
    conn.execute("CREATE INDEX idx_type_status ON items(item_type, status)")
    conn.commit()
    return conn


def get_index() -> sqlite3.Connection:
    """Lazily build the in-memory index on first use, then reuse it."""
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                _conn = _build_index()
    return _conn


def search_items(query: str, limit: int = 60, item_types: list[str] | None = None) -> list[dict]:
    """
    Partial, case-insensitive match against Item Code OR Description, ACTIVE
    items only. item_types restricts to specific Item Type values (e.g.
    ['RAWMATERIAL']) when given — the Material Costing "Add line" picker
    only wants raw materials, but this stays general-purpose.
    """
    q = (query or "").strip()
    if len(q) < 2:
        return []
    conn = get_index()
    like = f"%{q}%"
    sql = "SELECT code, desc, uom, rate FROM items WHERE status = 'ACTIVE' AND (code LIKE ? OR desc LIKE ?)"
    params: list = [like, like]
    if item_types:
        placeholders = ",".join("?" * len(item_types))
        sql += f" AND item_type IN ({placeholders})"
        params.extend(item_types)
    sql += " ORDER BY code LIMIT ?"
    params.append(limit)
    cur = conn.execute(sql, params)
    return [{"code": r[0], "desc": r[1], "uom": r[2], "rate": r[3]} for r in cur.fetchall()]
