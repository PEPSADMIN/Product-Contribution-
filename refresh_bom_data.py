"""
refresh_bom_data.py — batch-extract itemized BOMs for every SKU with a real
item_code, persist into bom_store.py.

Same reasoning as refresh_rm_costs.py: the FG ledger is 126MB+ and takes
minutes to stream, so this must be a batch job run periodically (whenever a
new "Accounts W..." month folder lands), not something done live per
request. extract_boms() already processes every requested item_code in one
pass, so this costs the same whether run for 1 SKU or all of them.

Runs across EVERY month folder under RM_ROOT (Feb/Mar/April/May'26, as of
this run), not just the latest — a product missing from May's FG ledger
(discontinued, renamed, or simply not produced that month) may still show
up in an earlier month, and bom_store's (item_code, month) primary key
already supports keeping every month's snapshot side by side. get_bom()
picks the latest month with a match, so checking more months can only
close coverage gaps, never make a match worse.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from sku_master import SKUS
from bom_extractor import extract_boms
import bom_store

RM_ROOT = r"C:\Users\ADMIN\Downloads\Product Contribution\Accounts W - 27.07.2026\RM"

# (month, FG path, SFG path) — oldest to newest, exact filenames as they
# actually appear on disk (naming isn't consistent month to month).
MONTHS = [
    ("2026-02", r"1 - Feb'26\2 - FG Feb'26.xlsx", r"1 - Feb'26\1 - SFG Feb'26.xlsx"),
    ("2026-03", r"2 - Mar'26\1 - FG Mar'26 dt 04-04-2026.xlsx", r"2 - Mar'26\2 - SFG Mar'26 dt 03-04-2026.xlsx"),
    ("2026-04", r"3 - April'26\2 - FG April'26 dt 22-05-2026.xlsx", r"3 - April'26\1 - SFG April'26 dt 22-05-2026.xlsx"),
    ("2026-05", r"4 - May'26\2 - FG MAY'26.xlsx", r"4 - May'26\1 - SFG MAY'26.xlsx"),
]

ITEM_CODES = sorted({s["item_code"] for s in SKUS if s.get("item_code")})


def main():
    print(f"Extracting BOMs for {len(ITEM_CODES)} item-coded SKUs across {len(MONTHS)} months...")
    matched_by_code = {}  # item_code -> set of months it was found in

    for month, fg_rel, sfg_rel in MONTHS:
        fg_path = os.path.join(RM_ROOT, fg_rel)
        sfg_path = os.path.join(RM_ROOT, sfg_rel)
        if not os.path.exists(fg_path) or not os.path.exists(sfg_path):
            print(f"\n[{month}] skip — FG or SFG file not found")
            continue

        print(f"\n[{month}] parsing {os.path.basename(fg_path)} + {os.path.basename(sfg_path)}...")
        t0 = time.time()
        results = extract_boms(ITEM_CODES, fg_path, sfg_path, progress=True)
        elapsed = time.time() - t0
        print(f"[{month}] parsed in {elapsed:.1f}s — {len(results)}/{len(ITEM_CODES)} item codes matched")

        for code, lines in results.items():
            bom_store.save_snapshot(code, month, lines)
            matched_by_code.setdefault(code, set()).add(month)

    never_matched = sorted(set(ITEM_CODES) - set(matched_by_code))
    print(f"\n{'='*70}\nFINAL COVERAGE — {len(matched_by_code)}/{len(ITEM_CODES)} item-coded SKUs matched in at least one month")
    if never_matched:
        print(f"\nNever found in ANY of the {len(MONTHS)} months checked ({len(never_matched)}):")
        for code in never_matched:
            print(f"  {code}")

    code_to_product = {s["item_code"]: s["product"] for s in SKUS if s.get("item_code")}
    print("\nCoverage by product (months matched, latest snapshot's line count + total cost):")
    for code in sorted(matched_by_code, key=lambda c: code_to_product.get(c, c)):
        months_found = sorted(matched_by_code[code])
        latest_month, lines = bom_store.latest_snapshot(code)
        total = sum(c["cost"] for c in lines)
        print(f"  {code_to_product.get(code, code):<28s} months={','.join(months_found):<24s} "
              f"latest={latest_month} {len(lines):>2d} lines  Rs.{total:>10,.2f}")


if __name__ == "__main__":
    main()
