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


@app.route('/api/skus')
def api_skus():
    out = []
    for s in SKUS:
        item = dict(s)
        code = s.get('item_code', '')
        snap = costing_store.latest(code) if code else None
        if snap:
            month, rm_cost, source_file = snap
            item['rm_cost'] = rm_cost
            item['rm_source'] = f'ledger:{month}'
            item['rm_source_file'] = source_file
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


if __name__ == '__main__':
    logger.info(f'=== server.py starting — serving {WEB_DIR} + API on http://{APP_HOST}:{APP_PORT} ===')
    logger.info(f'Log file: {LOG_PATH}')
    try:
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
    finally:
        logger.info('=== server.py stopped ===')
