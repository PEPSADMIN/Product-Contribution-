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
