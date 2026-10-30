import json
import os
import sqlite3
import time
from collections.abc import MutableMapping

from bot import database


class _PersistentState(dict):
    """A dict-compatible workflow state that saves top-level mutations."""

    def __init__(self, values, save_callback):
        super().__init__(values)
        self._save_callback = save_callback

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._save_callback(self)

    def __delitem__(self, key):
        super().__delitem__(key)
        self._save_callback(self)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save_callback(self)

    def pop(self, key, *args):
        existed = key in self
        value = super().pop(key, *args)
        if existed:
            self._save_callback(self)
        return value

    def clear(self):
        super().clear()
        self._save_callback(self)


_MISSING = object()


class PersistentStateMap(MutableMapping):
    """SQLite-backed mapping for short-lived user/admin conversation states.

    States survive process restarts but expire automatically. Writes use a
    plain SQLite connection so transient UI state does not trigger remote
    database backup uploads.
    """

    def __init__(self, namespace, ttl_seconds=7 * 24 * 60 * 60, db_path=None):
        self.namespace = str(namespace)
        self.ttl_seconds = int(ttl_seconds)
        self.db_path = db_path

    def _path(self):
        return self.db_path or database.DB_PATH

    def _connect(self):
        path = self._path()
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_states (
                namespace TEXT NOT NULL,
                user_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                PRIMARY KEY(namespace, user_id)
            )
        """)
        return conn

    def _save(self, user_id, state):
        now = time.time()
        payload = json.dumps(dict(state), ensure_ascii=False, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO workflow_states
                    (namespace, user_id, payload, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, user_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
            """, (
                self.namespace, str(user_id), payload, now,
                now + self.ttl_seconds
            ))

    def __getitem__(self, user_id):
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM workflow_states WHERE namespace = ? AND expires_at <= ?",
                (self.namespace, now)
            )
            row = conn.execute("""
                SELECT payload FROM workflow_states
                WHERE namespace = ? AND user_id = ? AND expires_at > ?
            """, (self.namespace, str(user_id), now)).fetchone()
        if not row:
            raise KeyError(user_id)
        values = json.loads(row[0])
        if not isinstance(values, dict):
            self.__delitem__(user_id)
            raise KeyError(user_id)
        return _PersistentState(
            values, lambda state: self._save(user_id, state)
        )

    def __setitem__(self, user_id, state):
        if not isinstance(state, dict):
            raise TypeError("Workflow state must be a dictionary.")
        self._save(user_id, state)

    def __delitem__(self, user_id):
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_states WHERE namespace = ? AND user_id = ?",
                (self.namespace, str(user_id))
            )
        if cursor.rowcount == 0:
            raise KeyError(user_id)

    def __iter__(self):
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM workflow_states WHERE namespace = ? AND expires_at <= ?",
                (self.namespace, now)
            )
            rows = conn.execute(
                "SELECT user_id FROM workflow_states WHERE namespace = ?",
                (self.namespace,)
            ).fetchall()
        return iter([row[0] for row in rows])

    def __len__(self):
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM workflow_states WHERE namespace = ? AND expires_at <= ?",
                (self.namespace, now)
            )
            row = conn.execute(
                "SELECT COUNT(*) FROM workflow_states WHERE namespace = ?",
                (self.namespace,)
            ).fetchone()
        return int(row[0])

    def pop(self, user_id, default=_MISSING):
        try:
            value = self[user_id]
        except KeyError:
            if default is not _MISSING:
                return default
            raise
        self.__delitem__(user_id)
        return dict(value)

    def clear(self):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM workflow_states WHERE namespace = ?",
                (self.namespace,)
            )
