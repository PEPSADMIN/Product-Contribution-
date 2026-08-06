"""
colour_lookup.py — real Colour per item_code, parsed from each SKU's own
Ramco ledger description (e.g. "Peps Bonnell Comfort Normal Beige
78X60X06" -> "Beige"). Extracted once from validation_exports/
Full_FG_Coverage_Validation.xlsx's ledger-scanned descriptions (see
scripts/export_full_fg_coverage.py) — not fabricated or guessed.

Only 42 of the 51 tracked item codes have a colour word in their real
description; the remaining 9 (all Italiano SKUs) genuinely don't state a
colour in the ledger, so they're absent here rather than guessed at.
"""

COLOUR_BY_CODE = {
    'HYPFURFMBG78X60X04': 'Beige',
    'HYPFURFMBG78X60X05': 'Beige',
    'HYPFURFMBG78X60X06': 'Beige',
    'HYPINSFMETMR78X60X05-90D': 'Maroon',
    'HYPINSFMETMR78X60X06-90D': 'Maroon',
    'HYPINSFMETMR78X60X08-90D': 'Maroon',
    'HYPINSFMLTETGRN78X60X05-90D': 'Green',
    'HYPINSFMLTETGRN78X60X06-90D': 'Green',
    'HYPINSFMLTETGRN78X60X08-90D': 'Green',
    'HYPINSFMLTGRN78X60X05-90D': 'Green',
    'HYPINSFMMFBL78X60X06-90D': 'Blue',
    'HYPINSFMMFETBL78X60X05-90D': 'Blue',
    'HYPINSFMMFETBL78X60X06-90D': 'Blue',
    'HYPINSFMMFETBL78X60X08-90D': 'Blue',
    'HYPINSFMMFGR78X60X05-90D': 'Grey',
    'HYPINSFMMFGR78X60X08-90D': 'Grey',
    'HYPINSFMMR78X60X04-90D': 'Maroon',
    'HYPKBRZFMDB78X60X04': 'Dark Blue',
    'HYPKBRZFMDB78X60X05': 'Dark Blue',
    'HYPKBRZFMDB78X60X06': 'Dark Blue',
    'HYPMEMFMVL78X60X05': 'Violet',
    'HYPMEMFMVL78X60X06': 'Violet',
    'HYPMEMFMVL78X60X08': 'Violet',
    'HYPMULTFMGR78X60X05': 'Grey',
    'HYPMULTFMGR78X60X06': 'Grey',
    'HYPMULTFMGR78X60X08': 'Grey',
    'HYPSPSFMNB78X60X05': 'Navy Blue',
    'HYPSPSFMNB78X60X06': 'Navy Blue',
    'HYPSPSFMNB78X60X08': 'Navy Blue',
    'PEPSBNCOMNLBG78X60X06': 'Beige',
    'PEPSBNCOMNLBG78X60X08': 'Beige',
    'PEPSBNCOMNLBG78X60X10': 'Beige',
    'RTBNSNBG78X60X06': 'Beige',
    'RTBNSNPLMFETGR78X60X06': 'Grey',
    'RTBNSNPLMFETGR78X60X08': 'Grey',
    'RTBNSNPLMFETPR78X60X10': 'Purple',
    'RTBNSNPLMFNLGR78X60X08': 'Grey',
    'RTBNSNPLMFNLGR78X60X10': 'Grey',
    'RTBNSNPLMFNLPR78X60X06': 'Purple',
    'RTBNSNPLMFPTPR78X60X06': 'Purple',
    'RTBNSNPLMFPTPR78X60X08': 'Purple',
    'RTBNSNPLMFPTPR78X60X10': 'Purple',
}


def colour_for(item_code: str):
    return COLOUR_BY_CODE.get(item_code)
