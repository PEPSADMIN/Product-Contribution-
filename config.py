"""
Master Parameters — single source of truth. All verified against source sheets.

Values live in finance_config.json (data), not here (code), so Costing/Finance
can update a margin, GST-diff, or overhead % without touching Python. This
module just loads and exposes them under the same names (FINANCE, COMMERCIAL)
everything else already imports.

Note: derivation comments that used to sit next to individual values
(e.g. "scheme_rm_pct exact: 428.045/3232.214") now live in
finance_config_notes.md instead, since JSON has no comment syntax.
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "finance_config.json"

with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _data = json.load(_f)

FINANCE = _data["FINANCE"]
COMMERCIAL = _data["COMMERCIAL"]
