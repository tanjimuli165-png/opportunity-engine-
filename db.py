import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import DB_PATH
from app.database.models import Report


_HASH_ITERATIONS = 310_000


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


class ReportStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = str(path)
        self._init()

    def _init(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, topic TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL, user_id TEXT NOT NULL DEFAULT '')")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
            if "user_id" not in columns:
                conn.execute("ALTER TABLE reports ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")

    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        normalized = username.strip().lower()
        if not 3 <= len(normalized) <= 40 or not normalized.replace("_", "").replace("-", "").isalnum():
            return False, "Use 3–40 letters, numbers, underscores, or hyphens for the username."
        if len(password) < 8:
            return False, "Password must contain at least 8 characters."
        user_id = secrets.token_hex(16)
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute("INSERT INTO users (user_id, username, password_hash, created_at) VALUES (?, ?, ?, datetime('now'))", (user_id, normalized, _password_hash(password)))
            return True, "Account created. You can now log in."
        except sqlite3.IntegrityError:
            return False, "That username is already registered."

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        normalized = username.strip().lower()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT user_id, username, password_hash FROM users WHERE username = ?", (normalized,)).fetchone()
        if not row or not _password_matches(password, row[2]):
            return None
        return {"user_id": row[0], "username": row[1]}

    def create_session(self, user_id: str, days: int = 30) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash, user_id, expires_at))
        return token

    def authenticate_session(self, token: str) -> Optional[dict]:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT users.user_id, users.username, sessions.expires_at FROM sessions JOIN users ON users.user_id = sessions.user_id WHERE sessions.token_hash = ?", (token_hash,)).fetchone()
        if not row:
            return None
        try:
            if datetime.fromisoformat(row[2]) <= datetime.now(timezone.utc):
                self.revoke_session(token)
                return None
        except ValueError:
            return None
        return {"user_id": row[0], "username": row[1]}

    def revoke_session(self, token: str) -> None:
        token_hash = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def save(self, report: Report, user_id: str | None = None):
        owner = user_id or report.user_id or "legacy"
        report.user_id = owner
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR REPLACE INTO reports (id, topic, created_at, payload, user_id) VALUES (?, ?, ?, ?, ?)", (report.id, report.topic, report.created_at.isoformat(), report.model_dump_json(), owner))

    def get(self, report_id: str, user_id: str | None = None) -> Optional[Report]:
        with sqlite3.connect(self.path) as conn:
            if user_id:
                row = conn.execute("SELECT payload FROM reports WHERE id = ? AND user_id = ?", (report_id, user_id)).fetchone()
            else:
                row = conn.execute("SELECT payload FROM reports WHERE id = ?", (report_id,)).fetchone()
        return Report.model_validate_json(row[0]) if row else None

    def recent(self, user_id: str | None = None, limit: int = 10) -> List[Report]:
        with sqlite3.connect(self.path) as conn:
            if user_id:
                rows = conn.execute("SELECT payload FROM reports WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Report.model_validate_json(row[0]) for row in rows]
