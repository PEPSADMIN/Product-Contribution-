# Known data gaps — Product Contribution Tool

Tracked blockers where real source data was missing and a number was
deliberately NOT fabricated, rather than silently guessed or left
inconsistent. Each is also called out inline as a comment at its location
in `sku_master.py`.

## Non-standard-width Cirrus Coir sizes hidden 2026-08-10

User flagged that the Material Costing tab's Size filter was showing
sizes outside the standard MRP grid. Every Peps line and the rest of
Cirrus Foam use a 7-width grid (30/36/42/48/60/66/72") — only Cirrus Coir
(Bond Plus family, Nimbo/Nimbo Plus, Comfort Plush, Luxury Memory/Plush
ET, New Eco, Eco Plus ET) has extra 54" and 84"-width columns on its own
real MRP sheet. Not a data error — these are real, MRP-priced sizes — but
not the user's standard size set, so hidden from the live tool for now,
same "keep but don't show" treatment as other inactive items.

108 SKUs moved to `scripts/coir_nonstandard_width_hidden.json` (MRP/RM
cost preserved, not deleted) and removed from `sku_master.py`. User noted
this may get its own dedicated logic/section later rather than staying
permanently hidden. Live catalog count: 3,685 (was 3,793).

## Critical bug fixed 2026-08-08 — channel_key never reached the calc engine

`applyServerSkus()` in the frontend never synced `item.channel_key` to the
`ck` field `calcSKU()`/`mcAdapt()` actually branch on — only affected
brand-new (appended) SKUs, since the original embedded fallback entries
had `ck` hardcoded directly. Real-world impact: **~800 new Inspree-family
size variants + all 350 Vista Foam/Vista Soft/Caprina Gel/Caprina HR
SKUs** were silently priced using the plain-Cirrus 30% policy instead of
their real one (35%/20%) — since whenever this session's work began.
Fixed in `applyServerSkus()` (both the matched-entry and appended-entry
paths). Worth a spot-check of Net Margin values on these products after
the next refresh, since the displayed numbers before this fix were wrong.

## Blockage 1 — South MRP lines expansion (2026-08-07)

1. ~~**Sanibel MF 6" / Sanibel MF ET 10" MRP not refreshed.**~~ **RESOLVED
   2026-08-08.** User confirmed the Purple-colour codes
   (`RTBNSNPLMFNLPR78X60X06` / `RTBNSNPLMFETPR78X60X10`) are genuinely
   manufactured — my original matcher had simply picked the Grey-colour
   code instead when both existed for the same size (a "first match wins"
   bug, not a real data gap). Re-extracted directly against
   `Accounts W - 27.07.2026\RM\4 - May'26\2 - FG MAY'26.xlsx` and
   confirmed present; both entries now carry real MRP (29024 / 43536) and
   RM cost (4446.34 / 5512.86) from May'26.
2. **Double Decker 16" height bracket excluded (35 size combos) — still
   open, deferred by user ("internal issue, later we can solve it").**
   `freight_south` is height-based (verified identical across Comfort/
   Sanibel/Italiano at 6"/8"/10"/12"), but no verified freight figure
   exists anywhere in the source data for 16".
3. ~~**Inspree Memory 5" / Inspree Memory 8" MRP not refreshed.**~~
   **RESOLVED 2026-08-08.** Same root cause and same fix as #1 — the
   Grey-colour codes (`HYPINSFMMFGR78X60X05-90D` / `...08-90D`) ARE
   present in the ledger; matcher had picked Blue instead. Re-extracted
   directly, both entries now carry real RM cost (3612.11 / 4839.14);
   MRP was already correct (colour doesn't affect list price).

**RESOLVED 2026-08-08 (second pass).** User pointed out a real source file
(`Contribution\1 - Peps Product Contribution dt 14-07-2026.xlsx`, DD tab)
with the actual Double Decker freight: 10"=2343.11, 12"=2349.61,
16"=3843.37. This revealed the ORIGINAL South-lines expansion had a much
bigger problem than just Double Decker's freight — see the new entry
below.

## Blockage 1x — South-lines commercial policy was wrong for 6 of 9 lines (2026-08-08)

While fixing Double Decker's freight, checked the same Contribution file's
tabs for every other South line and found the whole "apply Sanibel's 33%
policy to all 9 lines" assumption (from the earlier user answer) was only
correct for 3 of them. Real per-line data:

| Line | Dealer margin | Admin OHS % | Notes |
|---|---|---|---|
| Sanibel, Ardene | 33% | 23.71% | matches what was used |
| SPK-CT | 30% | 23.71% | was wrongly set to 33% |
| Zenimo | 33% | 12.52% | dealer % happened to match, admin % didn't |
| Organica, Crystal | 35% | 12.52% | was wrongly set to 33% |
| Grand Palais, Vivah, Double Decker | 40% | 12.52% | was wrongly set to 33% |

Also found: **freight is NOT a shared height-based table** across these
lines (only Sanibel/Ardene/SPK-CT happen to match the generic 431/574/714
table) — Zenimo, Organica, Crystal, Grand Palais, Vivah, and Double Decker
each have their own real, distinct freight figures. Same for
**consumer_scheme**, which varies by exact line AND height (not one flat
number per line as originally modeled) — e.g. Sanibel MF is 0/0/313 for
6"/8"/10", not a flat 313 everywhere.

**Fixed:** added 6 new commercial-policy buckets (`spk_ct`, `zenimo`,
`organica_crystal`, `grand_palais`, `vivah`, `dd`) to `finance_config.json`
plus corrected South-line-specific finance percentages (direct labour,
mfg OHS, marketing, advertisement, finance cost, depreciation — all were
being approximated from Italiano's rates, none of which actually matched).
Corrected freight_south/consumer_scheme on all ~1,400 existing South-line
SKUs to their real per-height (and per-sub-line, for Zenimo) values.
Added Double Decker's 16" bracket (35 SKUs) now that real freight exists.

Also discovered and fixed a real pre-existing bug while doing this: the
Materials-tab engine's "Finance cost" row was hardcoded to the global
default rate instead of the per-brand rate like every other cost line —
harmless before (no brand had overridden it), but would have been wrong
for the new South-line rate groups.

**Spine Guard — RESOLVED 2026-08-08.** Added as a new line: 70/70 real
size combos matched (South MRP workbook's "SPG" sheet, family prefix
`SKSGSR`), 70/70 confirmed with real BOM/RM across all 4 months. Shares
the `organica_crystal` rate group (35% dealer margin, 12.52% admin OHS —
verified identical in the Contribution file's own SPG-Bonnell tab); its
freight is Spine-Guard-specific (813.31/870.80 for 6"/8"), not shared.

## Blockage 4 — Sanibel Latex / Ardene Latex have no real item code anywhere (2026-08-08)

The Contribution file has 6 tabs for these (Sanibel Latex/Latex PT/Latex
ET, Ardene Latex/Latex PT/Latex ET) with real MRP and the same 33% dealer
margin as the rest of the Sanibel/Ardene family — but all 6 tabs list the
exact same "Item Code": `RTBNSNMR78X60X06` / `RTBNSNMR78X60X08`.

Checked what that code actually is: **"Peps Restonic Bonnell Sanibel
Normal Maroon 78x60x06"** — the plain base Sanibel line, unrelated to
Latex. This is a copy-paste artifact in the source spreadsheet (all 6
tabs were likely duplicated from the Sanibel NL tab and the Item Code
field was never updated), not a real shared code.

Searched exhaustively for a genuine Sanibel/Ardene Latex code: the main
ledger's Full FG Coverage validation export (Item Master + all 4 months +
Foam Item Codes files), the raw Item Master CSV directly, and the HCF
ledger (May+June'26) — zero matches for "Latex" combined with "Sanibel"
or "Ardene" anywhere.

**Not added** — using the placeholder code would either misattribute the
unrelated Sanibel Normal product's real BOM/cost to "Sanibel Latex", or
require inventing a cost with no data behind it. Neither is acceptable.

**Update 2026-08-10 — confirmed with two more independent sources, still
no code found.** User pointed to their actual/authoritative Item Master
(`C:\Users\ADMIN\Downloads\KR\Item Master.csv`, 201,671 rows — a
different snapshot than the project's own `Item Master/Item Master.csv`,
though same row count) and their own product classification file
(`D:\Hari JR. DATA\Development\Sales_Mobile\Excel\Category_Validation.xlsx`,
"Full Item Detail" sheet). Searched both directly for "Latex" combined
with "Sanibel"/"Ardene" — zero matches in either.

Went further and pulled every distinct Sanibel-family item description in
the KR Item Master (230 distinct base names — covers finished mattresses,
fabric, edge tape, spring units, headboards, pillows, cushions, mini
samples) and every distinct Ardene-family one (153 distinct base names,
same breadth) — genuinely nothing Latex-related in either list, not even
a raw-material component. This isn't just "the finished mattress code is
missing" — there is no trace of a Latex-specific Sanibel or Ardene
product anywhere in Ramco at any level (component or finished good).

That's now 4 independent sources checked (main ledger validation export,
raw Item Master ×2 different snapshots, HCF ledger, Category_Validation)
all agreeing: this product has never been assigned a real Ramco identity.
Strongly suggests these are planned/conceptual line extensions that were
priced out in the Contribution-file model but never actually launched or
coded into the system — not a data-search problem on my end.

**CLOSED 2026-08-10 — user confirmed these have no BOM and should be
treated as inactive/discontinued for now**, same policy already applied
to the Cirrus Coir gaps (Blockage 2): no real cost data behind a product
means mark it inactive rather than leave it as an open question. Recorded
in `scripts/sanibel_ardene_latex_inactive.json` (kept, not deleted — MRP
and everything else already known is preserved there, so this can be
reactivated instantly if a real item code is assigned later, without
redoing this investigation). Not added to `sku_master.py` — this was
already true before this pass (no verified RM cost exists to add), so
the closure is a documentation/policy step, not a data change.

## Blockage 2 — Cirrus Coir and Cirrus Latex have no real BOM/RM data (2026-08-07)

**Partially resolved 2026-08-08 — still needs more work, not fully fixed.**

Original finding: Cirrus Coir (733 combos) and Cirrus Latex/"Pin Core
Latex" (105 combos) matched real item codes in the MRP grid, but showed
zero production records in the main `Accounts W - 27.07.2026\RM` ledger.

User provided a second source: `C:\Users\ADMIN\Downloads\Product
Contribution\HCF` — a separate monthly ledger (May'26 and June'26 only,
same FG/SFG/Bom Code schema as the main ledger) using an "HCF"-prefixed
item code family (e.g. `HCFCIRCOFPLBL` = "HCF Cirrus Comfort Plush Blue")
that DOES have real production data — confirmed real, not a wrong-brand
collision like the earlier Hypnos case.

**Still unresolved:** the HCF ledger's product naming doesn't cleanly
match the 12 sub-line groups from the "Cirrus Coir Mattress MRP" price
list used to build the original 733-combo grid. Only 3 of 12 groups have
an obvious HCF equivalent:
  - Comfort Plush → `HCFCIRCOFPL*`
  - Luxury Memory → `HCFCIRLUXMF*`
  - Luxury Plush ET → `HCFCIRLUXPLET*`

The other 9 (New Eco, Cloud Plus, Nimbo, Nimbo Plus, Eco Plus ET, Bond
Plus Regular/MF Patented/MF Patented PT/Latex Patented) have no clearly
corresponding HCF code family — meanwhile the HCF ledger has its OWN
additional sub-lines (Basic, Value, Value Ortho, Economic, plain Comfort,
plain Luxury/NL) not present in the MRP price list at all. This looks
like the factory-internal (HCF) product catalog and the customer-facing
MRP price list use different internal groupings, not a 1:1 naming
mismatch fixable by a simple prefix swap.

Cirrus Latex ("Pin Core Latex") — not yet re-investigated against the HCF
source; unclear if it's tracked there at all.

**Update 2026-08-08, second pass:** re-checked directly against the raw
HCF ledger files (not the possibly-stale validation export) and found the
ORIGINAL "CIR..." item codes (not renamed to "HCF...") present in HCF's
May'26 and June'26 FG files, with real BOM data — a 5th/6th month never
checked before. This resolved most of the gap:

- **450/733 Coir combos now added** with real MRP + RM cost, across all
  groups except Cloud Plus.
- **Cloud Plus: still 0/91** — confirmed absent from the main ledger AND
  both HCF months.
- **283 other combos** (scattered across Bond Plus Regular, Comfort
  Plush, New Eco, Nimbo, Nimbo Plus — specific sizes only, not whole
  groups) also remain unmatched; full list in
  `logs/refresh_coir_hcf.log`.
- Along the way, found and fixed a real data-quality issue: some HCF
  ledger rows have the literal text `#N/A` in the Rate column instead of
  a number, which crashed the extractor — patched `bom_extractor.py` to
  treat those as 0 rather than fail the whole batch.

Cirrus Latex ("Pin Core Latex") — checked directly against both HCF
months too: still 0/105, not present under any code there either.

**Update 2026-08-08, third pass — user confirmed the root cause for part
of the gap:** White and Grey colour variants of several Coir sub-lines
have been discontinued ("stopped"), which is why they show no recent
production data — confirmed 43 of the 283 unmatched codes are White/Grey
colour codes (e.g. `CIRBOPLDGR...` "Bond Plus Dark Grey"). Also confirmed
**78x84 is the real maximum current Coir size** — 7 already-added entries
above that (L=80 or L=84, e.g. `CIRLUXPLETCR84X72X06`) were sizes beyond
current production despite having ledger data, so they were removed
rather than kept as stale/discontinued-size entries:
`CIRNECOMR80X60X04`, `CIRBOPLMFPDBL84X72X06`, `CIRBOPLMFPTPDOR84X72X06`,
`CIRLUXMFMR84X36X08`, `CIRLUXPLETGN80X66X06`, `CIRLUXPLETGN80X72X06`,
`CIRLUXPLETCR84X72X06`. Current Coir count: 443 SKUs (was 450).

**CLOSED 2026-08-08, fourth pass — user set a standing policy.** Rather
than chase a per-colour explanation for every remaining gap, the user
gave a general rule: **a colour/size with no production data in any
checked ledger is an inactive product** — Bond Plus's Grey family was the
one case with an explicit "discontinued" confirmation, but the same
"no data = inactive" logic applies uniformly, not just where a reason is
known. Sizes beyond 78x84 are separately excluded regardless of ledger
status (special-case/inactive sizes, not a data problem).

Final split of the 283 unmatched combos, recorded in
`scripts/cirrus_coir_inactive_products.json` (kept, not deleted — visible
to the tool's internals but excluded from the live/active catalog, so
they can be reactivated later without re-doing this whole investigation):

- **51 — oversized** (L>78 or W>84): excluded regardless of data status.
- **232 — inactive, no production data found**: Cloud Plus (81), Nimbo
  Plus (49), Nimbo (28), Bond Plus Regular (26, includes the confirmed
  Grey family), Comfort Plush (24), New Eco (24).

None of these 283 are added to `sku_master.py` — this was already true
before this pass (they were never added in the first place, having no
real cost data), so no code/data change was needed to "hide" them; this
pass is a documentation closure, formalizing that they're inactive by
policy rather than leaving them as an open question. Current live Coir
count remains 443 SKUs.

**Cirrus Latex — RESOLVED 2026-08-08, via a different source entirely.**
Exhaustively checked and ruled out: the main ledger (4 months), the HCF
ledger (2 months), and the "Foam Item Codes - Rate" files (raw-material
block rates only, not finished-mattress cost). Found instead in the raw
`Item Master/Item Master.csv`: all 210 full-size `HYPPINLTX...` codes have
a real "Standard Cost" field (Costing Method: STANDARD COST, Status:
ACTIVE) — a genuinely different costing mechanism than the itemized BOM
ledger, used for products that don't roll up from an FG/SFG BOM.

Standard Cost isn't pure RM cost, though — cross-checked it against 3
independently-real RM costs (`Contribution/2 - Cirrus Foam Product
Contribution dt 14-07-2026.xlsx`, " Cirrus Latex Mattress" tab, 78x60 at
5"/6"/8") and found Standard Cost / RM Cost = 1.256295 with only a 0.004%
spread across all 3 — a real, verified conversion factor, not assumed.
Used to derive RM cost for the 105 MRP-priced combos (5"/6"/8" only — the
other Item Master heights, 4"/10"/12", have no real MRP so were excluded).

Also found real commercial policy on the same tab: 35% dealer margin, 3%
DCT (not the standard Cirrus 2.85%), 0% advertising spend, consumer
scheme 189.76 flat, and finance-side percentages matching the "south"
rate group rather than plain Cirrus. Wired in as a new `cirrus_latex`
channel_key branch in both calc engines.

Because this isn't from the ledger, `server.py` labels it honestly via a
new `rm_source_note` field (`item_master:standard_cost_derived`) rather
than misrepresenting it as `ledger:<month>` or underselling it as
`estimated:...`.

## Blockage 3 — Vista Foam / Vista Soft / Caprina Gel / Caprina HR commercial policy — RESOLVED 2026-08-08

Found the real commercial policy directly in `source_data/2 - Cirrus Foam
Product Contribution dt 06-02-2026.xlsx` (a per-line "Product
Contribution" waterfall sheet — turned out to be neither the standard
Cirrus 30% nor the Inspree 35% tier):

- All 4 lines: **20% dealer margin**, consumer_scheme 105, DCT 0% (vs 2.85%
  standard Cirrus) — everything else (dist VAT diff, dist margin, CD, TOD,
  sales return) matches standard Cirrus.
- Vista Foam has its own distinct scheme rate (~27.9% of RM); Vista
  Soft/Caprina Gel/Caprina HR cluster closer together (~13-14%) — modeled
  as two new commercial-policy buckets, `cirrus.vista_foam` and
  `cirrus.caprina`, in `finance_config.json`, wired into both `calcSKU()`
  implementations in `peps_contribution_tool.html`.

All 350 real, ledger-verified codes added to `sku_master.py`
(`scripts/apply_vista_caprina_expansion.py`). No longer a gap.

## Blockage 4 — Foamera: INACTIVE product, NOT a data gap (2026-09-04)

The 3 `Foamera 4"/5"/6"` rows in `sku_master.py` have no `item_code`
(so cannot be attached to any ledger/BOM) and were previously flagged as
"unmatchable". **User confirmed Foamera is an INACTIVE/discontinued
product** — it needs no BOM/RM/MRP work and should be treated as out of
scope, not a missing-data gap. Recorded here so it is not re-reported.

(Gap tracking workbook: `Gap_Tracking.xlsx`.)

## Current gap summary (confirmed 2026-09-04)

**Needs DATA/BOM input (blocked, no BOM source in tool):**
- 12 Accessories — RM is a flat placeholder, no itemized component BOM
- Absent Peps brands — HotMot, Caspio, Allura, Carousel, Tartania, Geneva,
  Opulence, Fontaine, Cameo (exist in Item Master, not tracked)
- Absent Cirrus brands — Kozybond, Mirage, Spring Soft, Pure Latex,
  Panorama, Orthobond, Haven, Memorio

**Needs FINANCE input, but not blocking** — Ardene (630), Spine Guard (70),
Vista Bond (105), Kozybreeze (210), Furno (3) all have complete BOM/MRP;
only `policy_cost` (and, for Kozybreeze/Furno, `channel_key`) is unset.
User confirmed this can be filled in later during testing, not a launch
blocker.

**No longer gaps (resolved):**
- Peps+Cirrus no-BOM SKUs (2,946) — July'26 ledger scan
- Last 16 no-BOM (15 Pin Core Latex + 1 Peps Supreme) — commit 9887904
- 70 Crystal New Beige (-NEW) — RM from Crystal Beige
- Freight 9.76%/10.06% catalog-wide (6,536 SKUs)

**Out of scope:**
- Foamera (3 SKUs) — confirmed INACTIVE product, no BOM needed.
