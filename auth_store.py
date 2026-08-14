"""
auth_store.py — users + notifications, same SQLite DB and schema style as
bom_store.py/costing_store.py/rd_store.py.

Two roles only, not BOM Tool's four-tier admin/developer/sub_admin/user:
this tool doesn't have BOM Tool's approval-chain complexity, so 'admin'
(sees Settings + CMS + everything, ignores allowed_tabs) and 'user'
(sees only whichever of ALL_TABS they were granted at creation) is
enough. Password hashing via werkzeug.security, same as BOM Tool.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "costing_history.db"  # same DB file as the other stores

# The 4 sidebar "Views" tabs a 'user'-role account can be individually
# granted/denied at creation (see server.py's /api/users POST). Settings
# (self-service account page) and CMS (already hard-gated to role=admin)
# are deliberately not part of this list — there's no scenario where
# either should be independently toggled per user.
ALL_TABS = ["nm", "params", "material", "rd"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',  -- 'admin' | 'user'
    allowed_tabs  TEXT    NOT NULL DEFAULT '[]',    -- JSON list, subset of ALL_TABS (ignored for role='admin', who always sees everything)
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    last_login    TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    message     TEXT    NOT NULL,
    notif_type  TEXT    NOT NULL DEFAULT 'info',
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    # Migrate existing DBs: allowed_tabs was added after the users table
    # already existed for some installs.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "allowed_tabs" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN allowed_tabs TEXT NOT NULL DEFAULT '[]'")
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def seed_default_admin():
    """First run only: create a default admin account if no users exist yet."""
    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            pw_hash = generate_password_hash("Admin@1234")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, is_active, created_at) "
                "VALUES ('admin', ?, 'admin', 1, ?)",
                (pw_hash, _now())
            )
            print("=" * 60)
            print("  FIRST RUN: default admin account created")
            print("  Username : admin")
            print("  Password : Admin@1234")
            print("  Please change the password after first login (Settings tab).")
            print("=" * 60)


def get_user_by_username(username: str):
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, allowed_tabs, is_active FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if not row:
            return None
        d = dict(zip(["id", "username", "password_hash", "role", "allowed_tabs", "is_active"], row))
        d["allowed_tabs"] = json.loads(d["allowed_tabs"])
        return d


def get_user_by_id(user_id: int):
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, username, role, allowed_tabs, is_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(zip(["id", "username", "role", "allowed_tabs", "is_active"], row))
        d["allowed_tabs"] = json.loads(d["allowed_tabs"])
        return d


def update_last_login(user_id: int):
    with _conn() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))


def list_users():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, username, role, allowed_tabs, is_active, created_at, last_login FROM users ORDER BY username"
        ).fetchall()
        cols = ["id", "username", "role", "allowed_tabs", "is_active", "created_at", "last_login"]
        out = []
        for r in rows:
            d = dict(zip(cols, r))
            d["allowed_tabs"] = json.loads(d["allowed_tabs"])
            out.append(d)
        return out


def create_user(username: str, password: str, role: str = "user", allowed_tabs: list | None = None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, allowed_tabs, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (username, generate_password_hash(password), role, json.dumps(allowed_tabs or []), _now())
        )
        return cur.lastrowid


def set_user_active(user_id: int, is_active: bool):
    with _conn() as conn:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))


def set_user_role(user_id: int, role: str):
    with _conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_tabs(user_id: int, allowed_tabs: list):
    with _conn() as conn:
        conn.execute("UPDATE users SET allowed_tabs = ? WHERE id = ?", (json.dumps(allowed_tabs), user_id))


def set_user_password(user_id: int, password: str):
    with _conn() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                      (generate_password_hash(password), user_id))


def list_admin_ids() -> list[int]:
    with _conn() as conn:
        rows = conn.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
        return [r[0] for r in rows]


def notify(user_id: int, message: str, notif_type: str = "info"):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO notifications (user_id, message, notif_type, is_read, created_at) VALUES (?, ?, ?, 0, ?)",
            (user_id, message, notif_type, _now())
        )


def notify_many(user_ids: list[int], message: str, notif_type: str = "info"):
    for uid in user_ids:
        notify(uid, message, notif_type)


def get_user_notifications(user_id: int, limit: int = 30) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, message, notif_type, is_read, created_at FROM notifications "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        cols = ["id", "message", "notif_type", "is_read", "created_at"]
        return [dict(zip(cols, r)) for r in rows]


def get_unread_count(user_id: int) -> int:
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
        ).fetchone()[0]


def mark_notifications_read(user_id: int):
    with _conn() as conn:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
