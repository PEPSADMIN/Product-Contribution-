"""runner.py — calculate all SKUs, validate, print NM abstract, what-if."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from engine import calc_peps, calc_cirrus, calc_italiano, calc_accessories
from sku_master import SKUS
from config import FINANCE, COMMERCIAL
import costing_store


def _live_rm_cost(item_code: str, hardcoded: float) -> tuple:
    """Prefer the latest Ramco-ledger-sourced RM cost for this item_code;
    fall back to sku_master.py's hardcoded value if no snapshot exists yet.

    Returns (rm_cost, rm_source) where rm_source is one of:
      "ledger:<month>"           — Ramco-ledger-verified this month
      "estimated:no_item_code"   — SKU has no item_code; can never be
                                    matched to a Ramco BOM/ledger row
      "estimated:no_ledger_match" — has an item_code but no ledger
                                    snapshot exists for it yet
    (see Leakage Analysis §C.1/§C.2 — an unverified RM cost should never
    be presented with the same confidence as a source-checked one)
    """
    if not item_code:
        return hardcoded, "estimated:no_item_code"
    snap = costing_store.latest(item_code)
    if snap is None:
        return hardcoded, "estimated:no_ledger_match"
    month, rm_cost, _source_file = snap
    return rm_cost, f"ledger:{month}"

try:
    from tabulate import tabulate
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable,"-m","pip","install","tabulate",
                           "--break-system-packages","-q"])
    from tabulate import tabulate


def run_all(overrides: dict = None, use_live_rm: bool = True) -> list:
    """overrides: {product_name: {mrp, rm_cost, ...}}

    use_live_rm=True (default, business view): prefer the latest Ramco-
    ledger RM cost per SKU — this is what the NM Abstract / HTML tool show.

    use_live_rm=False (formula-correctness check): use sku_master.py's
    static rm_cost, matching the exact snapshot VALIDATION_TARGETS were
    calibrated against. Live RM cost moves month to month by design (that's
    the point of the Ramco refresh) — validate() must hold RM cost fixed,
    or every monthly refresh looks like a broken formula when it's really
    just current, correct, different data (see Leakage Analysis §C.8).
    """
    fin = {**FINANCE}
    results = []
    for sku in SKUS:
        s = {**sku}
        key = s.get("item_code") or s["product"]
        if overrides and key in overrides:
            s.update(overrides[key])
        if overrides and s["product"] in overrides:
            s.update(overrides[s["product"]])

        brand   = s["brand"]
        mrp     = s["mrp"]
        if use_live_rm:
            rm, rm_source = _live_rm_cost(s.get("item_code", ""), s["rm_cost"])
        else:
            rm, rm_source = s["rm_cost"], "static:sku_master"
        freight = s.get("freight_south", 0)
        sqft    = s.get("sqft", 32.5)
        cs      = s.get("consumer_scheme", 105)
        channel_key = s.get("channel_key", None)

        if brand == "peps":
            policy = COMMERCIAL["peps"]["dis_south"]
            r = calc_peps(mrp, rm, freight, policy, fin,
                          product=s["product"], item_code=s.get("item_code",""),
                          channel="South DIS", sqft=sqft, consumer_scheme=cs)

        elif brand == "cirrus":
            ck = channel_key or "dis_south"
            policy = COMMERCIAL["cirrus"][ck]
            r = calc_cirrus(mrp, rm, freight, policy, fin,
                            product=s["product"], item_code=s.get("item_code",""),
                            channel="South DIS", sqft=sqft, consumer_scheme=cs)

        elif brand == "italiano":
            policy = COMMERCIAL["italiano"]["dis_south"]
            r = calc_italiano(mrp, rm, freight, policy, fin,
                              product=s["product"], item_code=s.get("item_code",""),
                              channel="South DIS", sqft=sqft)

        elif brand == "accessories":
            policy = COMMERCIAL["accessories"]["south"]
            r = calc_accessories(mrp, rm, freight, policy, fin,
                                 product=s["product"], item_code=s.get("item_code",""),
                                 channel="South", sqft=sqft,
                                 mfg_type=s.get("mfg_type","BO"))
        else:
            continue
        rd = r.to_dict()
        rd["rm_source"] = rm_source
        results.append(rd)
    return results


VALIDATION_TARGETS = {
    "Peps Comfort 6\"":   (0.08625, 0.002),
    "Peps Comfort 8\"":   (0.12732, 0.002),
    "Peps Comfort 10\"":  (0.14610, 0.002),
    "Kozybreeze 4\"":     (-0.07350, 0.003),
    "Kozybreeze 5\"":     (0.02239, 0.003),
    "Kozybreeze 6\"":     (0.10132, 0.003),
    "Furno 4\"":          (0.14907, 0.003),
    "Inspree PU 4\"":     (0.13825, 0.003),
    "Serenita NL 6\"":    (0.07643, 0.003),
    "Enchanto NL 8\"":    (0.21881, 0.003),
    "Icona CT 8\"":       (0.24696, 0.003),
    "Magnifico FT 8\"":   (0.36319, 0.003),
    "Peps Stargaze Pillow 26x16": (0.13019, 0.005),  # minor SR basis diff
    "Memory Moulded Pillow":      (0.27301, 0.010),  # mfg item, slightly diff
}


def validate(results):
    print("\n── Validation vs source sheets ─────────────────────────────────")
    passed = failed = 0
    for r in results:
        prod = r["product"]
        if prod not in VALIDATION_TARGETS:
            continue
        target, tol = VALIDATION_TARGETS[prod]
        got  = r["net_margin_pct"]
        diff = abs(got - target)
        status = "PASS" if diff <= tol else "FAIL"
        if status == "FAIL": failed += 1
        else: passed += 1
        print(f"  {status:4s}  {prod:32s}  target={target:+.4f}  got={got:+.4f}  Δ={diff:.4f}")
    print(f"\n  {passed} passed / {failed} failed")


def nm_abstract(results):
    rows = []
    for r in results:
        nm = r["net_margin_pct"]
        flag = "✓" if nm >= 0.12 else ("~" if nm >= 0.06 else "!")
        rows.append([
            r["brand"].capitalize(), r["product"],
            f"₹{r['mrp']:,.0f}", f"₹{r['net_billing_rate']:,.0f}",
            f"₹{r['rm_cost']:,.0f}", f"₹{r['ebitda']:,.0f}",
            f"{nm*100:.1f}%", flag,
        ])
    print("\n── NM Abstract ─────────────────────────────────────────────────")
    print(tabulate(rows, headers=["Brand","Product","MRP","Net Billing","RM","EBITDA","NM%",""],
                   tablefmt="simple"))
    print("\n  ✓ ≥12%   ~ 6-12%   ! <6%")


def whatif(product: str, new_mrp: float):
    ov = {product: {"mrp": new_mrp}}
    base = {r["product"]: r for r in run_all()}
    rev  = {r["product"]: r for r in run_all(ov)}
    if product not in base:
        print(f"Product '{product}' not found.")
        return
    b = base[product]; rv = rev[product]
    print(f"\n── What-if: {product}  ₹{b['mrp']:,.0f} → ₹{new_mrp:,.0f} ─────")
    rows = [
        ["Net Billing Rate", f"₹{b['net_billing_rate']:,.0f}", f"₹{rv['net_billing_rate']:,.0f}",
         f"{(rv['net_billing_rate']-b['net_billing_rate']):+,.0f}"],
        ["Net Sales",        f"₹{b['net_sales']:,.0f}",        f"₹{rv['net_sales']:,.0f}",
         f"{(rv['net_sales']-b['net_sales']):+,.0f}"],
        ["Gross Margin",     f"₹{b['gross_margin']:,.0f}",     f"₹{rv['gross_margin']:,.0f}",
         f"{(rv['gross_margin']-b['gross_margin']):+,.0f}"],
        ["EBITDA",           f"₹{b['ebitda']:,.0f}",           f"₹{rv['ebitda']:,.0f}",
         f"{(rv['ebitda']-b['ebitda']):+,.0f}"],
        ["Net Margin ₹",     f"₹{b['net_margin']:,.0f}",       f"₹{rv['net_margin']:,.0f}",
         f"{(rv['net_margin']-b['net_margin']):+,.0f}"],
        ["Net Margin %",     f"{b['net_margin_pct']*100:.2f}%",f"{rv['net_margin_pct']*100:.2f}%",
         f"{(rv['net_margin_pct']-b['net_margin_pct'])*100:+.2f}pp"],
        ["NM / sq.ft",       f"₹{b['net_margin_per_sqft']:,.2f}", f"₹{rv['net_margin_per_sqft']:,.2f}",
         f"{(rv['net_margin_per_sqft']-b['net_margin_per_sqft']):+,.2f}"],
    ]
    print(tabulate(rows, headers=["Line Item","Current","Revised","Δ"], tablefmt="simple"))


if __name__ == "__main__":
    # Formula-correctness check: static RM cost, matches VALIDATION_TARGETS' snapshot.
    validate(run_all(use_live_rm=False))
    # Business view: live Ramco-ledger RM cost where available.
    nm_abstract(run_all(use_live_rm=True))
    print()
    whatif("Peps Comfort 6\"", 17500)
    whatif("Serenita NL 6\"", 52000)
