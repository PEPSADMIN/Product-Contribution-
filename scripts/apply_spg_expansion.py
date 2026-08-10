"""
apply_spg_expansion.py — Phase 3 for Spine Guard (SPG), a line present in
Contribution/1 - Peps Product Contribution dt 14-07-2026.xlsx's Abstract
order but never added in the original Blockage-1 sweep. Real dealer
margin (35%) and admin OHS (12.52%) match the existing "organica_crystal"
rate group exactly, so it's reused rather than adding a near-duplicate
bucket. Freight is Spine-Guard-specific (813.31/870.80 for 6"/8"), not
shared with Organica/Crystal.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "spg_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FREIGHT_BY_HEIGHT = {6: 813.31, 8: 870.80}
CONSUMER_SCHEME = 0


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def latest_rm(code):
    snap = costing_store.latest(code)
    return snap[1] if snap else None


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))["SPG"]
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    lines = []
    added, skipped_no_rm = 0, []
    for v in sorted(variants, key=lambda x: (x["L"], x["W"], x["h"])):
        rm = latest_rm(v["code"])
        if rm is None:
            skipped_no_rm.append(v["code"])
            continue
        product = f'Spine Guard {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
        entry = (
            f'    {{"brand":"peps","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
            f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{CONSUMER_SCHEME},\n'
            f'     "channel_key":"sanibel","rg":"organica_crystal","cost_structure":"premium"}},\n'
        )
        lines.append(entry)
        added += 1

    block = (
        "    # Spine Guard (SPG) — real Ramco item codes + RM cost extracted from\n"
        "    # the Feb-May'26 ledger, MRP from the 01.04.2026 South MRP workbook's\n"
        "    # SPG sheet. Shares the organica_crystal rate group (35% dealer margin,\n"
        "    # 12.52% admin OHS — verified identical in the Contribution file's\n"
        "    # SPG-Bonnell tab); freight is Spine-Guard-specific.\n"
        + "".join(lines)
    )
    anchor = "    # Vista bond 4\"/5\"/6\" — INTENTIONALLY NOT ADDED"
    if anchor not in src:
        print("ERROR: anchor not found — aborting.")
        return
    src = src.replace(anchor, block + anchor, 1)
    open(SKU_MASTER_PATH, "w", encoding="utf-8").write(src)

    print(f"Added {added} Spine Guard entries")
    if skipped_no_rm:
        print(f"Skipped {len(skipped_no_rm)} with no RM data: {skipped_no_rm[:10]}")


if __name__ == "__main__":
    main()
