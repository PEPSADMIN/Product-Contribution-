# Notes on finance_config.json values

Derivation notes that used to sit as inline comments next to individual
values in config.py, preserved here since JSON has no comment syntax.

- `FINANCE.admin_ohs_lump` (500), `FINANCE.mktg_ohs_lump` (1516), `FINANCE.direct_labour_spring` (400): Peps only — flat rupee amount per unit, not a percentage of RM.
- `FINANCE.admin_ohs_pct`, `FINANCE.mktg_salary_pct`, `FINANCE.direct_labour_pct_cirrus/it/acc`: percentage of RM cost, used for Cirrus/Italiano/Accessories.
- `FINANCE.depreciation_pct` (0.0155): Accessories.
- `FINANCE.depreciation_pct_cirrus` (0.0259): Cirrus + Italiano.
- `FINANCE.direct_tax_rate` (0.2517): Cirrus / Italiano / Accessories. Peps uses tax_rate=0 per management notes (income tax not considered for Peps brand).
- `COMMERCIAL.peps.dis_south.scheme_rm_pct` (0.132431): exact ratio 428.045/3232.214 from source sheet.
- `COMMERCIAL.cirrus.dis_south.scheme_rm_pct` (0.133759): exact ratio 359.597/2688.4.
- `COMMERCIAL.cirrus.inspree.scheme_rm_pct` (0.148600): exact ratio 399.956/2691.355.
- `COMMERCIAL.italiano.dis_south.scheme_rm_pct` (0.183736): exact ratio 1506.082/8196.986.
- `COMMERCIAL.peps.sanibel.scheme_rm_pct` (0.14732): exact ratio 667.664073362354/4532.33296295 (Sanibel MF 6", "Scheme (09:01)" row, source workbook). Verified 2026-07-28: Sanibel/Ardene-family Peps SKUs use 33% dealer margin (not Peps' standard 30%) and Italiano-style %-of-RM overheads (see `engine.calc_peps_premium`), not Peps' flat-₹/zero-tax convention — confirmed against dedicated per-product sheets in the Peps source workbook.
