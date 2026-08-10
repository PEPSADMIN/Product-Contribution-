"""
build_spg_variants.py — Spine Guard (SPG), the line from the South MRP
workbook's "SPG" sheet that was never added in the original Blockage-1
sweep. Same exact-dimension cross-match method as the other lines.
Real code family: "SKSGSR" (Peps Spine Guard Spring), confirmed against
Contribution/1 - Peps Product Contribution dt 14-07-2026.xlsx's
SPG-Bonnell tab (item codes SKSGSR78X60X06/08).
"""
import json
import os
import re

import xlrd
import openpyxl

MRP_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "Accounts W - 27.07.2026", "MRP", "1 - South MRP New 01 04 2026 dt 11-04-2026.xls",
)
COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "validation_exports", "Full_FG_Coverage_Validation.xlsx")
OUT_PATH = os.path.join(os.path.dirname(__file__), "spg_variants.json")

FAMILY_PREFIX = "SKSGSR"


def parse_sheet(wb):
    sh = wb.sheet_by_name("SPG")
    group_row = [sh.cell_value(2, c) for c in range(sh.ncols)]
    height_row = [sh.cell_value(3, c) for c in range(sh.ncols)]
    cutoff = sh.ncols
    for c in range(3, sh.ncols):
        if str(group_row[c]).strip() == "STANDARD SIZES":
            cutoff = c
            break
    heights = [None] * cutoff
    for c in range(3, cutoff):
        m = re.search(r"(\d+)", str(height_row[c]).strip())
        heights[c] = int(m.group(1)) if m else None

    out = []
    dim_re = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*$", re.I)
    for r in range(4, sh.nrows):
        inches = str(sh.cell_value(r, 1)).strip()
        m = dim_re.match(inches)
        if not m:
            continue
        L, W = float(m.group(1)), float(m.group(2))
        sqft = sh.cell_value(r, 2)
        for c in range(3, cutoff):
            if heights[c] is None:
                continue
            val = sh.cell_value(r, c)
            if not isinstance(val, (int, float)) or val <= 0:
                continue
            out.append((L, W, sqft, heights[c], round(float(val))))
    return out


def build_ledger_index():
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True, data_only=True)
    ws = wb["FG Coverage"]
    dim_re = re.compile(r"^([A-Z0-9\-\.]*?)(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)(?:-\S+)?$", re.I)
    index = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        code = row[0]
        if not code:
            continue
        code_s = str(code).upper()
        if not code_s.startswith(FAMILY_PREFIX):
            continue
        m = dim_re.match(code_s)
        if not m:
            continue
        L, W, H = float(m.group(2)), float(m.group(3)), float(m.group(4))
        index.setdefault((L, W, H), code_s)
    return index


def fnum(v):
    return v if v != int(v) else int(v)


def main():
    wb = xlrd.open_workbook(MRP_PATH)
    grid = parse_sheet(wb)
    ledger = build_ledger_index()

    matched, misses = [], []
    for L, W, sqft, height, mrp in grid:
        code = ledger.get((L, W, height))
        if code:
            matched.append({"line": "SPG", "group": "Spine Guard", "L": fnum(L), "W": fnum(W),
                             "h": height, "sqft": round(float(sqft), 2), "mrp": mrp, "code": code})
        else:
            misses.append((fnum(L), fnum(W), height))

    print(f"SPG: {len(matched)}/{len(grid)} matched")
    if misses:
        print(f"  unmatched ({len(misses)}): {misses[:10]}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"SPG": matched}, f, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
