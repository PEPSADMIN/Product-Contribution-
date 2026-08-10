"""
fix_inspree_duplicates.py — one-off correction for a bug in
apply_cirrus_foam_expansion.py: a quote-escaping mismatch meant the
"Inspree PU 5/6/8\"" blank-item_code fill-in silently failed, and instead
the new-size-variant loop added "Inspree PU 78x60 5/6/8\"" /
"Inspree Memory 78x60 5/8\"" as separate, duplicate-looking entries for
the exact same size already tracked under a different name.

Fixes:
  1. "Inspree PU 5/6/8\"" — were genuinely blank (no prior colour
     commitment) — fill in their item_code/mrp/rm_cost for real now, then
     delete the redundant "Inspree PU 78x60 X\"" duplicates.
  2. "Inspree Memory 5/8\"" — DO have a prior colour commitment (Grey,
     no fresh ledger data, same situation as the Sanibel Blockage 1 case)
     — leave those untouched, just delete the redundant BL-coloured
     "Inspree Memory 78x60 X\"" duplicates rather than silently swapping
     colours under existing tracked names.
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import costing_store

SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FILL_IN = {
    'Inspree PU 5\\"': "HYPINSFMMR78X60X05-90D",
    'Inspree PU 6\\"': "HYPINSFMMR78X60X06-90D",
    'Inspree PU 8\\"': "HYPINSFMMR78X60X08-90D",
}
DELETE_PRODUCTS = [
    'Inspree PU 78x60 5\\"', 'Inspree PU 78x60 6\\"', 'Inspree PU 78x60 8\\"',
    'Inspree Memory 78x60 5\\"', 'Inspree Memory 78x60 8\\"',
]


def entry_bounds(src, product_marker):
    idx = src.find(f'"product":"{product_marker}"')
    if idx == -1:
        return None
    start = src.rfind("{", 0, idx)
    end = src.find("},\n", idx) + len("},\n")
    return start, end


def main():
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    filled = 0
    for product, code in FILL_IN.items():
        snap = costing_store.latest(code)
        if not snap:
            print(f"SKIP fill {product}: no RM data for {code}")
            continue
        rm = snap[1]
        bounds = entry_bounds(src, product)
        if not bounds:
            print(f"SKIP fill {product}: entry not found")
            continue
        start, end = bounds
        entry = src[start:end]
        entry = entry.replace('"item_code":""', f'"item_code":"{code}"')
        entry = re.sub(r'"rm_cost":[\d.]+', f'"rm_cost":{rm:.2f}', entry)
        src = src[:start] + entry + src[end:]
        filled += 1
        print(f"Filled {product} -> {code}, rm={rm:.2f}")

    deleted = 0
    for product in DELETE_PRODUCTS:
        bounds = entry_bounds(src, product)
        if not bounds:
            print(f"SKIP delete {product}: not found (already gone?)")
            continue
        start, end = bounds
        src = src[:start] + src[end:]
        deleted += 1
        print(f"Deleted duplicate entry: {product}")

    with open(SKU_MASTER_PATH, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"\nDone. Filled {filled}, deleted {deleted}.")


if __name__ == "__main__":
    main()
