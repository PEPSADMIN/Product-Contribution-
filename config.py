"""Master Parameters — single source of truth. All verified against source sheets."""

FINANCE = {
    "mfg_ohs_pct":              0.0672,
    "admin_ohs_lump":           500,        # Peps: ₹ flat per unit
    "admin_ohs_pct":            0.1815,     # Cirrus / Accessories: % of RM
    "admin_ohs_pct_it":         0.2371,     # Italiano: % of RM
    "mktg_ohs_lump":            1516,       # Peps: ₹ flat per unit
    "mktg_salary_pct":          0.1672,     # Cirrus / Accessories: % of RM
    "mktg_salary_pct_it":       0.163,      # Italiano: % of RM
    "adv_promo_pct_it":         0.1921,     # Italiano A&P: % of RM
    "finance_cost_pct":         0.0204,
    "depreciation_pct":         0.0155,     # Accessories
    "depreciation_pct_cirrus":  0.0259,     # Cirrus + Italiano
    "direct_tax_rate":          0.2517,     # Cirrus / Italiano / Accessories
    # Peps: tax_rate=0 (per mgmt notes: income tax not considered)
    "direct_labour_spring":     400,        # Peps: ₹ flat per unit
    "direct_labour_pct_cirrus": 0.1635,     # % of RM
    "direct_labour_pct_it":     0.1635,
    "direct_labour_pct_acc":    0.0982,
}

COMMERCIAL = {
    "peps": {
        "dis_south": {
            "dealer_margin": 0.30, "dist_vat_diff": 0.016364, "dist_margin": 0.10,
            "cd": 0.030, "dct": 0.040, "tod": 0.030, "sales_return": 0.015,
            "scheme_rm_pct": 0.132431,   # exact: 428.045/3232.214
        },
        "dd_south": {
            "dealer_margin": 0.35, "dist_vat_diff": 0.0, "dist_margin": 0.0,
            "cd": 0.030, "dct": 0.040, "tod": 0.0, "sales_return": 0.015,
            "scheme_rm_pct": 0.132431,
        },
        "dd_a_south": {
            "dealer_margin": 0.40, "dist_vat_diff": 0.0, "dist_margin": 0.0,
            "cd": 0.030, "dct": 0.0, "tod": 0.0, "sales_return": 0.015,
            "scheme_rm_pct": 0.0,
        },
    },
    "cirrus": {
        "dis_south": {
            "dealer_margin": 0.30, "dist_vat_diff": 0.016364, "dist_margin": 0.10,
            "cd": 0.030, "dct": 0.0285, "tod": 0.040, "sales_return": 0.015,
            "scheme_rm_pct": 0.133759,   # exact: 359.597/2688.4
        },
        "inspree": {
            "dealer_margin": 0.35, "dist_vat_diff": 0.016364, "dist_margin": 0.10,
            "cd": 0.030, "dct": 0.0285, "tod": 0.040, "sales_return": 0.015,
            "scheme_rm_pct": 0.148600,   # exact: 399.956/2691.355
        },
        "mgmt": {
            "dealer_margin": 0.30, "dist_vat_diff": 0.016364, "dist_margin": 0.10,
            "cd": 0.030, "dct": 0.0285, "tod": 0.040, "sales_return": 0.0573,
            "scheme_rm_pct": 0.133759,
        },
    },
    "italiano": {
        "dis_south": {
            "dealer_margin": 0.40, "dist_vat_diff": 0.016364, "dist_margin": 0.10,
            "cd": 0.030, "dct": 0.040, "tod": 0.030, "sales_return": 0.015,
            "scheme_rm_pct": 0.183736,   # exact: 1506.082/8196.986
        },
    },
    "accessories": {
        "south": {
            "dealer_margin": 0.50, "dist_vat_diff": 0.0, "dist_margin": 0.0,
            "cd": 0.030, "dct": 0.0, "tod": 0.0, "sales_return": 0.015,
            "scheme_rm_pct": 0.0,
        },
        "pan_india": {
            "dealer_margin": 0.50, "dist_vat_diff": 0.0, "dist_margin": 0.0,
            "cd": 0.0, "dct": 0.0, "tod": 0.0, "sales_return": 0.015,
            "scheme_rm_pct": 0.0,
        },
    },
}
