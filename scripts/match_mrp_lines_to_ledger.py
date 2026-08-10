"""
match_mrp_lines_to_ledger.py — Phase 1 of expanding sku_master.py's size
coverage: for every product line named in the MRP files, search the
already-scanned FG ledger data (Full_FG_Coverage_Validation.xlsx, 136,640
codes with real descriptions) for codes that actually belong to that
line, and parse each one's real Length x Width x Height.

This is discovery only — no RM cost extraction yet, no writes to
sku_master.py. It answers "which sizes does this product line actually
get manufactured at" (per the real ledger) before committing to the much
bigger job of extracting itemized BOM/RM cost for every newly-found code.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import openpyxl

COVERAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "validation_exports", "Full_FG_Coverage_Validation.xlsx")

# (brand, sheet/line name in the MRP file, search terms to look for in the
# ledger description — some lines need more than one term, e.g. the MRP
# sheet "Comfort & Supreme" is really two separate lines)
LINES = [
    ("Peps", "Comfort", ["comfort"]),
    ("Peps", "Supreme", ["supreme"]),
    ("Peps", "SPK CT", ["springkoil", "spring koil", "spk ct", "crown top"]),
    ("Peps", "Sanibel", ["sanibel"]),
    ("Peps", "Ardene", ["ardene"]),
    ("Peps", "SPG", ["spine guard", "spg"]),
    ("Peps", "Organica", ["organica"]),
    ("Peps", "Zenimo", ["zenimo"]),
    ("Peps", "Crystal", ["crystal"]),
    ("Peps", "Grand Palais", ["grand palais", "grandpalais"]),
    ("Peps", "Vivah", ["vivah"]),
    ("Peps", "Double Decker", ["double decker"]),
    ("Peps", "Italiano", ["italiano"]),
    ("Cirrus Foam", "Kozybreeze", ["kozybreeze", "kozy breeze"]),
    ("Cirrus Foam", "Vistabond", ["vistabond", "vista bond"]),
    ("Cirrus Foam", "Inspree PU", ["inspree"]),
    ("Cirrus Foam", "Inspree MF", ["inspree"]),
    ("Cirrus Foam", "Inspree Latex", ["inspree"]),
    ("Cirrus Foam", "Memorio", ["memorio"]),
    ("Cirrus Foam", "Vista Foam", ["vista foam"]),
    ("Cirrus Foam", "Vista Soft", ["vista soft"]),
    ("Cirrus Foam", "Caprina Gel", ["caprina"]),
    ("Cirrus Foam", "Caprina HR", ["caprina"]),
    ("Cirrus Foam", "Cirrus Latex", ["cirrus latex"]),
    ("Cirrus Coir", "Cirrus Coir", ["coir"]),
]

_DIM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)')


def main():
    print(f"Loading {COVERAGE_PATH} ...")
    wb = openpyxl.load_workbook(COVERAGE_PATH, read_only=True)
    ws = wb["FG Coverage"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows); next(rows)  # title, blank, header

    all_codes = []  # (code, desc_upper)
    for row in rows:
        code, desc = row[0], row[1]
        if desc:
            all_codes.append((code, desc.upper()))
    wb.close()
    print(f"  {len(all_codes):,} codes with descriptions loaded\n")

    # Exclude anything that's clearly not a full-size mattress: mini
    # samples / swatches, raw foam blocks (component-level, not finished
    # product), headboards, and pillows/cushions/comforters all share
    # keywords with real product lines but aren't mattress SKUs.
    EXCLUDE_TERMS = ['mini sample', 'sample', 'block', 'headboard', 'pillow',
                      'cushion', 'comforter', 'bolster', 'runner', 'topper']
    MIN_MATTRESS_DIM = 45  # inches — real mattress width/length; samples/swatches are much smaller

    print(f"{'Brand':<12} {'Line':<15} {'Real sizes found':<18} Sample codes")
    print("-" * 100)
    for brand, line, terms in LINES:
        terms_upper = [t.upper() for t in terms]
        excl_upper = [t.upper() for t in EXCLUDE_TERMS]
        sizes = {}  # (L,W,H) -> [codes]
        for code, du in all_codes:
            if not any(t in du for t in terms_upper):
                continue
            if any(t in du for t in excl_upper):
                continue
            m = _DIM_RE.search(du)
            if not m:
                continue
            try:
                l, w = float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
            if l < MIN_MATTRESS_DIM or w < MIN_MATTRESS_DIM:
                continue
            key = (m.group(1), m.group(2), m.group(3))
            sizes.setdefault(key, []).append(code)
        sample = list(sizes.items())[:5]
        sample_str = "; ".join(f"{k[0]}x{k[1]}x{k[2]}={v[0]}" for k, v in sample)
        print(f"{brand:<12} {line:<15} {len(sizes):<18} {sample_str}")


if __name__ == "__main__":
    main()
