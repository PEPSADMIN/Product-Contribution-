"""
server.py — live API + static host for the Product Contribution web tool,
mirroring BOM Tool's pattern (Flask app serving both the page and a JSON
API the page's own JS calls, instead of a static file with data baked in).

Endpoints:
  GET /                          -> the web tool (web/peps_contribution_tool.html)
  GET /peps_contribution_tool.html -> same
  GET /api/skus                  -> sku_master.SKUS merged with the latest
                                     Ramco-ledger RM cost (costing_store),
                                     falling back to the hardcoded value
  GET /api/config                -> FINANCE + COMMERCIAL from config.py
                                     (finance_config.json under the hood)
  GET /api/bom/<item_code>       -> itemized BOM (FG->SFG->RM), from the
                                     user's saved edits if any, else the
                                     latest ledger-extracted snapshot
  POST /api/bom/<item_code>      -> save the user's edited BOM tree
  DELETE /api/bom/<item_code>    -> discard edits, revert to the ledger baseline
  GET /api/rm-history/<item_code> -> every tracked month's RM cost snapshot
                                     (Product History tab)
  GET /api/bom-history/<item_code>/<month> -> that month's real itemized
                                     BOM (Product History drill-down)
  GET /api/item-search?q=...     -> partial Item Code/Description search
                                     over the full Item Master (RM items by
                                     default; add &types=RAWMATERIAL,... to
                                     widen/narrow)
  GET /api/rd/drafts             -> list all R&D drafts (sandbox BOM
                                     experiments — never touch sku_master.py)
  POST /api/rd/drafts            -> create a draft, seeded from a real
                                     product's BOM
  GET /api/rd/drafts/<id>        -> full draft + all its variants
  PUT /api/rd/drafts/<id>        -> rename / change status
  DELETE /api/rd/drafts/<id>     -> delete a draft and its variants
  POST /api/rd/drafts/<id>/variants        -> add a variant (for compare mode)
  PUT /api/rd/drafts/<id>/variants/<vid>   -> save a variant's edited BOM
  DELETE /api/rd/drafts/<id>/variants/<vid> -> delete a variant
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, send_from_directory, request
from werkzeug.exceptions import HTTPException

from sku_master import SKUS
from config import FINANCE, COMMERCIAL
import costing_store
import bom_store
import rd_store
from item_master import search_items
from colour_lookup import colour_for

APP_HOST = '192.168.0.133'
APP_PORT = 5007
WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
LOG_PATH = os.path.join(os.path.dirname(__file__), 'server.log')

# File log (persists across restarts / terminal closes) + console, so both
# a re-opened terminal and this log file show the same activity. Mirrors
# BOM Tool's bom_server.log pattern. 2MB x 5 backups keeps it bounded.
_file_handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=5, encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s  %(levelname)-7s %(message)s'))
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter('%(asctime)s  %(levelname)-7s %(message)s'))

logger = logging.getLogger('product_contribution')
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# Flask's own request/error logger (werkzeug) -> same file + console.
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addHandler(_file_handler)
werkzeug_logger.addHandler(_console_handler)

app = Flask(__name__, static_folder=None)


@app.before_request
def _log_request():
    logger.info(f'{request.method} {request.path} from {request.remote_addr}')


@app.after_request
def _no_cache(response):
    # This tool's whole point is showing current data (SKU list, RM cost,
    # BOM) — never let a browser, proxy, or embedded preview panel (e.g.
    # VS Code's Edge DevTools) serve a stale cached copy of any response,
    # including the HTML page itself.
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.errorhandler(Exception)
def _log_error(e):
    # Normal HTTP errors (404 for /favicon.ico, etc.) are expected traffic,
    # not bugs — let Flask serve its normal 4xx/5xx response for those.
    # Only log+reraise genuine unhandled exceptions (would otherwise be a
    # silent 500 with nothing in server.log to debug from).
    if isinstance(e, HTTPException):
        return e
    logger.exception(f'Unhandled error on {request.method} {request.path}: {e}')
    raise


@app.route('/')
@app.route('/peps_contribution_tool.html')
def index():
    return send_from_directory(WEB_DIR, 'peps_contribution_tool.html')


@app.route('/favicon.ico')
def favicon():
    # No favicon file exists — every browser auto-requests this on load,
    # so a plain 204 keeps it out of the 404 noise in server.log.
    return '', 204


@app.route('/api/skus')
def api_skus():
    out = []
    for s in SKUS:
        item = dict(s)
        code = s.get('item_code', '')
        item['colour'] = colour_for(code) if code else None
        snap = costing_store.latest(code) if code else None
        if snap:
            month, rm_cost, source_file = snap
            item['rm_cost'] = rm_cost
            item['rm_source'] = f'ledger:{month}'
            item['rm_source_file'] = source_file
        elif s.get('rm_source_note'):
            # Real, but not from the FG/SFG BOM ledger (e.g. Cirrus Latex:
            # derived from the Item Master's own Standard Cost field via a
            # verified conversion ratio — see docs/known_gaps.md). Neither
            # "ledger" (wrong provenance) nor "estimated" (undersells a
            # real, cross-checked figure) is honest here.
            item['rm_source'] = s['rm_source_note']
            item['rm_source_file'] = None
        elif code:
            # Has a real item_code but no ledger snapshot yet for it —
            # still not Ramco-verified, distinct from "no item_code at all".
            item['rm_source'] = 'estimated:no_ledger_match'
            item['rm_source_file'] = None
        else:
            # No item_code means this SKU can never be matched to a Ramco
            # BOM/ledger row — the RM cost is an estimate, not a source-
            # verified figure (see Leakage Analysis §C.1/§C.2).
            item['rm_source'] = 'estimated:no_item_code'
            item['rm_source_file'] = None
        out.append(item)
    return jsonify(out)


@app.route('/api/config')
def api_config():
    return jsonify({'FINANCE': FINANCE, 'COMMERCIAL': COMMERCIAL})


@app.route('/api/bom/<item_code>', methods=['GET'])
def api_bom_get(item_code):
    lines, source = bom_store.get_bom(item_code)
    if lines is None:
        return jsonify({'item_code': item_code, 'lines': None, 'source': None,
                         'message': 'Not yet extracted from the Ramco ledger for this product.'}), 404
    return jsonify({'item_code': item_code, 'lines': lines, 'source': source})


@app.route('/api/bom/<item_code>', methods=['POST'])
def api_bom_save(item_code):
    body = request.get_json(silent=True) or {}
    lines = body.get('lines')
    if not isinstance(lines, list):
        return jsonify({'error': "body must be {'lines': [...]}"}), 400
    bom_store.save_override(item_code, lines)
    logger.info(f'Saved BOM edit for {item_code}: {len(lines)} lines')
    return jsonify({'item_code': item_code, 'lines': lines, 'source': 'override'})


@app.route('/api/bom/<item_code>', methods=['DELETE'])
def api_bom_revert(item_code):
    bom_store.clear_override(item_code)
    logger.info(f'Reverted BOM edits for {item_code} to ledger baseline')
    lines, source = bom_store.get_bom(item_code)
    return jsonify({'item_code': item_code, 'lines': lines, 'source': source})


@app.route('/api/rm-history/<item_code>')
def api_rm_history(item_code):
    rows = costing_store.history(item_code)
    return jsonify([{'month': m, 'rm_cost': rm, 'line_count': lc, 'source_file': sf}
                     for m, rm, lc, sf in rows])


@app.route('/api/bom-history/<item_code>/<month>')
def api_bom_history(item_code, month):
    lines = bom_store.get_snapshot(item_code, month)
    if lines is None:
        return jsonify({'item_code': item_code, 'month': month, 'lines': None,
                         'message': f'No extracted BOM for {item_code} in {month}.'}), 404
    return jsonify({'item_code': item_code, 'month': month, 'lines': lines})


@app.route('/api/item-search')
def api_item_search():
    q = request.args.get('q', '')
    types_param = request.args.get('types', 'RAWMATERIAL')
    item_types = [t.strip() for t in types_param.split(',') if t.strip()] if types_param else None
    results = search_items(q, limit=60, item_types=item_types)
    return jsonify(results)


# ── R&D drafts — sandbox BOM experiments, never written to sku_master.py ──
# "Approved" is a status the user sets by hand once their admin signs off
# in their own separate BOMAT Tool workflow; nothing here promotes a draft
# into the live catalog automatically.

_SKUS_BY_CODE = {s['item_code']: s for s in SKUS if s.get('item_code')}


@app.route('/api/rd/drafts', methods=['GET'])
def api_rd_list():
    return jsonify(rd_store.list_drafts())


@app.route('/api/rd/drafts', methods=['POST'])
def api_rd_create():
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    mode = body.get('mode')
    base_item_code = body.get('base_item_code')
    dummy_item_code = (body.get('dummy_item_code') or '').strip() or None
    if not name or mode not in ('existing', 'new') or not base_item_code:
        return jsonify({'error': "body must be {'name', 'mode': 'existing'|'new', 'base_item_code', "
                                  "'dummy_item_code' (mode='new' only)}"}), 400
    if base_item_code not in _SKUS_BY_CODE:
        return jsonify({'error': f'{base_item_code} is not a real tracked item code'}), 400
    lines, _source = bom_store.get_bom(base_item_code)
    if lines is None:
        return jsonify({'error': f'{base_item_code} has no extracted BOM to start a draft from'}), 400
    draft_id = rd_store.create_draft(name, mode, base_item_code, lines, dummy_item_code)
    logger.info(f'Created R&D draft {draft_id} "{name}" (mode={mode}) from {base_item_code}')
    return jsonify(_with_base_sku(rd_store.get_draft(draft_id))), 201


def _with_base_sku(draft):
    # The draft's base product's real financial parameters (MRP, brand,
    # freight, consumer scheme, sqft) ride along so the frontend can compute
    # a real Net Margin waterfall for the draft — a draft has no financial
    # identity of its own, it borrows its base's. (Commercial-policy keys
    # like rate group / channel key aren't in sku_master.py at all — the
    # frontend resolves those from its own already-loaded catalog instead.)
    if draft is not None:
        draft['base_sku'] = _SKUS_BY_CODE.get(draft['base_item_code'])
    return draft


@app.route('/api/rd/drafts/<int:draft_id>', methods=['GET'])
def api_rd_get(draft_id):
    draft = rd_store.get_draft(draft_id)
    if draft is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(_with_base_sku(draft))


@app.route('/api/rd/drafts/<int:draft_id>', methods=['PUT'])
def api_rd_update(draft_id):
    body = request.get_json(silent=True) or {}
    if rd_store.get_draft(draft_id) is None:
        return jsonify({'error': 'not found'}), 404
    rd_store.update_draft(draft_id, name=body.get('name'), status=body.get('status'))
    logger.info(f'Updated R&D draft {draft_id}: {body}')
    return jsonify(rd_store.get_draft(draft_id))


@app.route('/api/rd/drafts/<int:draft_id>', methods=['DELETE'])
def api_rd_delete(draft_id):
    rd_store.delete_draft(draft_id)
    logger.info(f'Deleted R&D draft {draft_id}')
    return jsonify({'deleted': draft_id})


@app.route('/api/rd/drafts/<int:draft_id>/variants', methods=['POST'])
def api_rd_variant_add(draft_id):
    draft = rd_store.get_draft(draft_id)
    if draft is None:
        return jsonify({'error': 'not found'}), 404
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip() or f'Option {len(draft["variants"]) + 1}'
    copy_from = body.get('copy_from_variant_id')
    lines = None
    if copy_from is not None:
        for v in draft['variants']:
            if v['id'] == copy_from:
                lines = v['lines']
                break
    if lines is None:
        lines = draft['variants'][0]['lines'] if draft['variants'] else []
    variant_id = rd_store.add_variant(draft_id, name, lines)
    logger.info(f'Added variant "{name}" to R&D draft {draft_id}')
    return jsonify(rd_store.get_draft(draft_id)), 201


@app.route('/api/rd/drafts/<int:draft_id>/variants/<int:variant_id>', methods=['PUT'])
def api_rd_variant_save(draft_id, variant_id):
    body = request.get_json(silent=True) or {}
    lines = body.get('lines')
    if not isinstance(lines, list):
        return jsonify({'error': "body must be {'lines': [...]}"}), 400
    rd_store.save_variant(variant_id, lines, name=body.get('name'))
    return jsonify(rd_store.get_draft(draft_id))


@app.route('/api/rd/drafts/<int:draft_id>/variants/<int:variant_id>', methods=['DELETE'])
def api_rd_variant_delete(draft_id, variant_id):
    rd_store.delete_variant(variant_id)
    return jsonify(rd_store.get_draft(draft_id))


if __name__ == '__main__':
    logger.info(f'=== server.py starting — serving {WEB_DIR} + API on http://{APP_HOST}:{APP_PORT} ===')
    logger.info(f'Log file: {LOG_PATH}')
    try:
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
    finally:
        logger.info('=== server.py stopped ===')
