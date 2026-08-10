"""
apply_cirrus_latex_expansion.py — Cirrus Latex ("Pin Core Latex"), the
last remaining Blockage-2 gap. Never appears in the FG/SFG BOM ledger
(main or HCF) under any code — but the raw Item Master
(Item Master/Item Master.csv) has a real "Standard Cost" field, Costing
Method "STANDARD COST", Status "ACTIVE", for all 210 full-size HYPPINLTX
codes. That's a fully-loaded standard cost, not pure RM — but 3 exact
real RM costs exist (Contribution/2 - Cirrus Foam Product Contribution dt
14-07-2026.xlsx, " Cirrus Latex Mattress" tab, 78x60 at 5"/6"/8") to
cross-check against: Standard Cost / RM Cost = 1.25628 / 1.25632 / 1.25628
— a 0.004% spread across 3 independent points, i.e. a real, discoverable
conversion factor, not an assumption. Used here (as 1.256295, the
average) to derive RM cost for the other 102 combos from their real
Standard Cost.

Scope: only the 105 combos actually on the Cirrus Latex MRP grid (heights
5"/6"/8", the only ones with a real MRP) — not all 210 Item Master combos
(which include unpriced 4"/10"/12" heights never sold at that footprint).
"""
import csv
import json
import os
import re

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "cirrus_foam_variants.json")
ITEM_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "Item Master", "Item Master.csv")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

RATIO = 1.256295  # Standard Cost / real RM Cost, verified against 3 independent points
FREIGHT_BY_HEIGHT = {5: 558.82, 6: 666.67, 8: 883.72}
CONSUMER_SCHEME = 189.76


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def load_standard_costs():
    out = {}
    with open(ITEM_MASTER_PATH, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader)
        idx = {h: i for i, h in enumerate(headers)}
        for row in reader:
            if len(row) <= idx["Item Code"]:
                continue
            code = row[idx["Item Code"]]
            if not code.startswith("HYPPINLTX"):
                continue
            desc = row[idx["Item Variant Desc."]] if len(row) > idx["Item Variant Desc."] else ""
            if "MINI" in desc.upper():
                continue
            cost_s = row[idx["Standard Cost"]] if len(row) > idx["Standard Cost"] else ""
            try:
                out[code] = float(cost_s)
            except ValueError:
                continue
    return out


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))["Cirrus Latex"]
    std_costs = load_standard_costs()
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    lines = []
    added, skipped_no_cost = 0, []
    for v in sorted(variants, key=lambda x: (x["L"], x["W"], x["h"])):
        std_cost = std_costs.get(v["code"])
        if std_cost is None:
            skipped_no_cost.append(v["code"])
            continue
        rm = std_cost / RATIO
        product = f'Cirrus Latex {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
        entry = (
            f'    {{"brand":"cirrus","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
            f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{CONSUMER_SCHEME},\n'
            f'     "channel_key":"cirrus_latex","rm_source_note":"item_master:standard_cost_derived"}},\n'
        )
        lines.append(entry)
        added += 1

    block = (
        "    # Cirrus Latex (\"Pin Core Latex\") — never appears in the FG/SFG BOM\n"
        "    # ledger (main or HCF), but the Item Master has a real Standard Cost\n"
        "    # field for every code (Costing Method: STANDARD COST, Status:\n"
        "    # ACTIVE). RM cost derived via a verified real conversion ratio\n"
        "    # (Standard Cost / RM Cost = 1.256295, checked against 3 independent\n"
        "    # real data points at 78x60x5/6/8\" — 0.004% spread, not assumed).\n"
        "    # rm_source_note tells server.py to label this honestly (neither\n"
        "    # ledger-verified nor a blind estimate) — see server.py's api_skus().\n"
        + "".join(lines)
    )
    anchor = "    # Vista bond 4\"/5\"/6\" — INTENTIONALLY NOT ADDED"
    if anchor not in src:
        print("ERROR: anchor not found — aborting.")
        return
    src = src.replace(anchor, block + anchor, 1)
    open(SKU_MASTER_PATH, "w", encoding="utf-8").write(src)

    print(f"Added {added} Cirrus Latex entries")
    if skipped_no_cost:
        print(f"Skipped {len(skipped_no_cost)} with no Standard Cost found: {skipped_no_cost}")


if __name__ == "__main__":
    main()
