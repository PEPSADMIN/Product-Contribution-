"""
build_cirrus_foam_variants.py — same method as build_south_lines_variants.py
(exact-dimension cross-match against the ledger, no loose keyword search),
applied to the Cirrus Foam Mattress MRP workbook.

Row layout differs slightly from the South MRP workbook: group-label row
is row 1 (not 2), height labels row 2, mm labels row 3, data starts row 4
— no separate "region" row. All sheets used here split South/Rest-of-India
HORIZONTALLY (like SPK CT etc in the South workbook), not vertically like
Sanibel/Ardene/Italiano, so only a column cutoff is needed.

Two lines are deliberately EXCLUDED, not matched:
  - "Kozybreeze" (old sheet, WEF 15.07.2024) — superseded by "Kozybreeze3"
    (WEF 01.04.2026), which is used instead.
  - "Vistabond" — already excluded elsewhere in this project (see
    sku_master.py's "Vista bond ... INTENTIONALLY NOT ADDED" comment): its
    Direct Labour/Admin OHS/Marketing OHS are each exactly half of the
    expected formula value, a real structural anomaly needing Works
    Manager confirmation, not a data-matching problem. Left alone here too.

Ledger descriptions for this family include a same-named "Hypnos" brand
(e.g. "Hypnos Inspree Soft Top Beige") mixed in with the real Cirrus-brand
codes sharing the same MM prefix — same false-match risk as the Cirrus/
Comfort collision caught earlier in this project. Any candidate whose
description contains "HYPNOS" is excluded from the ledger index entirely.
"""
import json
import os
import re

import xlrd
import openpyxl

MRP_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "Accounts W - 27.07.2026", "MRP", "2 - Cirrus Foam Mattress MRP 01 04 2026 dt 11-04-2026 - Copy.xls",
)
COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "validation_exports", "Full_FG_Coverage_Validation.xlsx")
OUT_PATH = os.path.join(os.path.dirname(__file__), "cirrus_foam_variants.json")

FAMILY_PREFIXES = {
    "Kozybreeze3": {
        "Kozybreeze": ["HYPKBRZFMDB", "HYPKBRZFMMR"],
    },
    "Inspree PU": {
        "Inspree PU Normal": ["HYPINSFMMR"],
        "Inspree PU ET": ["HYPINSFMETMR"],
    },
    "Inspree MF": {
        "Inspree Memory Foam Normal": ["HYPINSFMMFBL", "HYPINSFMMFGR"],
        "Inspree Memory Foam ET": ["HYPINSFMMFETBL", "HYPINSFMMFETGR"],
    },
    "Inspree Latex": {
        "Inspree Latex Normal": ["HYPINSFMLTGRN", "HYPINSFMLTPNK"],
        "Inspree Latex ET": ["HYPINSFMLTETGRN", "HYPINSFMLTETPNK"],
    },
    "Memorio": {
        "Memorio": ["HYPMEMFMOR", "HYPMEMFMVL"],
    },
    "Vista Foam": {
        "Vista Foam": ["HYPVISFM"],
    },
    "Vista Soft": {
        "Vista Soft": ["HYPVISSFT"],
    },
    "Caprina Gel": {
        "Caprina Gel Memory + Lax": ["HYPCAPMFLAX"],
    },
    "Caprina HR": {
        "Caprina HR Latex": ["HYPCAPHRLTX"],
    },
    "Cirrus Latex": {
        "Pin Core Latex": ["HYPPINLTX"],
    },
}


def parse_sheet(wb, sheet_name):
    sh = wb.sheet_by_name(sheet_name)
    group_row = [sh.cell_value(1, c) for c in range(sh.ncols)]
    height_row = [sh.cell_value(2, c) for c in range(sh.ncols)]

    cutoff = sh.ncols
    for c in range(3, sh.ncols):
        if str(group_row[c]).strip() == "STANDARD SIZES":
            cutoff = c
            break

    groups = [None] * cutoff
    last = None
    for c in range(3, cutoff):
        v = str(group_row[c]).strip()
        if v:
            last = v
        groups[c] = last

    heights = [None] * cutoff
    for c in range(3, cutoff):
        hv = str(height_row[c]).strip()
        m = re.search(r"(\d+)", hv)
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
            if groups[c] is None or heights[c] is None:
                continue
            val = sh.cell_value(r, c)
            if not isinstance(val, (int, float)) or val <= 0:
                continue
            out.append((groups[c], L, W, sqft, heights[c], round(float(val))))
    return out


def build_ledger_index():
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True, data_only=True)
    ws = wb["FG Coverage"]
    dim_re = re.compile(r"^([A-Z0-9\-\.]*?)(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)(?:-\S+)?$", re.I)
    index = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        code, desc = row[0], row[1]
        if not code:
            continue
        if desc and "HYPNOS" in str(desc).upper():
            continue  # different brand, same-shaped codes — exclude
        code_s = str(code).upper()
        m = dim_re.match(code_s)
        if not m:
            continue
        prefix = m.group(1)
        L, W, H = float(m.group(2)), float(m.group(3)), float(m.group(4))
        index.setdefault(prefix, []).append((L, W, H, code_s))
    return index


def fnum(v):
    return v if v != int(v) else int(v)


def main():
    wb = xlrd.open_workbook(MRP_PATH)
    ledger_index = build_ledger_index()
    exact = {}
    for prefix, items in ledger_index.items():
        d = {}
        for L, W, H, code in items:
            d.setdefault((L, W, H), code)
        exact[prefix] = d

    results = {}
    for sheet_name, groups_cfg in FAMILY_PREFIXES.items():
        grid = parse_sheet(wb, sheet_name)
        matched, total, misses = [], 0, []
        for group_label, L, W, sqft, height, mrp in grid:
            prefixes = groups_cfg.get(group_label)
            if not prefixes:
                continue
            total += 1
            found_code = None
            for full_prefix, dmap in exact.items():
                if not any(full_prefix.startswith(pfx) for pfx in prefixes):
                    continue
                code = dmap.get((L, W, height))
                if code:
                    found_code = code
                    break
            if found_code:
                matched.append({
                    "line": sheet_name, "group": group_label,
                    "L": fnum(L), "W": fnum(W), "h": height,
                    "sqft": round(float(sqft), 2), "mrp": mrp, "code": found_code,
                })
            else:
                misses.append((group_label, fnum(L), fnum(W), height))
        results[sheet_name] = matched
        print(f"{sheet_name}: {len(matched)}/{total} matched")
        if misses:
            print(f"  unmatched ({len(misses)}): {misses[:10]}{' ...' if len(misses) > 10 else ''}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
