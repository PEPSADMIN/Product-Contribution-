"""
Peps Industries — Product Contribution Engine v3
All formula bases verified line-by-line against source sheets.

Verified bases (corrections from v2):
  admin_ohs     = rm_cost × pct  for ALL brands (Peps: lump ₹; others: % of RM)
  depreciation  = Peps=0, Cirrus/Italiano=0.0259, Accessories=0.0155
  direct_taxes  = ebt × rate  (ALWAYS — negative EBT gives negative tax = deferred asset)
  net_margin%   = net_margin / net_sales  (not /MRP)
  Peps: tax_rate=0 (notes: income tax not considered)
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ContributionResult:
    product: str = ""; item_code: str = ""; brand: str = ""; channel: str = ""
    mrp: float = 0.0
    dealer_margin: float = 0.0; dealer_price: float = 0.0
    dist_vat_diff: float = 0.0; after_vat: float = 0.0
    dist_margin: float = 0.0; dist_price: float = 0.0
    cgst: float = 0.0; sgst: float = 0.0; net_billing_rate: float = 0.0
    sales_return: float = 0.0; cd: float = 0.0; dct: float = 0.0
    tod: float = 0.0; scheme: float = 0.0; net_sales: float = 0.0
    direct_labour: float = 0.0; rm_cost: float = 0.0
    consumer_scheme: float = 0.0; mfg_ohs: float = 0.0
    gross_margin: float = 0.0
    marketing_ohs: float = 0.0; adv_promo: float = 0.0
    freight_ohs: float = 0.0; admin_ohs: float = 0.0
    ebitda: float = 0.0; finance_cost: float = 0.0; depreciation: float = 0.0
    ebt: float = 0.0; direct_taxes: float = 0.0
    net_margin: float = 0.0; net_margin_pct: float = 0.0
    sqft: float = 32.5; net_margin_per_sqft: float = 0.0

    def to_dict(self): return asdict(self)


def calculate(mrp, rm_cost, freight_ohs, direct_labour, consumer_scheme,
              channel_policy, finance, product="", item_code="", brand="",
              channel="", sqft=32.5,
              admin_ohs_lump=None,    # ₹ lump (Peps only)
              mktg_ohs_lump=None,     # ₹ lump (Peps only)
              adv_promo_pct=0.0,
              admin_ohs_pct=None,     # % of RM
              mktg_salary_pct=None,   # % of RM
              depreciation_pct=None,
              direct_tax_rate=None,   # override per brand
              ) -> ContributionResult:

    r = ContributionResult(product=product, item_code=item_code,
                           brand=brand, channel=channel, mrp=mrp, sqft=sqft)
    p = channel_policy; f = finance; gst = f.get("gst_pct", 0.18)

    # ── Revenue waterfall ────────────────────────────────────────────────────
    r.dealer_margin = mrp * p["dealer_margin"]
    r.dealer_price  = mrp - r.dealer_margin
    dv = p["dist_vat_diff"]
    r.dist_vat_diff = r.dealer_price * dv / (1 + dv) if dv else 0.0
    r.after_vat     = r.dealer_price / (1 + dv) if dv else r.dealer_price
    dm = p["dist_margin"]
    r.dist_margin   = r.after_vat * dm / (1 + dm) if dm else 0.0
    r.dist_price    = r.after_vat / (1 + dm) if dm else r.after_vat
    r.cgst = r.sgst = r.dist_price * (gst / 2) / (1 + gst)
    r.net_billing_rate = r.dist_price / (1 + gst)

    # ── Deductions ───────────────────────────────────────────────────────────
    r.sales_return = rm_cost * p["sales_return"]            # % of RM
    r.cd    = r.dist_price * p["cd"]                        # % of dist_price
    r.dct   = (r.dealer_price / (1 + gst)) * p["dct"]      # % of GST-ex dealer price
    r.tod   = r.net_billing_rate * p["tod"]                 # % of NBR
    r.scheme = rm_cost * p.get("scheme_rm_pct", 0.0)        # % of RM
    r.net_sales = (r.net_billing_rate
                   - r.sales_return - r.cd - r.dct - r.tod - r.scheme)

    # ── Costs ────────────────────────────────────────────────────────────────
    r.direct_labour = direct_labour; r.rm_cost = rm_cost
    r.consumer_scheme = consumer_scheme
    r.mfg_ohs = rm_cost * f["mfg_ohs_pct"]
    r.gross_margin = (r.net_sales - r.direct_labour - r.rm_cost
                      - r.consumer_scheme - r.mfg_ohs)

    # ── Overheads (all % of RM unless lump) ─────────────────────────────────
    r.marketing_ohs = (mktg_ohs_lump if mktg_ohs_lump is not None
                       else rm_cost * (mktg_salary_pct or f.get("mktg_salary_pct", 0.1672)))
    r.adv_promo   = rm_cost * adv_promo_pct
    r.freight_ohs = freight_ohs
    r.admin_ohs   = (admin_ohs_lump if admin_ohs_lump is not None
                     else rm_cost * (admin_ohs_pct or f.get("admin_ohs_pct", 0.1815)))
    r.ebitda = r.gross_margin - r.marketing_ohs - r.adv_promo - r.freight_ohs - r.admin_ohs

    # ── Below EBITDA ─────────────────────────────────────────────────────────
    r.finance_cost = rm_cost * f["finance_cost_pct"]
    dep = depreciation_pct if depreciation_pct is not None else f.get("depreciation_pct", 0.0)
    r.depreciation = rm_cost * dep
    r.ebt = r.ebitda - r.finance_cost - r.depreciation
    # Tax applied to full EBT (negative EBT → negative tax = deferred asset)
    # Peps: tax_rate=0 per management notes
    tax_rate = (direct_tax_rate if direct_tax_rate is not None
                else f.get("direct_tax_rate", 0.2517))
    r.direct_taxes = r.ebt * tax_rate
    r.net_margin   = r.ebt - r.direct_taxes           # = ebt * (1 - tax_rate)
    r.net_margin_pct      = r.net_margin / r.net_sales if r.net_sales else 0.0
    r.net_margin_per_sqft = r.net_margin / sqft if sqft else 0.0

    for k, v in r.__dict__.items():
        if isinstance(v, float): setattr(r, k, round(v, 4))
    return r


def calc_peps(mrp, rm_cost, freight_ohs, channel_policy, finance,
              product="", item_code="", channel="", sqft=32.5, consumer_scheme=105):
    return calculate(mrp, rm_cost, freight_ohs, finance["direct_labour_spring"],
                     consumer_scheme, channel_policy, finance,
                     product=product, item_code=item_code, brand="peps",
                     channel=channel, sqft=sqft,
                     admin_ohs_lump=finance["admin_ohs_lump"],
                     mktg_ohs_lump=finance["mktg_ohs_lump"],
                     depreciation_pct=0.0, direct_tax_rate=0.0)


def calc_cirrus(mrp, rm_cost, freight_ohs, channel_policy, finance,
                product="", item_code="", channel="", sqft=32.5, consumer_scheme=60):
    return calculate(mrp, rm_cost, freight_ohs,
                     rm_cost * finance["direct_labour_pct_cirrus"], consumer_scheme,
                     channel_policy, finance, product=product, item_code=item_code,
                     brand="cirrus", channel=channel, sqft=sqft,
                     admin_ohs_pct=finance["admin_ohs_pct"],
                     mktg_salary_pct=finance["mktg_salary_pct"],
                     depreciation_pct=finance["depreciation_pct_cirrus"])


def calc_italiano(mrp, rm_cost, freight_ohs, channel_policy, finance,
                  product="", item_code="", channel="", sqft=32.5):
    return calculate(mrp, rm_cost, freight_ohs,
                     rm_cost * finance["direct_labour_pct_it"], 678,
                     channel_policy, finance, product=product, item_code=item_code,
                     brand="italiano", channel=channel, sqft=sqft,
                     admin_ohs_pct=finance["admin_ohs_pct_it"],
                     mktg_salary_pct=finance["mktg_salary_pct_it"],
                     adv_promo_pct=finance["adv_promo_pct_it"],
                     depreciation_pct=finance["depreciation_pct_cirrus"])


def calc_accessories(mrp, rm_cost, freight_ohs, channel_policy, finance,
                     product="", item_code="", channel="", sqft=1.0, mfg_type="BO"):
    dl = rm_cost * finance["direct_labour_pct_acc"] if mfg_type != "BO" else 0.0
    r = calculate(mrp, rm_cost, freight_ohs, dl, 0, channel_policy, finance,
                  product=product, item_code=item_code, brand="accessories",
                  channel=channel, sqft=sqft,
                  admin_ohs_pct=finance["admin_ohs_pct"],
                  mktg_salary_pct=finance["mktg_salary_pct"],
                  depreciation_pct=finance["depreciation_pct"])
    if mfg_type == "BO":
        r.mfg_ohs = 0.0; r.direct_labour = 0.0
        r.gross_margin = r.net_sales - r.rm_cost
        r.ebitda = r.gross_margin - r.marketing_ohs - r.freight_ohs - r.admin_ohs
        r.ebt    = r.ebitda - r.finance_cost - r.depreciation
        r.direct_taxes = r.ebt * finance["direct_tax_rate"]
        r.net_margin   = r.ebt - r.direct_taxes
        r.net_margin_pct      = round(r.net_margin / r.net_sales, 4) if r.net_sales else 0.0
        r.net_margin_per_sqft = round(r.net_margin / sqft, 4) if sqft else 0.0
    return r
