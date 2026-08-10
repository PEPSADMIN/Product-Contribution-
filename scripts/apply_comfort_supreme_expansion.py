"""
apply_comfort_supreme_expansion.py — Phase 3: writes the actual
sku_master.py changes once refresh_comfort_supreme_boms.py has populated
real RM cost for all 210 Comfort/Supreme size-variant codes.

Does two things:
  1. Refreshes the 6 existing 78x60 Comfort/Supreme entries' MRP to the
     current 01.04.2026 MRP grid value (MRP is a mutable, month-to-month
     figure per the user — not something to leave frozen at whatever
     month sku_master.py happened to be built from), and fills in the
     Supreme entries' previously-blank item_code now that a real one is
     known.
  2. Inserts the other 204 size-variant entries (all combos except the
     already-tracked 78x60) as new SKUS entries, each with its own real
     item_code, MRP (from the grid), and RM cost (from this month's/any
     month's ledger extraction via costing_store).

Only ever appends/updates — never removes anything a user might already
be relying on.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "comfort_supreme_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

# Freight/consumer-scheme are carried over from the existing height-based
# convention already used for every other Peps-standard SKU in
# sku_master.py (431.03/574.71/714.29 by height 6/8/10, consumer_scheme
# 105 flat) — no per-footprint freight data exists to verify these
# against for the new sizes, so this is an approximation, not a gap we
# can currently close.
FREIGHT_BY_HEIGHT = {'6': 431.03, '8': 574.71, '10': 714.29}
CONSUMER_SCHEME = 105


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    # ---- Step 1: refresh the 6 existing 78x60 entries' MRP + fill in Supreme's item_code ----
    refresh_map = {}  # product name -> (new_mrp, item_code)
    for line_name, items in variants.items():
        for v in items:
            if v["L"] == 78 and v["W"] == 60:
                product = f'Peps {line_name} {v["h"]}"'
                refresh_map[product] = (v["mrp"], v["code"])

    old_block = '''    {"brand":"peps","item_code":"PEPSBNCOMNLBG78X60X06","product":"Peps Comfort 6\\"","sqft":32.5,
     "mrp":15999,"rm_cost":3232.21,"freight_south":431.03,"consumer_scheme":105},
    {"brand":"peps","item_code":"PEPSBNCOMNLBG78X60X08","product":"Peps Comfort 8\\"","sqft":32.5,
     "mrp":18499,"rm_cost":3720.74,"freight_south":574.71,"consumer_scheme":105},
    {"brand":"peps","item_code":"PEPSBNCOMNLBG78X60X10","product":"Peps Comfort 10\\"","sqft":32.5,
     "mrp":20999,"rm_cost":4310.56,"freight_south":714.29,"consumer_scheme":105},
    {"brand":"peps","item_code":"","product":"Peps Supreme 6\\"","sqft":32.5,
     "mrp":18999,"rm_cost":3295.50,"freight_south":431.03,"consumer_scheme":105},
    {"brand":"peps","item_code":"","product":"Peps Supreme 8\\"","sqft":32.5,
     "mrp":21555,"rm_cost":3867.17,"freight_south":574.71,"consumer_scheme":105},
    {"brand":"peps","item_code":"","product":"Peps Supreme 10\\"","sqft":32.5,
     "mrp":24999,"rm_cost":4473.30,"freight_south":714.29,"consumer_scheme":105},
'''
    def existing_rm(code):
        snap = costing_store.latest(code)
        return snap[1] if snap else None

    new_lines = []
    for line_name, height, old_mrp, old_rm, old_code in [
        ("Comfort", "6", 15999, 3232.21, "PEPSBNCOMNLBG78X60X06"),
        ("Comfort", "8", 18499, 3720.74, "PEPSBNCOMNLBG78X60X08"),
        ("Comfort", "10", 20999, 4310.56, "PEPSBNCOMNLBG78X60X10"),
        ("Supreme", "6", 18999, 3295.50, ""),
        ("Supreme", "8", 21555, 3867.17, ""),
        ("Supreme", "10", 24999, 4473.30, ""),
    ]:
        product = f'Peps {line_name} {height}"'
        new_mrp, code = refresh_map.get(product, (old_mrp, old_code or None))
        rm = existing_rm(code) if code else None
        rm = rm if rm is not None else old_rm
        new_lines.append(
            f'    {{"brand":"peps","item_code":"{code or ""}","product":"Peps {line_name} {height}\\"","sqft":32.5,\n'
            f'     "mrp":{int(new_mrp)},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[height]},"consumer_scheme":{CONSUMER_SCHEME}}},\n'
        )
    new_block = "".join(new_lines)
    src = src.replace(old_block, new_block)

    # ---- Step 2: build the 204 new size-variant entries ----
    variant_lines = []
    skipped_no_rm = []
    added = 0
    for line_name, items in variants.items():
        for v in sorted(items, key=lambda x: (x["L"], x["W"], x["h"])):
            if v["L"] == 78 and v["W"] == 60:
                continue  # already tracked, handled in step 1
            rm = existing_rm(v["code"])
            if rm is None:
                skipped_no_rm.append(v["code"])
                continue
            # NOTE: product ends with a literal `"` (the height mark) —
            # must be escaped before embedding into the generated Python
            # source string below, or it prematurely closes the "product"
            # string literal and corrupts every line after it.
            product = f'Peps {line_name} {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
            variant_lines.append(
                f'    {{"brand":"peps","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{CONSUMER_SCHEME}}},\n'
            )
            added += 1

    variant_block = (
        "    # Comfort & Supreme size variants — real Ramco item codes + RM cost\n"
        "    # extracted from the Feb-May'26 ledger, MRP from the 01.04.2026 South\n"
        "    # MRP price list (see scripts/build_comfort_supreme_variants.py +\n"
        "    # scripts/refresh_comfort_supreme_boms.py). Freight/consumer scheme\n"
        "    # carried over from the existing height-based convention (no verified\n"
        "    # per-footprint freight data exists yet).\n"
        + "".join(variant_lines)
    )

    anchor = '    # Sanibel family — FIXED 2026-07-28.'
    if anchor not in src:
        print("ERROR: could not find insertion anchor point — aborting before partial write.")
        return
    src = src.replace(anchor, variant_block + anchor, 1)

    with open(SKU_MASTER_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nWrote {SKU_MASTER_PATH}")
    print(f"  Refreshed 6 existing 78x60 Comfort/Supreme entries (MRP + item codes)")
    print(f"  Added {added} new size-variant entries")
    if skipped_no_rm:
        print(f"  Skipped {len(skipped_no_rm)} codes with no RM cost extracted yet:")
        for c in skipped_no_rm:
            print(f"    {c}")


if __name__ == "__main__":
    main()
