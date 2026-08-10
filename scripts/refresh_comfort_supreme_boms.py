"""
refresh_comfort_supreme_boms.py — extracts real itemized BOM + RM cost
for the 210 Comfort/Supreme size variants (scripts/comfort_supreme_
variants.json, built by build_comfort_supreme_variants.py) across all 4
months, same two-pass streaming approach as refresh_bom_data.py, and
saves into the same bom_store/costing_store databases the tool already
reads from — this is additive, the existing 51 tracked SKUs are
untouched.

Also saves an RM-cost snapshot into costing_store (not just bom_store),
since that's what /api/skus actually serves to the frontend.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bom_extractor import extract_boms
import bom_store
import costing_store

RM_ROOT = r"C:\Users\ADMIN\Downloads\Product Contribution\Accounts W - 27.07.2026\RM"
VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "comfort_supreme_variants.json")

MONTHS = [
    ("2026-02", r"1 - Feb'26\2 - FG Feb'26.xlsx", r"1 - Feb'26\1 - SFG Feb'26.xlsx"),
    ("2026-03", r"2 - Mar'26\1 - FG Mar'26 dt 04-04-2026.xlsx", r"2 - Mar'26\2 - SFG Mar'26 dt 03-04-2026.xlsx"),
    ("2026-04", r"3 - April'26\2 - FG April'26 dt 22-05-2026.xlsx", r"3 - April'26\1 - SFG April'26 dt 22-05-2026.xlsx"),
    ("2026-05", r"4 - May'26\2 - FG MAY'26.xlsx", r"4 - May'26\1 - SFG MAY'26.xlsx"),
]


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    item_codes = sorted({v["code"] for line in variants.values() for v in line})
    code_to_product = {}
    for line_name, items in variants.items():
        for v in items:
            L = v["L"]; W = v["W"]
            L_s = str(int(L)) if L == int(L) else f"{L:.2f}"
            W_s = str(int(W)) if W == int(W) else f"{W:.2f}"
            code_to_product[v["code"]] = f"Peps {line_name} {L_s}x{W_s} {v['h']}\""

    print(f"Extracting BOMs for {len(item_codes)} Comfort/Supreme size-variant codes across {len(MONTHS)} months...")
    matched_by_code = {}

    for month, fg_rel, sfg_rel in MONTHS:
        fg_path = os.path.join(RM_ROOT, fg_rel)
        sfg_path = os.path.join(RM_ROOT, sfg_rel)
        if not os.path.exists(fg_path) or not os.path.exists(sfg_path):
            print(f"\n[{month}] skip — FG or SFG file not found")
            continue

        print(f"\n[{month}] parsing {os.path.basename(fg_path)} + {os.path.basename(sfg_path)}...")
        t0 = time.time()
        results = extract_boms(item_codes, fg_path, sfg_path, progress=True)
        elapsed = time.time() - t0
        print(f"[{month}] parsed in {elapsed:.1f}s — {len(results)}/{len(item_codes)} codes matched")

        for code, lines in results.items():
            bom_store.save_snapshot(code, month, lines)
            total = sum(c["cost"] for c in lines)
            costing_store.save(code, code_to_product.get(code, code), month, total, len(lines), f"FG {month}")
            matched_by_code.setdefault(code, set()).add(month)

    never_matched = sorted(set(item_codes) - set(matched_by_code))
    print(f"\n{'='*70}\nFINAL COVERAGE — {len(matched_by_code)}/{len(item_codes)} size-variant codes matched in at least one month")
    if never_matched:
        print(f"\nNever found in ANY of the {len(MONTHS)} months ({len(never_matched)}):")
        for code in never_matched:
            print(f"  {code} ({code_to_product.get(code, '?')})")


if __name__ == "__main__":
    main()
