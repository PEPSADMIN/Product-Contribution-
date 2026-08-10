"""
match_comfort_supreme_sizes.py — proper Phase 1 for "Peps Comfort" and
"Peps Supreme" only: parse the MRP sheet's EXACT standard-size grid
(5 lengths x 7 widths x 3 heights = 105 combos each), then check each
one against the real ledger data for an exact-dimension match — not a
loose "contains this keyword and is big enough" guess like the first
pass, which mostly caught one-off custom order sizes instead of real
catalog SKUs.
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
    """Returns {'Comfort': [(L,W,sqft,{h:mrp}), ...], 'Supreme': [...]}."""
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
    """72.0 -> '72', 77.5 -> '77.50' (matches Ramco's own formatting seen in codes)."""
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def main():
    grid = parse_grid()
    print(f"Parsed {len(grid['Comfort'])} standard sizes each for Comfort and Supreme "
          f"({len(HEIGHTS)} heights = {len(grid['Comfort'])*3} total combos each)\n")

    print(f"Loading {COVERAGE_PATH} ...")
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True)
    ws = wb["FG Coverage"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows); next(rows)
    all_rows = [(row[0], row[1]) for row in rows if row[1]]
    wb.close()
    print(f"  {len(all_rows):,} codes loaded\n")

    for line in ('Comfort', 'Supreme'):
        print(f"=== Peps {line} ===")
        found, missing = [], []
        for L, W, sqft, mrp_by_h in grid[line]:
            for h in HEIGHTS:
                dim_str = f"{fmt_dim(L)}X{fmt_dim(W)}X{h.zfill(2)}"
                dim_str_alt = f"{fmt_dim(L)}X{fmt_dim(W)}X{h}"  # non-zero-padded height
                match = None
                for code, desc in all_rows:
                    du = desc.upper()
                    if line.upper() not in du:
                        continue
                    if dim_str in du or dim_str_alt in du:
                        match = (code, desc)
                        break
                if match:
                    found.append((L, W, h, mrp_by_h[h], match))
                else:
                    missing.append((L, W, h, mrp_by_h[h]))
        print(f"  Found: {len(found)}/{len(found)+len(missing)} real ledger matches")
        for L, W, h, mrp, (code, desc) in found[:15]:
            print(f"    {fmt_dim(L)}x{fmt_dim(W)}x{h}\" MRP=Rs.{mrp:,.0f} -> {code} ({desc})")
        if len(found) > 15:
            print(f"    ... and {len(found)-15} more")
        print()


if __name__ == "__main__":
    main()
