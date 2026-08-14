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

  Auth (mirrors BOM Tool's login_required/session pattern):
  GET/POST /login                -> login page / submit credentials
  GET /logout                    -> clear session, back to /login
  GET /api/me                    -> current session user (username, role)
  GET /api/users                 -> list users (admin/developer only)
  POST /api/users                -> create a user (admin/developer only)
  PUT /api/users/<id>            -> change role / active status / tabs / reset password (admin/developer only)
  POST /api/change-password      -> self-service password change
  GET /api/notifications         -> current user's notifications
  POST /api/notifications/read   -> mark all of the current user's notifications read

  Persisted overrides (previously browser-only, reset on reload):
  POST /api/commercial-rates     -> save a Commercial Rates card's edited
                                     values (history_store logs before/after)
  POST /api/mrp                  -> save one product's edited MRP

  History / rollback:
  GET /api/history                       -> the unified audit trail, newest first
  POST /api/history/<id>/rollback        -> restore a 'commercial_rate' /
                                     'mrp' / 'bom_line' entry's before-state
                                     (developer role only)
"""
import os
import sys
import logging
import secrets
from functools import wraps
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, send_from_directory, request, session, redirect, url_for, render_template
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from sku_master import SKUS
from config import FINANCE, COMMERCIAL
import costing_store
import bom_store
import rd_store
import auth_store
import history_store
import overrides_store
from item_master import search_items
from colour_lookup import colour_for

APP_HOST = '192.168.0.133'
APP_PORT = 5007
WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
LOG_PATH = os.path.join(os.path.dirname(__file__), 'server.log')
SECRET_KEY_PATH = os.path.join(os.path.dirname(__file__), '.flask_secret_key')

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

# Session signing key — generated once on first run, then persisted so
# sessions survive a server restart (this box restarts often, per the
# recurring stray-http.server issue seen during development). Gitignored,
# never checked in.
if os.path.exists(SECRET_KEY_PATH):
    with open(SECRET_KEY_PATH, 'r') as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, 'w') as f:
        f.write(app.secret_key)

auth_store.seed_default_admin()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorised'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Admin and Developer both get full CMS/settings access — Developer is a
    superset of Admin in this tool (see developer_required below for the one
    thing that's Developer-only: rolling back a history entry)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorised'}), 401
        if session.get('role') not in ('admin', 'developer'):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def developer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorised'}), 401
        if session.get('role') != 'developer':
            return jsonify({'error': 'Developer access required'}), 403
        return f(*args, **kwargs)
    return decorated


@app.before_request
def _require_login():
    """Block unauthenticated access to every route except login/logout/
    favicon — same blanket guard BOM Tool uses (app_v2_1.py's require_login)."""
    public = {'login_page', 'logout', 'favicon'}
    if request.endpoint in public:
        return None
    if not session.get('user_id'):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorised'}), 401
        return redirect(url_for('login_page'))


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


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = auth_store.get_user_by_username(username)
        if user and user['is_active'] and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            auth_store.update_last_login(user['id'])
            logger.info(f'Login: {user["username"]} ({user["role"]}) from {request.remote_addr}')
            return redirect(url_for('index'))
        error = 'Invalid username or password.'
        logger.info(f'Failed login attempt for "{username}" from {request.remote_addr}')
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    logger.info(f'Logout: {session.get("username", "")}')
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/api/me')
def api_me():
    user = auth_store.get_user_by_id(session['user_id']) if session.get('user_id') else None
    return jsonify({
        'username': session.get('username'),
        'role': session.get('role'),
        'allowed_tabs': user['allowed_tabs'] if user else [],
    })


@app.route('/api/skus')
def api_skus():
    mrp_overrides = overrides_store.get_mrp_overrides()
    # One query for every item's latest RM-cost snapshot, not one query per
    # SKU (~3700 of them) — costing_store.latest() opens its own sqlite3
    # connection per call, so calling it in this loop was ~3700 connect+
    # query+close round-trips on every single page load, which is exactly
    # what was behind "CMS tab takes 20 seconds to appear" (this route's
    # response gates loadMe(), which is what reveals the CMS/History nav
    # items — see connectToEngine() in the frontend).
    rm_snapshots = costing_store.all_latest()
    out = []
    for s in SKUS:
        item = dict(s)
        code = s.get('item_code', '')
        if item.get('product') in mrp_overrides:
            item['mrp'] = mrp_overrides[item['product']]
        item['colour'] = colour_for(code) if code else None
        snap = rm_snapshots.get(code) if code else None
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
    return jsonify({
        'FINANCE': FINANCE,
        'COMMERCIAL': COMMERCIAL,
        # Flat key/value overrides on top of COMMERCIAL's nested baseline —
        # the frontend already owns the flat-key<->nested-path mapping
        # (COMM_PATH), so this just hands back whatever's been saved and
        # lets applyServerConfig() overlay it the same way it builds COMM
        # from COMMERCIAL in the first place.
        'COMMERCIAL_OVERRIDES': overrides_store.get_commercial_overrides(),
    })


@app.route('/api/commercial-rates', methods=['POST'])
def api_commercial_rates_save():
    body = request.get_json(silent=True) or {}
    entity = (body.get('entity') or 'Commercial Rates').strip()
    values = body.get('values')
    before = body.get('before') or {}
    if not isinstance(values, dict) or not values:
        return jsonify({'error': "body must be {'entity', 'values': {key: number}, 'before': {key: number}}"}), 400
    username = session.get('username')
    for key, value in values.items():
        try:
            overrides_store.set_commercial_override(key, float(value), username)
        except (TypeError, ValueError):
            return jsonify({'error': f'invalid value for {key}'}), 400
    # Apply is card-scoped (every field in the card resubmits, not just the
    # one the user actually typed into) — only log/show fields whose value
    # genuinely moved, and skip the history entry entirely if none did
    # (an Apply click with no real edits shouldn't spam the audit trail).
    changed = {k: v for k, v in values.items() if before.get(k) != v}
    if changed:
        changes = ', '.join(f'{k}: {before.get(k)} → {v}' for k, v in changed.items())
        history_store.record(username, 'commercial_rate', entity, f'{entity} — {changes}', before, values)
    logger.info(f'Commercial Rates saved for {entity} by {username}: {values}')
    return jsonify({'ok': True})


@app.route('/api/mrp', methods=['POST'])
def api_mrp_save():
    body = request.get_json(silent=True) or {}
    product = (body.get('product') or '').strip()
    mrp = body.get('mrp')
    before = body.get('before')
    if not product or mrp is None:
        return jsonify({'error': "body must be {'product', 'mrp', 'before'}"}), 400
    try:
        mrp = float(mrp)
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid mrp value'}), 400
    username = session.get('username')
    overrides_store.set_mrp_override(product, mrp, username)
    before_str = f'₹{before:,.0f}' if before is not None else 'baseline'
    history_store.record(username, 'mrp', product, f'MRP {before_str} → ₹{mrp:,.0f}',
                          {'mrp': before} if before is not None else None, {'mrp': mrp})
    logger.info(f'MRP saved for "{product}" by {username}: {mrp}')
    return jsonify({'ok': True})


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
    before_lines = bom_store.get_override(item_code)
    bom_store.save_override(item_code, lines)
    history_store.record(session.get('username'), 'bom_line', item_code,
                          f'BOM updated ({len(lines)} lines)',
                          {'lines': before_lines} if before_lines is not None else None,
                          {'lines': lines})
    logger.info(f'Saved BOM edit for {item_code}: {len(lines)} lines')
    return jsonify({'item_code': item_code, 'lines': lines, 'source': 'override'})


@app.route('/api/bom/<item_code>', methods=['DELETE'])
def api_bom_revert(item_code):
    before_lines = bom_store.get_override(item_code)
    bom_store.clear_override(item_code)
    if before_lines is not None:
        history_store.record(session.get('username'), 'bom_line', item_code,
                              'BOM edits reverted to ledger baseline',
                              {'lines': before_lines}, None)
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


# ── Users (CMS) — admin-only account management ───────────────────────────

@app.route('/api/users', methods=['GET'])
@admin_required
def api_users_list():
    return jsonify(auth_store.list_users())


@app.route('/api/users', methods=['POST'])
@admin_required
def api_users_create():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    role = body.get('role') if body.get('role') in ('admin', 'developer', 'user') else 'user'
    # Missing key entirely = caller didn't send a tab list at all -> no
    # restriction (matches pre-this-feature behaviour). An explicit []
    # is respected as "no tabs" rather than silently upgraded to all.
    raw_tabs = body.get('allowed_tabs')
    allowed_tabs = auth_store.ALL_TABS if raw_tabs is None else [t for t in raw_tabs if t in auth_store.ALL_TABS]
    if not username or len(password) < 6:
        return jsonify({'error': 'username and a password of at least 6 characters are required'}), 400
    if auth_store.get_user_by_username(username):
        return jsonify({'error': f'"{username}" already exists'}), 400
    user_id = auth_store.create_user(username, password, role, allowed_tabs)
    history_store.record(session.get('username'), 'user_mgmt', username,
                          f'User "{username}" created ({role})',
                          None, {'id': user_id, 'role': role, 'allowed_tabs': allowed_tabs, 'is_active': True})
    logger.info(f'User "{username}" ({role}, tabs={allowed_tabs}) created by {session.get("username")}')
    return jsonify({'id': user_id, 'username': username, 'role': role, 'allowed_tabs': allowed_tabs}), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def api_users_update(user_id):
    body = request.get_json(silent=True) or {}
    target = auth_store.get_user_by_id(user_id)
    if target is None:
        return jsonify({'error': 'not found'}), 404
    before = {'id': user_id, 'role': target['role'], 'allowed_tabs': target['allowed_tabs'], 'is_active': bool(target['is_active'])}
    if 'role' in body and body['role'] in ('admin', 'developer', 'user'):
        auth_store.set_user_role(user_id, body['role'])
    if 'is_active' in body:
        auth_store.set_user_active(user_id, bool(body['is_active']))
    if 'allowed_tabs' in body and isinstance(body['allowed_tabs'], list):
        auth_store.set_user_tabs(user_id, [t for t in body['allowed_tabs'] if t in auth_store.ALL_TABS])
    updated = auth_store.get_user_by_id(user_id)
    after = {'id': user_id, 'role': updated['role'], 'allowed_tabs': updated['allowed_tabs'], 'is_active': bool(updated['is_active'])}
    if after != before:
        history_store.record(session.get('username'), 'user_mgmt', target['username'],
                              f'User "{target["username"]}" updated (role: {before["role"]}→{after["role"]})'
                              if before['role'] != after['role'] else
                              f'User "{target["username"]}" updated',
                              before, after)
    if body.get('new_password'):
        if len(body['new_password']) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        auth_store.set_user_password(user_id, body['new_password'])
        history_store.record(session.get('username'), 'user_password_reset', target['username'],
                              f'Password reset for "{target["username"]}"', None, None)
        logger.info(f'Password reset for user {user_id} by {session.get("username")}')
    logger.info(f'User {user_id} updated by {session.get("username")}: { {k: v for k, v in body.items() if k != "new_password"} }')
    return jsonify({'updated': user_id})


@app.route('/api/change-password', methods=['POST'])
def api_change_password():
    body = request.get_json(silent=True) or {}
    old_pw = body.get('old_password') or ''
    new_pw = body.get('new_password') or ''
    user = auth_store.get_user_by_username(session.get('username', ''))
    if not user or not check_password_hash(user['password_hash'], old_pw):
        return jsonify({'error': 'Current password is incorrect'}), 400
    if len(new_pw) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    auth_store.set_user_password(user['id'], new_pw)
    logger.info(f'Password changed for {user["username"]}')
    return jsonify({'ok': True})


# ── Notifications ───────────────────────────────────────────────────────

@app.route('/api/notifications')
def api_notifications():
    uid = session.get('user_id')
    return jsonify({
        'notifications': auth_store.get_user_notifications(uid),
        'unread_count': auth_store.get_unread_count(uid),
    })


@app.route('/api/notifications/read', methods=['POST'])
def api_notifications_read():
    auth_store.mark_notifications_read(session.get('user_id'))
    return jsonify({'ok': True})


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
    draft_id = rd_store.create_draft(name, mode, base_item_code, lines, dummy_item_code,
                                      created_by=session.get('username'))
    history_store.record(session.get('username'), 'rd_draft', name, f'Draft "{name}" created (from {base_item_code})',
                          None, {'id': draft_id, 'name': name, 'status': 'draft'})
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
    draft = rd_store.get_draft(draft_id)
    if draft is None:
        return jsonify({'error': 'not found'}), 404
    before = {'id': draft_id, 'name': draft['name'], 'status': draft['status']}
    rd_store.update_draft(draft_id, name=body.get('name'), status=body.get('status'))
    updated = rd_store.get_draft(draft_id)
    after = {'id': draft_id, 'name': updated['name'], 'status': updated['status']}
    if after != before:
        history_store.record(session.get('username'), 'rd_draft', updated['name'],
                              f'Draft "{before["name"]}" → status {before["status"]}→{after["status"]}'
                              if before['status'] != after['status'] else
                              f'Draft renamed "{before["name"]}" → "{after["name"]}"',
                              before, after)
    logger.info(f'Updated R&D draft {draft_id}: {body}')
    if body.get('status') == 'pending_review':
        submitter = session.get('username') or draft.get('created_by') or 'Someone'
        auth_store.notify_many(
            auth_store.list_admin_ids(),
            f'{submitter} submitted "{draft["name"]}" for admin review',
            notif_type='rd_review'
        )
    return jsonify(rd_store.get_draft(draft_id))


@app.route('/api/rd/drafts/<int:draft_id>', methods=['DELETE'])
def api_rd_delete(draft_id):
    draft = rd_store.get_draft(draft_id)
    rd_store.delete_draft(draft_id)
    if draft is not None:
        history_store.record(session.get('username'), 'rd_draft', draft['name'],
                              f'Draft "{draft["name"]}" deleted', draft, None)
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


# ── History / rollback — admin+developer can view, only developer can roll
# back (see developer_required's docstring) ────────────────────────────────

@app.route('/api/history', methods=['GET'])
@admin_required
def api_history_list():
    return jsonify(history_store.list_history())


# Action types with a real, safe "write the old blob back" rollback path.
# rd_draft/user_mgmt entries stay fully visible in the History tab for audit
# but have no rollback handler — see history_store.py's module docstring.
_ROLLBACK_ACTIONS = {'commercial_rate', 'mrp', 'bom_line'}


@app.route('/api/history/<int:history_id>/rollback', methods=['POST'])
@developer_required
def api_history_rollback(history_id):
    entry = history_store.get(history_id)
    if entry is None:
        return jsonify({'error': 'not found'}), 404
    if entry['status'] != 'active':
        return jsonify({'error': 'already rolled back'}), 400
    action = entry['action']
    if action not in _ROLLBACK_ACTIONS:
        return jsonify({'error': f'"{action}" entries cannot be rolled back'}), 400
    before = entry['before_data']
    username = session.get('username')

    if action == 'commercial_rate':
        for key, value in (before or {}).items():
            if value is None:
                overrides_store.clear_commercial_override(key)
            else:
                overrides_store.set_commercial_override(key, float(value), username)
    elif action == 'mrp':
        if before is None or before.get('mrp') is None:
            overrides_store.clear_mrp_override(entry['entity'])
        else:
            overrides_store.set_mrp_override(entry['entity'], float(before['mrp']), username)
    elif action == 'bom_line':
        lines = (before or {}).get('lines')
        if lines is not None:
            bom_store.save_override(entry['entity'], lines)
        else:
            bom_store.clear_override(entry['entity'])

    history_store.mark_rolled_back(history_id)
    logger.info(f'History #{history_id} ({action}: {entry["entity"]}) rolled back by {username}')
    return jsonify({'ok': True, 'id': history_id})


if __name__ == '__main__':
    logger.info(f'=== server.py starting — serving {WEB_DIR} + API on http://{APP_HOST}:{APP_PORT} ===')
    logger.info(f'Log file: {LOG_PATH}')
    try:
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
    finally:
        logger.info('=== server.py stopped ===')
