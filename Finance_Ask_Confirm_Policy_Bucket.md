# Finance Ask — confirm commercial-policy bucket for 4 product lines

**STATUS: RESOLVED 2026-09-07** — Sahana.K (Finance) replied with dealer/
distributor margins for all lines. Ardene, Spine Guard, and Kozybreeze were
already correct as-is. Vista Foam and Vista Bond were wrong (Vista Bond had
been incorrectly sharing Vista Foam's bucket) and have been corrected in
`finance_config.json` + `sku_master.py` + `peps_contribution_tool.html`.
See `docs/known_gaps.md` "Finance policy — RESOLVED" for the full breakdown.
Kept below for reference/audit trail only.

**To:** Finance / Costing
**From:** Product Contribution tooling
**Date:** 2026-09-07 (Furno removed — confirmed inactive)
**Scope:** 1,015 finished SKUs across 4 product lines. MRP and BOM/RM cost are
already present and correct for all of them. The only missing input is the
**commercial-policy bucket** — i.e. which set of dealer/distributor margin,
discount, and scheme % each line trades at.

## Background (what "policy" means here)

Each mattress is driven by a named policy bucket holding 8 commercial rates:

| Rate | Meaning |
|---|---|
| dealer_margin | Dealer margin % of MRP |
| dist_vat_diff / dist_margin | Distributor VA-tax difference + margin |
| cd | Cash discount |
| dct | Dealer CESS tax |
| tod | Trade/other discount |
| sales_return | Sales-return provision |
| scheme_rm_pct | Scheme as % of RM cost |

Every SKU needs a **channel_key** that points at the correct bucket. If a line
has no bucket, the tool silently falls back to a generic default and its margin
may be wrong.

## What needs confirmation (current state → required input)

| Line | SKUs | Current bucket | What we need from Finance |
|---|---|---|---|
| Ardene | 630 | sanibel (33%) | **Confirm** sanibel bucket is correct |
| Spine Guard | 70 | sanibel (33%) | **Confirm** sanibel bucket is correct |
| Vista Bond | 105 | vista_foam | **Confirm** vista_foam bucket is correct |
| Kozybreeze | 210 | **NONE** → generic default | **Choose** the correct bucket |

## Decisions requested

1. **Ardene** — is the sanibel dealer-margin bucket (33%) correct for Ardene? If
   it trades under a different scheme, give the 8 rates (or the bucket name).
2. **Spine Guard** — same question: confirm sanibel, or provide correct rates.
3. **Vista Bond** — confirm vista_foam, or provide correct rates.
4. **Kozybreeze** — currently has NO bucket. Which commercial policy applies?

For 4, if there is no product-specific policy, please say so explicitly — we
will then map it to the closest matching existing bucket.

## Impact

Once confirmed, we apply the bucket and the tool's per-SKU margin/scheme/EBITDA
waterfall for these 1,015 SKUs reflects the live commercial policy. Until then,
Kozybreeze remains on generic default values and should not be relied on for
margin reporting.

Note: Furno (3 SKUs) is excluded from this ask — confirmed as an inactive/
discontinued product, no policy needed.

---
Reference file: `C:\Users\ADMIN\Downloads\Product Contribution\finance_config.json`
(COMMERCIAL → peps / cirrus buckets) and `sku_master.py` (per-SKU channel_key).