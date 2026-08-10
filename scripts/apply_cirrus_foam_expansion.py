"""
apply_cirrus_foam_expansion.py — Phase 3 for the Cirrus Foam lines with
real, ledger-verified BOM/RM data: Kozybreeze, Inspree PU/MF/Latex
(Normal + ET), Memorio. Deliberately EXCLUDES (see docs/known_gaps.md):
  - Cirrus Latex ("Pin Core Latex") and Vista Foam/Vista Soft/Caprina Gel/
    Caprina HR — Blockage 2/3, no real data or no confirmed commercial
    policy yet.
  - Furno, Foamera, Spine Safe, Memorio Ultra, Vistabond — not covered by
    this batch's source sheets at all; left completely untouched.

Robust update strategy (learned from a near-miss on the South-lines
script): rather than reconstructing each existing entry's exact old text
to match via regex, locate each existing entry by its unique item_code
substring, then find its enclosing `{...}` dict by scanning forward to the
next "},\n" — far less fragile than pattern-matching the whole old entry.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "cirrus_foam_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FREIGHT_BY_HEIGHT = {4: 287.36, 5: 357.14, 6: 431.03, 8: 574.71}

# (sheet, group) -> (short product name, consumer_scheme, channel_key or None)
GROUP_INFO = {
    ("Kozybreeze3", "Kozybreeze"): ("Kozybreeze", 60, None),
    ("Inspree PU", "Inspree PU Normal"): ("Inspree PU", 245, "inspree"),
    ("Inspree PU", "Inspree PU ET"): ("Inspree PU ET", 245, "inspree"),
    ("Inspree MF", "Inspree Memory Foam Normal"): ("Inspree Memory", 313, "inspree"),
    ("Inspree MF", "Inspree Memory Foam ET"): ("Inspree Memory ET", 313, "inspree"),
    ("Inspree Latex", "Inspree Latex Normal"): ("Inspree Latex", 313, "inspree"),
    ("Inspree Latex", "Inspree Latex ET"): ("Inspree Latex ET", 313, "inspree"),
    ("Memorio", "Memorio"): ("Memorio", 313, "inspree"),
}

# Existing already-tracked item codes in this batch's scope (any 78x60
# combo already in sku_master.py under one of the above lines).
EXISTING_CODES = {
    "HYPKBRZFMDB78X60X04", "HYPKBRZFMDB78X60X05", "HYPKBRZFMDB78X60X06",
    "HYPINSFMMR78X60X04-90D",
    "HYPINSFMETMR78X60X05-90D", "HYPINSFMETMR78X60X06-90D", "HYPINSFMETMR78X60X08-90D",
    "HYPINSFMMFGR78X60X05-90D", "HYPINSFMMFBL78X60X06-90D", "HYPINSFMMFGR78X60X08-90D",
    "HYPINSFMMFETBL78X60X05-90D", "HYPINSFMMFETBL78X60X06-90D", "HYPINSFMMFETBL78X60X08-90D",
    "HYPINSFMLTGRN78X60X05-90D",
    "HYPINSFMLTETGRN78X60X05-90D", "HYPINSFMLTETGRN78X60X06-90D", "HYPINSFMLTETGRN78X60X08-90D",
    "HYPMEMFMVL78X60X05", "HYPMEMFMVL78X60X06", "HYPMEMFMVL78X60X08",
}
# Existing blank-item_code entries to fill in, keyed by product name.
BLANK_CODE_PRODUCTS = {
    "Inspree PU 5\"": ("Inspree PU", 5),
    "Inspree PU 6\"": ("Inspree PU", 6),
    "Inspree PU 8\"": ("Inspree PU", 8),
}


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def latest_rm(code):
    snap = costing_store.latest(code)
    return snap[1] if snap else None


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    # Index variants by (sheet, group, L, W, h) for quick lookup.
    by_key = {}
    for sheet_name, items in variants.items():
        for v in items:
            by_key[(sheet_name, v["group"], v["L"], v["W"], v["h"])] = v

    # ---- Step 1: refresh existing entries in place (by item_code anchor) ----
    refreshed, skipped_refresh = 0, []
    for code in sorted(EXISTING_CODES):
        rm = latest_rm(code)
        if rm is None:
            skipped_refresh.append(code + " (no fresh RM)")
            continue
        # Find the mrp for this code from the variants data.
        mrp = None
        for v in by_key.values():
            if v["code"] == code:
                mrp = v["mrp"]
                break
        if mrp is None:
            skipped_refresh.append(code + " (no fresh MRP)")
            continue
        idx = src.find(f'"item_code":"{code}"')
        if idx == -1:
            skipped_refresh.append(code + " (not found in file)")
            continue
        entry_start = src.rfind("{", 0, idx)
        entry_end = src.find("},\n", idx) + len("},\n")
        old_entry = src[entry_start:entry_end]
        new_entry = re.sub(r'"mrp":\d+', f'"mrp":{int(mrp)}', old_entry)
        new_entry = re.sub(r'"rm_cost":[\d.]+', f'"rm_cost":{rm:.2f}', new_entry)
        src = src[:entry_start] + new_entry + src[entry_end:]
        refreshed += 1

    # ---- Step 2: fill in previously-blank item codes ----
    filled = 0
    for product, (short, height) in BLANK_CODE_PRODUCTS.items():
        key = None
        for (sheet, group), (s, cs, ck) in GROUP_INFO.items():
            if s == short:
                key = (sheet, group, 78, 60, height)
                break
        v = by_key.get(key)
        if not v:
            continue
        rm = latest_rm(v["code"])
        if rm is None:
            continue
        idx = src.find(f'"product":"{product}"')
        if idx == -1:
            continue
        entry_start = src.rfind("{", 0, idx)
        entry_end = src.find("},\n", idx) + len("},\n")
        old_entry = src[entry_start:entry_end]
        new_entry = old_entry.replace('"item_code":""', f'"item_code":"{v["code"]}"')
        new_entry = re.sub(r'"mrp":\d+', f'"mrp":{int(v["mrp"])}', new_entry)
        new_entry = re.sub(r'"rm_cost":[\d.]+', f'"rm_cost":{rm:.2f}', new_entry)
        src = src[:entry_start] + new_entry + src[entry_end:]
        filled += 1

    # ---- Step 3: add new size-variant entries ----
    already_tracked = set(EXISTING_CODES)
    new_lines = []
    added, skipped_no_rm, skipped_no_freight = 0, [], []
    for sheet_name, items in variants.items():
        for v in sorted(items, key=lambda x: (x["group"], x["L"], x["W"], x["h"])):
            info = GROUP_INFO.get((sheet_name, v["group"]))
            if info is None:
                continue  # Cirrus Latex / not in this batch's safe scope
            if v["code"] in already_tracked:
                continue
            if v["h"] not in FREIGHT_BY_HEIGHT:
                skipped_no_freight.append(v["code"])
                continue
            rm = latest_rm(v["code"])
            if rm is None:
                skipped_no_rm.append(v["code"])
                continue
            short, cs, ck = info
            product = f'{short} {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
            ck_line = f',\n     "channel_key":"{ck}"' if ck else ""
            entry = (
                f'    {{"brand":"cirrus","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{cs}{ck_line}}},\n'
            )
            new_lines.append(entry)
            added += 1

    new_block = (
        "    # Kozybreeze/Inspree PU-MF-Latex/Memorio size variants — real Ramco\n"
        "    # item codes + RM cost extracted from the Feb-May'26 ledger, MRP from\n"
        "    # the 01.04.2026 Cirrus Foam MRP workbook (see\n"
        "    # scripts/build_cirrus_foam_variants.py + scripts/refresh_cirrus_boms.py).\n"
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
    print(f"  Refreshed {refreshed}/{len(EXISTING_CODES)} existing entries")
    if skipped_refresh:
        print(f"  Could not refresh: {skipped_refresh}")
    print(f"  Filled in {filled} previously-blank item codes")
    print(f"  Added {added} new size-variant entries")
    if skipped_no_rm:
        print(f"  Skipped {len(skipped_no_rm)} codes with no fresh RM cost")
    if skipped_no_freight:
        print(f"  Skipped {len(skipped_no_freight)} codes with unverified freight height")


if __name__ == "__main__":
    main()
