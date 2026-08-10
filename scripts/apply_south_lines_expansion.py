"""
apply_south_lines_expansion.py — Phase 3 for the 10 South MRP lines
(Sanibel, Ardene, SPK CT, Organica, Zenimo, Crystal, Grand Palais, Vivah,
Double Decker, Italiano). Mirrors apply_comfort_supreme_expansion.py:

  1. Refreshes the 19 already-tracked 78x60 entries (10 Sanibel + 9
     Italiano) to current MRP (mutable, month-to-month, per the user) and
     real ledger RM cost.
  2. Inserts every other real, ledger-matched size-variant combo as a new
     SKUS entry.

Commercial policy: per explicit user confirmation, Sanibel/Ardene/SPK CT/
Organica/Zenimo/Crystal/Grand Palais/Vivah/Double Decker (everything here
except Italiano, which already has its own dedicated channel branch in
calcSKU/engine.py) share the SAME "premium" cost_structure — 33% dealer
margin, not Peps' standard 30% (see calcSKU() in the HTML / calc_peps_
premium() in engine.py). consumer_scheme is likewise carried over from the
verified Sanibel figure (313) for all of them, since that field is a flat
per-unit ₹ figure tied to the commercial-policy bucket, not the specific
product line (confirmed: Comfort and Supreme, both "dis_south", share the
same 105; Sanibel's own 3 sub-lines all share 313).

freight_south is height-based, not brand-based (confirmed: Comfort and
Sanibel use the identical 431.03/574.71/714.29 table for 6/8/10", and
Italiano's own 909.09 for 12" fits the same progression) — reused here for
6/8/10/12". No verified freight figure exists for 16" (needed only for
Double Decker) — those rows are INTENTIONALLY EXCLUDED, not fabricated,
same discipline as the existing Vista Bond exclusion already in this file.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import costing_store

VARIANTS_PATH = os.path.join(os.path.dirname(__file__), "south_lines_variants.json")
SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

FREIGHT_BY_HEIGHT = {6: 431.03, 8: 574.71, 10: 714.29, 12: 909.09}
PREMIUM_CONSUMER_SCHEME = 313  # verified Sanibel figure, shared by the whole premium bucket

# (line, group) -> short product-display name, matching each line's own
# already-established naming convention (no "Peps" prefix, as with the
# existing Sanibel/Italiano entries).
SHORT_NAME = {
    ("Sanibel", "Sanibel Plush Memory Foam"): "Sanibel MF",
    ("Sanibel", "Sanibel Plush Memory Foam Pillow Top"): "Sanibel MF PT",
    ("Sanibel", "Sanibel Plush Memory Foam Euro Top"): "Sanibel MF ET",
    ("Ardene", "Ardene Plush Memory Foam"): "Ardene MF",
    ("Ardene", "Ardene Plush Memory Foam Pillow Top"): "Ardene MF PT",
    ("Ardene", "Ardene Plush Memory Foam Euro Top"): "Ardene MF ET",
    ("SPK CT", "Springkoil Crown Top"): "SPK CT",
    ("Organica", "Organica"): "Organica",
    ("Zenimo", "Zenimo Normal"): "Zenimo",
    ("Zenimo", "Zenimo Pillow Top"): "Zenimo PT",
    ("Crystal", "Crystal"): "Crystal",
    ("Grand Palais", "Grand Palais"): "Grand Palais",
    ("Vivah", "Vivah"): "Vivah",
    ("Double Decker", "Double Decker"): "Double Decker",
    ("Italiano", "Italiano Serenita"): "Serenita NL",
    ("Italiano", "Italiano Enchanto"): "Enchanto NL",
    ("Italiano", "Italiano Enchanto ET"): "Enchanto ET",
    ("Italiano", "Italiano Icona Italia CT"): "Icona CT",
    ("Italiano", "Italiano Magnifico Italia FT"): "Magnifico FT",
}

# Existing 78x60 entries to refresh in place: (item_code, old_mrp_literal, old_rm_literal) -> just need item_code, rest is looked up fresh.
EXISTING_SANIBEL = [
    ("RTBNSNPLMFNLPR78X60X06", "Sanibel MF 6\\\"", 431.03),
    ("RTBNSNPLMFNLGR78X60X08", "Sanibel MF 8\\\"", 574.71),
    ("RTBNSNPLMFNLGR78X60X10", "Sanibel MF 10\\\"", 714.29),
    ("RTBNSNPLMFPTPR78X60X06", "Sanibel MF PT 6\\\"", 431.03),
    ("RTBNSNPLMFPTPR78X60X08", "Sanibel MF PT 8\\\"", 574.71),
    ("RTBNSNPLMFPTPR78X60X10", "Sanibel MF PT 10\\\"", 714.29),
    ("RTBNSNPLMFETGR78X60X06", "Sanibel MF ET 6\\\"", 431.03),
    ("RTBNSNPLMFETGR78X60X08", "Sanibel MF ET 8\\\"", 574.71),
    ("RTBNSNPLMFETPR78X60X10", "Sanibel MF ET 10\\\"", 714.29),
]
EXISTING_ITALIANO = [
    ("PEPSITSTPKNL78X60X06", "Serenita NL 6\\\"", 454.55),
    ("PEPSITETPKNL78X60X08", "Enchanto NL 8\\\"", 602.41),
    ("PEPSITETPKET78X60X08", "Enchanto ET 8\\\"", 602.41),
    ("PEPSITICOPKCT78X60X08", "Icona CT 8\\\"", 602.41),
    ("PEPSITICOPKCT78X60X10", "Icona CT 10\\\"", 757.58),
    ("PEPSITICOPKCT78X60X12", "Icona CT 12\\\"", 909.09),
    ("PEPSITMGPKFT78X60X08", "Magnifico FT 8\\\"", 602.41),
    ("PEPSITMGPKFT78X60X10", "Magnifico FT 10\\\"", 757.58),
    ("PEPSITMGPKFT78X60X12", "Magnifico FT 12\\\"", 909.09),
]


def fmt_dim(v):
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def latest_rm(code):
    snap = costing_store.latest(code)
    return snap[1] if snap else None


def latest_mrp(variants, code):
    for line_items in variants.values():
        for v in line_items:
            if v["code"] == code:
                return v["mrp"]
    return None


def main():
    variants = json.load(open(VARIANTS_PATH, encoding="utf-8"))
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    # ---- Step 1: refresh existing 19 entries' MRP + RM in place ----
    refreshed, skipped_refresh = 0, []
    for code, product_escaped, freight in EXISTING_SANIBEL + EXISTING_ITALIANO:
        rm = latest_rm(code)
        mrp = latest_mrp(variants, code)
        if rm is None or mrp is None:
            skipped_refresh.append(code)
            continue
        import re
        pattern = re.compile(
            r'\{"brand":"(peps|italiano)","item_code":"' + re.escape(code) +
            r'","product":"' + re.escape(product_escaped) + r'","sqft":32\.5,\n'
            r'\s*"mrp":\d+,"rm_cost":[\d.]+,"freight_south":[\d.]+,"consumer_scheme":\d+(,\n\s*"channel_key":"sanibel","cost_structure":"premium")?\}',
        )
        m = pattern.search(src)
        if not m:
            skipped_refresh.append(code + " (pattern not found)")
            continue
        brand = m.group(1)
        cs = PREMIUM_CONSUMER_SCHEME if brand == "peps" else 678
        tail = ',\n     "channel_key":"sanibel","cost_structure":"premium"' if brand == "peps" else ""
        new_entry = (
            f'{{"brand":"{brand}","item_code":"{code}","product":"{product_escaped}","sqft":32.5,\n'
            f'     "mrp":{int(mrp)},"rm_cost":{rm:.2f},"freight_south":{freight},"consumer_scheme":{cs}{tail}}}'
        )
        src = src[:m.start()] + new_entry + src[m.end():]
        refreshed += 1

    # ---- Step 2: build new entries for every combo not already tracked ----
    already_tracked = {c for c, _, _ in EXISTING_SANIBEL + EXISTING_ITALIANO}
    sanibel_ardene_block_lines = []
    italiano_block_lines = []
    added, skipped_no_rm, skipped_no_freight = 0, [], []

    for line_name, items in variants.items():
        for v in sorted(items, key=lambda x: (x["group"], x["L"], x["W"], x["h"])):
            if v["code"] in already_tracked:
                continue
            short = SHORT_NAME.get((line_name, v["group"]))
            if short is None:
                continue
            if v["h"] not in FREIGHT_BY_HEIGHT:
                skipped_no_freight.append(v["code"])
                continue
            rm = latest_rm(v["code"])
            if rm is None:
                skipped_no_rm.append(v["code"])
                continue
            product = f'{short} {fmt_dim(v["L"])}x{fmt_dim(v["W"])} {v["h"]}\\"'
            if line_name == "Italiano":
                entry = (
                    f'    {{"brand":"italiano","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                    f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":678}},\n'
                )
                italiano_block_lines.append(entry)
            else:
                entry = (
                    f'    {{"brand":"peps","item_code":"{v["code"]}","product":"{product}","sqft":{v["sqft"]:.2f},\n'
                    f'     "mrp":{int(v["mrp"])},"rm_cost":{rm:.2f},"freight_south":{FREIGHT_BY_HEIGHT[v["h"]]},"consumer_scheme":{PREMIUM_CONSUMER_SCHEME},\n'
                    f'     "channel_key":"sanibel","cost_structure":"premium"}},\n'
                )
                sanibel_ardene_block_lines.append(entry)
            added += 1

    sanibel_block = (
        "    # Sanibel/Ardene/SPK CT/Organica/Zenimo/Crystal/Grand Palais/Vivah/\n"
        "    # Double Decker size variants — real Ramco item codes + RM cost\n"
        "    # extracted from the Feb-May'26 ledger, MRP from the 01.04.2026 South\n"
        "    # MRP workbook (see scripts/build_south_lines_variants.py +\n"
        "    # scripts/refresh_south_lines_boms.py). Same premium cost_structure/\n"
        "    # consumer_scheme as Sanibel (user-confirmed 2026-08-07). Double\n"
        "    # Decker's 16\" bracket is excluded — no verified freight figure exists\n"
        "    # for that height (do not fabricate; see Vista Bond exclusion above\n"
        "    # for the same discipline).\n"
        + "".join(sanibel_ardene_block_lines)
    )
    italiano_block = (
        "    # Italiano size variants — real Ramco item codes + RM cost extracted\n"
        "    # from the Feb-May'26 ledger, MRP from the 01.04.2026 South MRP\n"
        "    # workbook (see scripts/build_south_lines_variants.py).\n"
        + "".join(italiano_block_lines)
    )

    anchor_cirrus = "    # ── Cirrus Foam"
    if anchor_cirrus not in src:
        print("ERROR: could not find Cirrus Foam anchor — aborting before partial write.")
        return
    src = src.replace(anchor_cirrus, sanibel_block + anchor_cirrus, 1)

    # Italiano anchor: end of the refreshed Italiano block. Find the last
    # existing Italiano entry's closing brace and insert right after it.
    last_italiano_code = EXISTING_ITALIANO[-1][0]
    idx = src.find(last_italiano_code)
    if idx == -1:
        print("ERROR: could not find last Italiano entry — aborting before partial write.")
        return
    end_of_entry = src.find("},\n", idx) + len("},\n")
    src = src[:end_of_entry] + italiano_block + src[end_of_entry:]

    with open(SKU_MASTER_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nWrote {SKU_MASTER_PATH}")
    print(f"  Refreshed {refreshed}/19 existing entries (MRP + RM cost)")
    if skipped_refresh:
        print(f"  Could not refresh: {skipped_refresh}")
    print(f"  Added {added} new size-variant entries")
    if skipped_no_rm:
        print(f"  Skipped {len(skipped_no_rm)} codes with no RM cost extracted")
    if skipped_no_freight:
        print(f"  Skipped {len(skipped_no_freight)} codes with no verified freight (height not in {sorted(FREIGHT_BY_HEIGHT)}): sample {skipped_no_freight[:5]}")


if __name__ == "__main__":
    main()
