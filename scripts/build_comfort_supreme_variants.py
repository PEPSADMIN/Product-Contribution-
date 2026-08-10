"""
build_comfort_supreme_variants.py — Phase 2 of the Comfort/Supreme size
expansion: build the clean, Peps-brand-verified (item_code, L, W, H, mrp,
sqft) list for all 210 standard-size combos, fixing the earlier bug where
a loose "contains COMFORT" search cross-matched a Cirrus-brand code.

Requires the match to be a PEPS-brand code (starts with "PEPS") and to
contain the line name — this is stricter than the Phase-1 discovery pass
and is what actually gets used to expand sku_master.py.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import xlrd
import openpyxl

MRP_PATH = r"C:\Users\ADMIN\Downloads\Product Contribution\Accounts W - 27.07.2026\MRP\1 - South MRP New 01 04 2026 dt 11-04-2026.xls"
COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "validation_exports", "Full_FG_Coverage_Validation.xlsx")

HEIGHTS = ['6', '8', '10']


def parse_grid():
    wb = xlrd.open_workbook(MRP_PATH)
    ws = wb.sheet_by_name('Comfort & Supreme')
    result = {'Comfort': [], 'Supreme': []}
    for r in range(5, ws.nrows):
        inches = ws.cell_value(r, 1)
        if not inches or 'x' not in str(inches):
            continue
        parts = str(inches).split('x')
        if len(parts) != 2:
            continue
        try:
            L, W = float(parts[0].strip()), float(parts[1].strip())
        except ValueError:
            continue
        sqft = ws.cell_value(r, 2)
        comfort_mrp = {HEIGHTS[i]: ws.cell_value(r, 3 + i) for i in range(3)}
        supreme_mrp = {HEIGHTS[i]: ws.cell_value(r, 6 + i) for i in range(3)}
        result['Comfort'].append((L, W, sqft, comfort_mrp))
        result['Supreme'].append((L, W, sqft, supreme_mrp))
    return result


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def main():
    grid = parse_grid()
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True)
    ws = wb["FG Coverage"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows); next(rows)
    all_rows = [(row[0], row[1]) for row in rows if row[1]]
    wb.close()

    results = {}  # line -> [(code, L, W, h, mrp, sqft), ...]
    for line in ('Comfort', 'Supreme'):
        found = []
        for L, W, sqft, mrp_by_h in grid[line]:
            for h in HEIGHTS:
                dim_str = f"{fmt_dim(L)}X{fmt_dim(W)}X{h.zfill(2)}"
                dim_str_alt = f"{fmt_dim(L)}X{fmt_dim(W)}X{h}"
                match = None
                for code, desc in all_rows:
                    if not code.upper().startswith('PEPS'):
                        continue
                    du = desc.upper()
                    if line.upper() not in du:
                        continue
                    if 'CIRRUS' in du or 'HYPNOS' in du:
                        continue
                    if dim_str in du or dim_str_alt in du:
                        match = code
                        break
                if match:
                    found.append((match, L, W, h, mrp_by_h[h], sqft))
                else:
                    print(f"  [MISSING] Peps {line} {fmt_dim(L)}x{fmt_dim(W)}x{h}\" — no Peps-brand ledger match")
        results[line] = found
        print(f"Peps {line}: {len(found)}/{len(grid[line])*3} verified Peps-brand matches\n")

    return results


if __name__ == "__main__":
    r = main()
    for line, items in r.items():
        print(f"=== {line} ({len(items)}) ===")
        for code, L, W, h, mrp, sqft in items[:8]:
            print(f"  {code:<28} {fmt_dim(L)}x{fmt_dim(W)}x{h}\"  MRP=Rs.{mrp:,.0f}  sqft={sqft:.2f}")
        if len(items) > 8:
            print(f"  ... and {len(items)-8} more")

    import json
    out_path = os.path.join(os.path.dirname(__file__), "comfort_supreme_variants.json")
    payload = {line: [{"code": c, "L": L, "W": W, "h": h, "mrp": mrp, "sqft": sqft}
                       for c, L, W, h, mrp, sqft in items]
               for line, items in r.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved {out_path}")
