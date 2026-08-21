"""
refresh_rm_costs_from_statement.py — the new, monthly RM-cost refresh path.

Unlike refresh_rm_costs.py / refresh_bom_data.py (which re-scan the giant
FG/SFG ledger exports, ~100-250MB and several minutes each), this re-prices
the EXISTING BOM structure (whatever the last real ledger extraction or the
user's own saved edits already recorded — same components, same quantities)
using fresh per-item rates from whatever file the user has most recently
dropped into RM Statement/. Structure rarely changes month to month; price
does, and this is what "the user only has to update the RM Statement" means
in practice — the BOM itself isn't re-derived, just re-priced.

Per-item rate, exactly the fallback chain specified:
    1. Closing Stock Rate   2. Stock Out Rate
    3. Stock In Rate        4. Opening Stock Rate
    5. Item Master's own Standard Cost (last resort)
A component with no rate anywhere is left at its last known cost and
reported as unresolved — never silently zeroed or fabricated.

Run this whenever a new RM Statement lands (no fixed schedule assumed).
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import bom_store
import costing_store
import history_store
import item_master
import rm_statement
from sku_master import SKUS

STATEMENT: dict


def resolve_rate(item_code: str):
    """RM Statement fallback chain, then Item Master Standard Cost.
    Returns (rate, source) or (None, None) if nothing is available anywhere."""
    hit = STATEMENT["rates"].get(item_code)
    if hit:
        return hit["rate"], hit["source"]
    std = item_master.get_standard_cost(item_code)
    if std:
        return std, "item_master_standard_cost"
    return None, None


def reprice_component(comp: dict) -> tuple[float, str | None]:
    """Re-prices one RM-warehouse line in place. Preserves whatever hidden
    unit-conversion factor the original ledger-derived cost captured (see
    bom_extractor.py's own docstring on this — e.g. spool-priced thread)
    by scaling the existing cost by the rate's ratio, rather than
    recomputing qty*rate from scratch, which would silently drop that
    factor for the handful of items where qty*rate != the real cost."""
    new_rate, source = resolve_rate(comp["code"])
    if new_rate is None:
        return comp["cost"], None
    old_rate = comp.get("rate") or 0
    new_cost = round(comp["cost"] * (new_rate / old_rate), 4) if old_rate > 0 \
        else round(comp["qty"] * new_rate, 4)
    comp["rate"] = new_rate
    comp["cost"] = new_cost
    return new_cost, source


def reprice_bom(lines: list) -> tuple[float, list]:
    total = 0.0
    unresolved = []
    for c in lines:
        if c.get("wh") == "SFG":
            children = c.get("children") or []
            if children:
                # Convention confirmed against the real ledger-extracted
                # data (see refresh_rm_costs_from_statement.py commit
                # notes): an SFG line's rate = the cost of ONE unit of
                # that sub-assembly = sum of its children's costs; its own
                # line cost = parent qty * that rate (children's own qty
                # values are already "per one unit of this SFG", baked
                # into their individual costs, not the parent's qty).
                sfg_rate = 0.0
                for child in children:
                    cost, source = reprice_component(child)
                    sfg_rate += cost
                    if source is None:
                        unresolved.append(child["code"])
                c["rate"] = round(sfg_rate, 4)
                c["cost"] = round(c.get("qty", 0) * sfg_rate, 4)
                total += c["cost"]
            else:
                # This SFG code was never itemized in the SFG ledger (no
                # sub-components on file to reprice) — its only value is
                # the FG ledger's own top-level rate for it, which the RM
                # Statement can't refresh (it lists RM items, not SFG
                # codes). Try the SFG code directly against the statement/
                # Item Master; if that also has nothing, leave the
                # existing FG-ledger-sourced cost untouched rather than
                # collapsing it to 0 by summing an empty children list.
                cost, source = reprice_component(c)
                total += cost
                if source is None:
                    unresolved.append(c["code"])
        else:
            cost, source = reprice_component(c)
            total += cost
            if source is None:
                unresolved.append(c["code"])
    return round(total, 4), unresolved


def main():
    global STATEMENT
    STATEMENT = rm_statement.parse()
    month = STATEMENT["month"] or "unknown"
    print(f"RM Statement : {STATEMENT['path']}")
    print(f"Reporting period : {month}")
    print(f"Items with a resolvable rate in the statement : {len(STATEMENT['rates'])}")

    tracked = [s for s in SKUS if s.get("item_code")]
    print(f"Re-pricing {len(tracked)} tracked products' existing BOM structure...")

    updated = 0
    no_bom = 0
    all_unresolved: set[str] = set()
    per_source: dict[str, int] = {}

    for s in tracked:
        code = s["item_code"]
        override = bom_store.get_override(code)
        if override is not None:
            lines = override
            total, unresolved = reprice_bom(lines)
            bom_store.save_override(code, lines)
        else:
            snap = bom_store.latest_snapshot(code)
            if snap is None:
                no_bom += 1
                continue
            _, lines = snap
            total, unresolved = reprice_bom(lines)
            bom_store.save_snapshot(code, month, lines)
        costing_store.save(code, s["product"], month, total, len(lines), STATEMENT["path"])
        updated += 1
        all_unresolved.update(unresolved)

    print(f"\nUpdated {updated} products' RM cost for {month}")
    print(f"No BOM structure on file yet (never extracted from a ledger) : {no_bom}")
    print(f"Components with no rate anywhere (statement or Item Master) : {len(all_unresolved)}")
    if all_unresolved:
        for code in sorted(all_unresolved)[:20]:
            print("   ", code)
        if len(all_unresolved) > 20:
            print(f"   ... and {len(all_unresolved) - 20} more")

    history_store.record(
        "system", "rm_refresh",
        f"RM Statement — {month}",
        f"Refreshed RM cost for {updated} products from {os.path.basename(STATEMENT['path'])} "
        f"(reporting period {month}); {len(all_unresolved)} components had no rate in the statement "
        f"or Item Master and were left unchanged.",
        None, {"month": month, "updated": updated, "unresolved": len(all_unresolved)},
    )


if __name__ == "__main__":
    main()
