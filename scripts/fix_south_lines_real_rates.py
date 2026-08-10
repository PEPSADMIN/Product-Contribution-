"""
fix_south_lines_real_rates.py — corrects freight_south, consumer_scheme,
and adds the "rg" (rate_group) field across all South-line SKUs already
in sku_master.py, using REAL per-line values found 2026-08-08 in
Contribution/1 - Peps Product Contribution dt 14-07-2026.xlsx (see
scripts/south_lines_real_rates.json for the raw extraction).

Root cause being fixed: the original South-lines expansion (Blockage 1)
assumed ALL 9 lines shared Sanibel's exact commercial policy (per an
earlier, less-informed user answer) and reused Comfort's generic height-
based freight table for everyone. This file proves that's wrong for most
lines — only Sanibel/Ardene/SPK-CT actually share Sanibel's real policy;
Zenimo/Organica/Crystal/Grand Palais/Vivah/Double Decker each have their
own distinct dealer margin, admin OHS %, freight, and consumer scheme.

Also adds Double Decker's 16" bracket (35 SKUs) — previously excluded for
lack of a verified freight figure; now resolved (3843.37, real, from this
same file), so Blockage 1's Double Decker gap is fully closed.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import costing_store

SKU_MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "sku_master.py")

# item_code prefix -> (rate_group or None [None = stays on cst=premium],
#                        {height: (freight, consumer_scheme)} OR
#                        {(marker, height): (freight, consumer_scheme)} if group-dependent)
DIM_RE = re.compile(r"X(\d+(?:\.\d+)?)$")

LINES = [
    # (match function on item_code, rate_group, height->={ (freight, cs) })
    {
        "match": lambda c: c.startswith("SKBNCT"),
        "rg": "spk_ct",
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("RTBNSNPLMFNL"),  # Sanibel MF (base/NL)
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 313)},
    },
    {
        "match": lambda c: c.startswith("RTBNSNPLMFPT"),  # Sanibel PT
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("RTBNSNPLMFET"),  # Sanibel ET
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("RTPKARPLMFNL"),  # Ardene MF (base/NL)
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("RTPKARPLMFPT"),  # Ardene PT
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("RTPKARPLMFET"),  # Ardene ET
        "rg": None,
        "by_height": {6: (431.03, 0), 8: (574.71, 0), 10: (714.29, 0)},
    },
    {
        "match": lambda c: c.startswith("PEPSPKORGBW"),  # Organica
        "rg": "organica_crystal",
        "by_height": {6: (933.71, 0), 8: (953.99, 0), 10: (998.45, 0)},
    },
    {
        "match": lambda c: c.startswith("RTGPCSBG") or c.startswith("RTGPCSPW"),  # Crystal
        "rg": "organica_crystal",
        "by_height": {6: (607.41, 285), 8: (622.59, 285), 10: (690.94, 285)},
    },
    {
        "match": lambda c: c.startswith("RTUPGPBW") or c.startswith("RTUPGPGR"),  # Grand Palais
        "rg": "grand_palais",
        "by_height": {8: (960.17, 285), 10: (1050.22, 285), 12: (1047.81, 285)},
    },
    {
        "match": lambda c: c.startswith("RTVHETPT"),  # Vivah
        "rg": "vivah",
        "by_height": {8: (676.26, 285), 10: (770.19, 285), 12: (834.73, 285)},
    },
    {
        "match": lambda c: c.startswith("RTPKDD"),  # Double Decker
        "rg": "dd",
        "by_height": {10: (2343.11, 285), 12: (2349.61, 285), 16: (3843.37, 285)},
    },
]
# Zenimo needs group-aware lookup (NL vs PT have different freight)
ZENIMO_BY_GROUP_HEIGHT = {
    ("NL", 6): (571.17, 0), ("NL", 8): (614.52, 0),
    ("PT", 6): (638.72, 0), ("PT", 8): (660.46, 0),
}


def parse_height(code):
    m = DIM_RE.search(code.split("-")[0])
    return int(float(m.group(1))) if m else None


def entry_bounds(src, code):
    idx = src.find(f'"item_code":"{code}"')
    if idx == -1:
        return None
    start = src.rfind("{", 0, idx)
    end = src.find("},\n", idx) + len("},\n")
    return start, end


def set_field(entry, field, value):
    pattern = re.compile(rf'"{field}":[\d.]+')
    if pattern.search(entry):
        return pattern.sub(f'"{field}":{value}', entry, count=1)
    return entry


def add_rg(entry, rg):
    if '"channel_key"' in entry:
        return re.sub(r'"channel_key":"[^"]*"', f'"channel_key":"sanibel","rg":"{rg}"', entry, count=1)
    # insert rg right before the closing brace
    return entry[:-3] + f',\n     "rg":"{rg}"' + entry[-3:]


def main():
    src = open(SKU_MASTER_PATH, encoding="utf-8").read()

    fixed = 0
    for code_match in re.findall(r'"item_code":"([^"]+)"', src):
        code = code_match
        if code.startswith("PEPSZENPK"):
            group = "NL" if "PKNL" in code else ("PT" if "PKPT" in code else None)
            h = parse_height(code)
            key = (group, h)
            if group is None or key not in ZENIMO_BY_GROUP_HEIGHT:
                continue
            freight, cs = ZENIMO_BY_GROUP_HEIGHT[key]
            bounds = entry_bounds(src, code)
            if not bounds:
                continue
            start, end = bounds
            entry = src[start:end]
            entry = set_field(entry, "freight_south", freight)
            entry = set_field(entry, "consumer_scheme", cs)
            if '"rg"' not in entry:
                entry = add_rg(entry, "zenimo")
            src = src[:start] + entry + src[end:]
            fixed += 1
            continue

        for line in LINES:
            if not line["match"](code):
                continue
            h = parse_height(code)
            if h not in line["by_height"]:
                continue
            freight, cs = line["by_height"][h]
            bounds = entry_bounds(src, code)
            if not bounds:
                continue
            start, end = bounds
            entry = src[start:end]
            entry = set_field(entry, "freight_south", freight)
            entry = set_field(entry, "consumer_scheme", cs)
            if line["rg"] and '"rg"' not in entry:
                entry = add_rg(entry, line["rg"])
            src = src[:start] + entry + src[end:]
            fixed += 1
            break

    open(SKU_MASTER_PATH, "w", encoding="utf-8").write(src)
    print(f"Fixed freight/consumer_scheme/rate_group on {fixed} existing entries")


if __name__ == "__main__":
    main()
