"""
build_south_lines_variants.py — Phase 1 for the 10 remaining Peps lines in
the South MRP workbook (Comfort & Supreme already done separately). Same
method that gave 105/105 for Comfort/Supreme: parse each sheet's standard-
size grid (MM/INCHES/Sq.Ft + one MRP column per sub-line-and-height), then
cross-match each (L, W, height) combo against the ledger validation export
by an exact-dimension match on a real, ledger-verified item code — never a
loose keyword search (that's what produced false Cirrus/mini-sample/
wooden-base matches earlier in this project).

Each line's sub-lines (e.g. Sanibel's Plush Memory / Pillow Top / Euro Top)
use a stable family code PREFIX with a variable trailing colour code
(GR/PR/BG/BL/...) — discovered by inspecting real ledger descriptions
(see conversation), not guessed. FAMILY_PREFIXES below is that mapping.

Only South MRP sheets are read; some sheets (SPK CT, Organica, Zenimo,
Crystal, Grand Palais, Vivah, Double Decker) duplicate a second "Rest of
India" block further right in the same sheet — COLUMN CUTOFF logic below
stops before that second "STANDARD SIZES" header to avoid pulling in ROI
prices under the South line.
"""
import json
import os
import re
import sys

import xlrd
import openpyxl

MRP_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "Accounts W - 27.07.2026", "MRP", "1 - South MRP New 01 04 2026 dt 11-04-2026.xls",
)
COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "validation_exports", "Full_FG_Coverage_Validation.xlsx")
OUT_PATH = os.path.join(os.path.dirname(__file__), "south_lines_variants.json")

# sheet name -> { MRP-grid group label (as it appears in row 2) -> list of
# acceptable family code prefixes (colour suffix + dimensions follow) }
FAMILY_PREFIXES = {
    "Sanibel": {
        "Sanibel Plush Memory Foam": ["RTBNSNPLMFNL"],
        "Sanibel Plush Memory Foam Pillow Top": ["RTBNSNPLMFPT"],
        "Sanibel Plush Memory Foam Euro Top": ["RTBNSNPLMFET"],
    },
    "Ardene": {
        "Ardene Plush Memory Foam": ["RTPKARPLMFNL"],
        "Ardene Plush Memory Foam Pillow Top": ["RTPKARPLMFPT"],
        "Ardene Plush Memory Foam Euro Top": ["RTPKARPLMFET"],
    },
    "SPK CT": {
        "Springkoil Crown Top": ["SKBNCT"],
    },
    "Organica": {
        "Organica": ["PEPSPKORGBW"],
    },
    "Zenimo": {
        "Zenimo Normal": ["PEPSZENPKNL"],
        "Zenimo Pillow Top": ["PEPSZENPKPT"],
    },
    "Crystal": {
        "Crystal": ["RTGPCSBG", "RTGPCSPW"],
    },
    "Grand Palais": {
        "Grand Palais": ["RTUPGPBW", "RTUPGPGR"],
    },
    "Vivah": {
        "Vivah": ["RTVHETPT"],
    },
    "Double Decker": {
        "Double Decker": ["RTPKDD"],
    },
    "Italiano": {
        "Italiano Serenita": ["PEPSITSTPKNL"],
        "Italiano Enchanto": ["PEPSITETPKNL"],
        "Italiano Enchanto ET": ["PEPSITETPKET"],
        "Italiano Icona Italia CT": ["PEPSITICOPKCT"],
        "Italiano Magnifico Italia FT": ["PEPSITMGPKFT"],
    },
}


def parse_sheet(wb, sheet_name):
    """Returns list of (group_label, L, W, sqft, height, mrp) for the South
    (left-hand) block of the given sheet only."""
    sh = wb.sheet_by_name(sheet_name)
    group_row = [sh.cell_value(2, c) for c in range(sh.ncols)]
    height_row = [sh.cell_value(3, c) for c in range(sh.ncols)]

    # Column cutoff: stop before a second "STANDARD SIZES" (Rest of India
    # duplicate block), if present.
    cutoff = sh.ncols
    for c in range(3, sh.ncols):
        if str(group_row[c]).strip() == "STANDARD SIZES":
            cutoff = c
            break

    # Forward-fill merged group-label cells within [3, cutoff).
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

    # Row cutoff: some sheets (Sanibel, Ardene, Italiano) stack a second
    # "Rest of India" grid vertically below the South one instead of
    # beside it — stop before that row or every South size gets matched
    # twice, once with the wrong (ROI) MRP silently overwriting nothing
    # but producing a duplicate entry.
    row_cutoff = sh.nrows
    for r in range(4, sh.nrows):
        v0 = str(sh.cell_value(r, 0)).strip()
        if "Rest of India" in v0 or "Special Shape" in v0:
            row_cutoff = r
            break

    out = []
    dim_re = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*$", re.I)
    for r in range(4, row_cutoff):
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
    """code-prefix -> {(L, W, H): item_code} using exact-integer-or-decimal
    dimension match parsed straight from the real FG item code."""
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True, data_only=True)
    ws = wb["FG Coverage"]
    dim_re = re.compile(r"^([A-Z0-9\-\.]*?)(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)(?:-\S+)?$", re.I)
    index = {}  # prefix -> list of (L, W, H, code)
    for row in ws.iter_rows(min_row=4, values_only=True):
        code = row[0]
        if not code:
            continue
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

    # Flatten ledger index into: exact prefix -> {(L,W,H): code}
    exact = {}
    for prefix, items in ledger_index.items():
        d = {}
        for L, W, H, code in items:
            d.setdefault((L, W, H), code)
        exact[prefix] = d

    results = {}
    for sheet_name, groups_cfg in FAMILY_PREFIXES.items():
        grid = parse_sheet(wb, sheet_name)
        matched, total = [], 0
        misses = []
        for group_label, L, W, sqft, height, mrp in grid:
            prefixes = groups_cfg.get(group_label)
            if not prefixes:
                continue  # a group on the sheet we didn't configure (skip, don't guess)
            total += 1
            found_code = None
            # search all indexed prefixes that start with one of our target prefixes
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
