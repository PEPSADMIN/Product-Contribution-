"""
apply_vista_caprina_expansion.py — Phase 3 for Vista Foam, Vista Soft,
Caprina Gel, Caprina HR (Blockage 3, resolved 2026-08-08): real commercial
policy found in source_data/2 - Cirrus Foam Product Contribution
dt 06-02-2026.xlsx — 20% dealer margin (not 30% standard Cirrus or 35%
Inspree), consumer_scheme=105, with two distinct scheme_rm_pct rates:
"vista_foam" (~27.9%, Vista Foam only) and "caprina" (~13.4%, shared by
Vista Soft/Caprina Gel/Caprina HR — their own rates cluster at
14.0/13.4/12.9%, close enough that a shared bucket average matches this
tool's existing precision convention, e.g. the "inspree" bucket already
covers several distinct products with one shared rate).

All 350 codes already have real BOM/RM data from the earlier Cirrus Foam
extraction (scripts/refresh_cirrus_boms.py) — this script only writes the
sku_master.py entries, no new ledger extraction needed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "cirrus_foam_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FREIGHT_BY_HEIGHT = {4: 287.36, 5: 357.14, 6: 431.03, 8: 574.71}
CONSUMER_SCHEME = 105

LINES = {
    "Vista Foam": ("Vista Foam", "vista_foam"),
    "Vista Soft": ("Vista Soft", "caprina"),
    "Caprina Gel": ("Caprina Gel", "caprina"),
    "Caprina HR": ("Caprina HR", "caprina"),
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
    added, skipped = 0, []
    for sheet_name, (short, ck) in LINES.items():
        items = variants[sheet_name]
        for v in sorted(items, key=lambda x: (x["L"], x["W"], x["h"])):
            if v["h"] not in FREIGHT_BY_HEIGHT:
                skipped.append(v["code"] + " (no freight)")
                continue
            rm = latest_rm(v["code"])
            if rm is None:
                skipped.append(v["code"] + " (no RM)")
                continue
            product = f'{short} {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
            entry = (
                f'    {{"brand":"cirrus","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{CONSUMER_SCHEME},\n'
                f'     "channel_key":"{ck}"}},\n'
            )
            new_lines.append(entry)
            added += 1

    new_block = (
        "    # Vista Foam/Vista Soft/Caprina Gel/Caprina HR — real Ramco item\n"
        "    # codes + RM cost from the Feb-May'26 ledger (scripts/refresh_cirrus_\n"
        "    # boms.py), MRP from the Cirrus Foam MRP workbook, commercial policy\n"
        "    # (20% dealer margin, own scheme rate) from source_data/2 - Cirrus\n"
        "    # Foam Product Contribution dt 06-02-2026.xlsx — Blockage 3, resolved\n"
        "    # 2026-08-08.\n"
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
    if skipped:
        print(f"  Skipped {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
