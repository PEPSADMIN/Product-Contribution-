"""
refresh_rm_costs.py — backfill monthly RM cost snapshots from Ramco's FG
ledger exports into costing_store, for every SKU in sku_master.py that has
a real item_code.

Run once per month (or whenever a new "Accounts W..." month folder lands).
Feb'26's FG file is ~255MB and can take several minutes to open — this is
a batch job, not something to run on every page load.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from sku_master import SKUS
from rm_ledger import sum_rm_cost
import costing_store

RM_ROOT = r"C:\Users\ADMIN\Downloads\Product Contribution\Accounts W - 27.07.2026\RM"

MONTHS = [
    ("2026-02", r"1 - Feb'26\2 - FG Feb'26.xlsx"),
    ("2026-03", r"2 - Mar'26\1 - FG Mar'26 dt 04-04-2026.xlsx"),
    ("2026-04", r"3 - April'26\2 - FG April'26 dt 22-05-2026.xlsx"),
    ("2026-05", r"4 - May'26\2 - FG MAY'26.xlsx"),
]

ITEM_CODES = {s["item_code"]: s["product"] for s in SKUS if s.get("item_code")}


def main():
    print(f"Tracking {len(ITEM_CODES)} item codes with known item_code in sku_master.py")
    for month, rel_path in MONTHS:
        filepath = os.path.join(RM_ROOT, rel_path)
        if not os.path.exists(filepath):
            print(f"  [skip] {month}: file not found -> {filepath}")
            continue
        t0 = time.time()
        print(f"\n== {month}  ({rel_path}) ==")
        try:
            results = sum_rm_cost(filepath, ITEM_CODES.keys(), sheet_keyword="FG")
        except Exception as e:
            print(f"  ERROR parsing {filepath}: {e}")
            continue
        elapsed = time.time() - t0
        print(f"  parsed in {elapsed:.1f}s, matched {len(results)}/{len(ITEM_CODES)} item codes")
        for code, data in results.items():
            product = ITEM_CODES[code]
            costing_store.save(code, product, month, data["rm_cost"],
                                data["line_count"], rel_path)
            print(f"    {code:<28s} {product:<22s} rm_cost={data['rm_cost']:>10,.2f}  "
                  f"({data['line_count']} lines)")
        missing = set(ITEM_CODES) - set(results)
        if missing:
            print(f"  not found in this month's ledger: {sorted(missing)}")


if __name__ == "__main__":
    main()
