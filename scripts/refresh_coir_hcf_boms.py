"""
refresh_coir_hcf_boms.py — Blockage 2 (Cirrus Coir), continued 2026-08-08:
user provided the HCF ledger folder as a second, real production data
source. Direct scan of HCF\\MAY'26 and HCF\\JUNE'26 FG files confirmed 450
of the original 733 Cirrus Coir size/colour combos exist there under
their ORIGINAL "CIR..." item codes (not renamed) — a 5th/6th month never
checked before. Extracts real BOM/RM for those 450 codes from the HCF
ledger (same FG/SFG schema as the main Accounts ledger, just a separate
factory unit's own workbook).

Cloud Plus (0/91) and Cirrus Latex/"Pin Core Latex" (0/105, from the
Cirrus Foam batch) are NOT covered by this fix — confirmed absent from
both HCF months too, see docs/known_gaps.md.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bom_extractor import extract_boms
import bom_store
import costing_store

HCF_ROOT = r"C:\Users\ADMIN\Downloads\Product Contribution\HCF"
VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "cirrus_coir_variants.json")

MONTHS = [
    ("2026-05-hcf", r"MAY'26\3 - FG HCF May'26.xlsx", r"MAY'26\1 - SFG HCF May'26.xlsx"),
    ("2026-06-hcf", r"JUNE'26\3 - FG HCF June'26.xlsx", r"JUNE'26\1 - SFG HCF June'26.xlsx"),
]


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    item_codes = sorted({v["code"] for items in variants.values() for v in items})
    code_to_product = {}
    for line_name, items in variants.items():
        for v in items:
            code_to_product.setdefault(v["code"], f"{line_name} {v['group']} {v['L']}x{v['W']} {v['h']}\"")

    print(f"Extracting BOMs for {len(item_codes)} Cirrus Coir codes against the HCF ledger ({len(MONTHS)} months)...")
    matched_by_code = {}

    for month, fg_rel, sfg_rel in MONTHS:
        fg_path = os.path.join(HCF_ROOT, fg_rel)
        sfg_path = os.path.join(HCF_ROOT, sfg_rel)
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
            costing_store.save(code, code_to_product.get(code, code), month, total, len(lines), f"HCF FG {month}")
            matched_by_code.setdefault(code, set()).add(month)

    never_matched = sorted(set(item_codes) - set(matched_by_code))
    print(f"\n{'='*70}\nFINAL COVERAGE — {len(matched_by_code)}/{len(item_codes)} Coir codes matched in the HCF ledger")
    if never_matched:
        print(f"\nNever found in either HCF month ({len(never_matched)}):")
        for code in never_matched:
            print(f"  {code} ({code_to_product.get(code, '?')})")


if __name__ == "__main__":
    main()
