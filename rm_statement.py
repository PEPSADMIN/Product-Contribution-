"""
rm_statement.py — parses the monthly RM Statement (a Ramco "Stock Statement
Report" export for the CBERM raw-material warehouse) into a per-item rate,
and picks up whatever the user has most recently dropped into the
"RM Statement" folder — no fixed filename, just "the newest file there".

Per-item rate resolution (exactly the fallback chain the user specified):
    1. Closing Stock Rate
    2. Stock Out Rate
    3. Stock In Rate
    4. Opening Stock Rate
    5. (caller's responsibility) Item Master Standard Cost, via item_master.py

A rate tier is "available" only if the cell holds a real positive number —
blank cells (Ramco leaves the rate blank when the corresponding qty is 0,
e.g. closing rate is blank whenever closing stock is fully depleted) don't
count, so this correctly falls through to the next tier instead of treating
an empty cell as a zero-cost material.

Supports both the classic .xls export (via xlrd) and .xlsx, in case a
future month's export comes in the newer format.
"""
from __future__ import annotations
import os
import re
from datetime import datetime

FOLDER = r"C:\Users\ADMIN\Downloads\Product Contribution\RM Statement"

# Column names as they appear in the real export's header row, in fallback
# priority order — matched by exact text, not position, since a future
# month's export could reorder/insert columns.
RATE_COLUMNS_IN_PRIORITY = [
    ("Closing Stock Rate", "closing_stock"),
    ("Stock Out Rate", "stock_out"),
    ("Stock In Rate", "stock_in"),
    ("Opening Stock Rate", "opening_stock"),
]


def latest_statement_path() -> str | None:
    """The most-recently-modified spreadsheet in the RM Statement folder,
    or None if it's empty — the user just drops one file in there each
    month, no naming convention required."""
    if not os.path.isdir(FOLDER):
        return None
    candidates = []
    for name in os.listdir(FOLDER):
        if name.startswith("~$"):  # Excel's own lock file for an open workbook
            continue
        if name.lower().endswith((".xls", ".xlsx")):
            path = os.path.join(FOLDER, name)
            candidates.append((os.path.getmtime(path), path))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _rows_xls(path: str):
    import xlrd
    wb = xlrd.open_workbook(path)
    ws = wb.sheet_by_index(0)
    return [ws.row_values(r) for r in range(ws.nrows)]


def _rows_xlsx(path: str):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_links=False)
    ws = wb.worksheets[0]
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _load_rows(path: str) -> list[list]:
    if path.lower().endswith(".xlsx"):
        return _rows_xlsx(path)
    return _rows_xls(path)


def _to_float(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if f > 0 else None


def _find_header_row(rows: list[list]) -> int | None:
    for i, row in enumerate(rows):
        cells = {str(c).strip() for c in row if c is not None}
        if "Item Code" in cells and "Closing Stock Rate" in cells:
            return i
    return None


def _find_month(rows: list[list]) -> str | None:
    """Reads the report's own 'Date From' cell (e.g. '2026-07-01 00:00:00.0')
    and returns 'YYYY-MM', so a refresh run stores this under the real
    reporting period rather than today's date."""
    for row in rows:
        for i, cell in enumerate(row):
            if str(cell).strip() == "Date From" and i + 1 < len(row):
                val = row[i + 1]
                s = str(val).strip()
                m = re.match(r"(\d{4})-(\d{2})", s)
                if m:
                    return f"{m.group(1)}-{m.group(2)}"
    return None


def parse(path: str | None = None) -> dict:
    """
    Returns {
        'path': str, 'month': 'YYYY-MM' | None,
        'rates': {item_code: {'rate': float, 'source': 'closing_stock'|..., 'desc': str}},
    }
    Raises FileNotFoundError if no statement file is given/found.
    """
    path = path or latest_statement_path()
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"No RM Statement file found in {FOLDER}")

    rows = _load_rows(path)
    header_i = _find_header_row(rows)
    if header_i is None:
        raise ValueError(f"Could not find the header row (Item Code / Closing Stock Rate) in {path}")

    header = [str(c).strip() if c is not None else "" for c in rows[header_i]]
    col = {name: header.index(name) for name in header if name}
    if "Item Code" not in col or "Item Desc" not in col:
        raise ValueError(f"Expected 'Item Code' and 'Item Desc' columns, got: {header}")

    rate_cols = [(col[name], source) for name, source in RATE_COLUMNS_IN_PRIORITY if name in col]
    if not rate_cols:
        raise ValueError(f"None of the expected rate columns were found in {path}: {header}")

    rates: dict[str, dict] = {}
    for row in rows[header_i + 1:]:
        if col["Item Code"] >= len(row):
            continue
        code = str(row[col["Item Code"]] or "").strip()
        if not code:
            continue
        desc = str(row[col["Item Desc"]]).strip() if col["Item Desc"] < len(row) else ""
        for c_idx, source in rate_cols:
            if c_idx >= len(row):
                continue
            rate = _to_float(row[c_idx])
            if rate is not None:
                rates[code] = {"rate": round(rate, 4), "source": source, "desc": desc}
                break  # fallback chain stops at the first available tier

    return {"path": path, "month": _find_month(rows), "rates": rates}
