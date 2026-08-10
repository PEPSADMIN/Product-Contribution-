"""
build_cirrus_coir_variants.py — same exact-dimension cross-match method,
applied to the Cirrus Coir Mattress MRP workbook.

This workbook has much denser, easily-confused sub-line naming than the
other MRP files: "Nimbo" vs "Nimbo Plus", "Bond Plus Regular" vs "Bond
Plus MF Patented" vs "Bond Plus MF Patented PT" vs "Bond Plus Latex
Patented", "Eco Plus ET" vs the un-tracked plain "Eco Plush"/"Eco Plush
PT". A truncated prefix like "CIRNIMB" would incorrectly also match
"CIRNIMBPL..." (Nimbo Plus) via startswith. So FAMILY_PREFIXES here are
EXACT, fully-specific prefixes enumerated by hand from the real ledger
descriptions (see conversation) — never a shared truncated root. There is
also a separate "HCF..." code family reusing the same product names as a
different channel/brand variant (like the Hypnos collision in the Cirrus
Foam file) — excluded by only indexing "CIR"-prefixed codes at all.

The old standalone "Kozybreeze" sheet here (WEF 15.07.2024) is skipped —
Kozybreeze is already covered via the Cirrus Foam workbook's "Kozybreeze3"
sheet (WEF 01.04.2026).
"""
import json
import os
import re

import xlrd
import openpyxl

MRP_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "Accounts W - 27.07.2026", "MRP", "3 -  Cirrus Coir Mattress MRP 01 04 2026 dt 11-04-2026.xls",
)
COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "validation_exports", "Full_FG_Coverage_Validation.xlsx")
OUT_PATH = os.path.join(os.path.dirname(__file__), "cirrus_coir_variants.json")

FAMILY_PREFIXES = {
    "Cirrus Coir 1": {
        "New Eco": ["CIRNECOBL", "CIRNECOMR"],
        "Cloud Plus": ["CIRCOCLPLBBL", "CIRCOCLPLBG", "CIRCOCLPLBLMR", "CIRCOCLPLLGR",
                       "CIRCOCLPLPDBG", "CIRCOCLPLPRBG"],
        "Nimbo": ["CIRNIMBBL", "CIRNIMBBW", "CIRNIMBGN", "CIRNIMBGR", "CIRNIMBMR",
                  "CIRNIMBWH", "CIRNIMBWHBL", "CIRNIMBWHMR", "CIRNIMBWMR"],
        "Nimbo Plus": ["CIRNIMBPL", "CIRNIMBPLBL", "CIRNIMBPLMR", "CIRNIMBPLWH",
                       "CIRNIMBPLWHBL", "CIRNIMBPLWHMR"],
    },
    "Cirrus Coir 2": {
        "Eco Plus ET": ["CIRECOPLETBL", "CIRECOPLETMR", "CIRECOPLETPK"],
        "Bond Plus Regular": ["CIRBOPLDG", "CIRBOPLDGR", "CIRBOPLGN", "CIRBOPLGRN",
                               "CIRBOPLGPR", "CIRBOPLGR", "CIRBOPLLGR", "CIRBOPLLMR",
                               "CIRBOPLPK", "CIRBOPLSMR", "CIRBOPLWGR"],
        "Bond Plus MF Patented": ["CIRBOPLMFPDBL", "CIRBOPLMFPDGN"],
        "Bond Plus MF Patented PT": ["CIRBOPLMFPTPDOR"],
        "Bond Plus Latex Patented": ["CIRBOPLLTPD", "CIRBOPLLTPDWHBL"],
    },
    "Cirrus Coir 3": {
        "Comfort Plush": ["CIRCFPLBL", "CIRCFPLIV", "CIRCFPLMR", "CIRCFPLPK", "CIRCFPLWH"],
        "Luxury Memory": ["CIRLUXMFBG", "CIRLUXMFGRN", "CIRLUXMFMR", "CIRLUXMFNB", "CIRLUXMFPG"],
        "Luxury Plush ET": ["CIRLUXPLETCR", "CIRLUXPLETGN"],
    },
}

# Sanity guard: for group X, no matched code's prefix should ALSO be a
# prefix configured under this "must not be" list — catches accidental
# startswith leakage between near-collisions (e.g. Nimbo vs Nimbo Plus).
MUST_NOT_CONTAIN = {
    ("Cirrus Coir 1", "Nimbo"): ["PL"],  # plain Nimbo must not be Nimbo Plus
    ("Cirrus Coir 2", "Bond Plus Regular"): ["MF", "LT", "PD", "PT"],
    ("Cirrus Coir 2", "Bond Plus MF Patented"): ["PT", "RG"],
    ("Cirrus Coir 2", "Bond Plus MF Patented PT"): ["RG"],
    ("Cirrus Coir 2", "Bond Plus Latex Patented"): ["RG"],
    ("Cirrus Coir 3", "Luxury Memory"): ["ET"],
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
        code = row[0]
        if not code:
            continue
        code_s = str(code).upper()
        if not code_s.startswith("CIR"):
            continue  # excludes the HCF-channel duplicate naming entirely
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
        matched, total, misses, guard_fail = [], 0, [], []
        for group_label, L, W, sqft, height, mrp in grid:
            prefixes = groups_cfg.get(group_label)
            if not prefixes:
                continue
            total += 1
            found_code = None
            for full_prefix, dmap in exact.items():
                if full_prefix not in prefixes:
                    continue
                code = dmap.get((L, W, height))
                if code:
                    found_code = code
                    found_prefix = full_prefix
                    break
            if found_code:
                bad_tokens = MUST_NOT_CONTAIN.get((sheet_name, group_label), [])
                if any(tok in found_prefix for tok in bad_tokens):
                    guard_fail.append(found_code)
                    continue
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
        if guard_fail:
            print(f"  SANITY GUARD TRIPPED, excluded: {guard_fail}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
