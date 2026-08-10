"""
apply_coir_expansion.py — Phase 3 for Cirrus Coir (Blockage 2, partially
resolved 2026-08-08 via the HCF ledger). Writes the 450/733 codes with
real BOM/RM data from scripts/refresh_coir_hcf_boms.py. Cloud Plus (0/91)
and the remaining 283 combos across other groups are NOT added — no real
data exists for them in either the main ledger or the HCF ledger's
May/June'26 months.

Commercial policy: brand=cirrus, no channel_key (standard Cirrus 30%
dealer margin terms) — no evidence found anywhere that Coir products use
a different policy tier, unlike Sanibel/Ardene (Peps) or Vista/Caprina
(Cirrus Foam) which had explicit real-source evidence for a different
tier. Not assuming one without evidence.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "cirrus_coir_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FREIGHT_BY_HEIGHT = {4: 287.36, 5: 357.14, 6: 431.03, 8: 574.71}
CONSUMER_SCHEME = 105  # standard Cirrus figure — no evidence Coir differs

SHORT_NAME = {
    "New Eco": "New Eco",
    "Cloud Plus": "Cloud Plus",  # excluded below (no real data) but named for completeness
    "Nimbo": "Nimbo",
    "Nimbo Plus": "Nimbo Plus",
    "Eco Plus ET": "Eco Plus ET",
    "Bond Plus Regular": "Bond Plus",
    "Bond Plus MF Patented": "Bond Plus MF",
    "Bond Plus MF Patented PT": "Bond Plus MF PT",
    "Bond Plus Latex Patented": "Bond Plus Latex",
    "Comfort Plush": "Comfort Plush",
    "Luxury Memory": "Luxury Memory",
    "Luxury Plush ET": "Luxury Plush ET",
}


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def latest_rm(code):
    snap = costing_store.latest(code)
    return snap[1] if snap else None


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    new_lines = []
    added, skipped_no_rm, skipped_no_freight = 0, [], []
    for sheet_name, items in variants.items():
        for v in sorted(items, key=lambda x: (x["group"], x["L"], x["W"], x["h"])):
            if v["h"] not in FREIGHT_BY_HEIGHT:
                skipped_no_freight.append(v["code"])
                continue
            rm = latest_rm(v["code"])
            if rm is None:
                skipped_no_rm.append(v["code"])
                continue
            short = SHORT_NAME[v["group"]]
            product = f'{short} {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
            entry = (
                f'    {{"brand":"cirrus","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{CONSUMER_SCHEME}}},\n'
            )
            new_lines.append(entry)
            added += 1

    new_block = (
        "    # Cirrus Coir — real Ramco item codes + RM cost from the HCF ledger's\n"
        "    # May/June'26 FG data (scripts/refresh_coir_hcf_boms.py), MRP from the\n"
        "    # Cirrus Coir Mattress MRP workbook. 450/733 grid combos matched —\n"
        "    # Cloud Plus and the remaining combos across other groups have no real\n"
        "    # production data in either the main ledger or HCF May/June'26 (see\n"
        "    # docs/known_gaps.md, Blockage 2).\n"
        + "".join(new_lines)
    )
    anchor = "    # Vista bond 4\"/5\"/6\" — INTENTIONALLY NOT ADDED"
    if anchor not in src:
        print("ERROR: could not find Vista Bond anchor — aborting before partial write.")
        return
    src = src.replace(anchor, new_block + anchor, 1)

    with open(SKU_MASTER_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nWrote {SKU_MASTER_PATH}")
    print(f"  Added {added} new entries")
    if skipped_no_rm:
        print(f"  Skipped {len(skipped_no_rm)} codes with no RM cost")
    if skipped_no_freight:
        print(f"  Skipped {len(skipped_no_freight)} codes with unverified freight height")


if __name__ == "__main__":
    main()
