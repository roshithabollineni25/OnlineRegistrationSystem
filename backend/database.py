"""
Online Course Registration System - Database Abstraction Layer
Supports both SQLite (local zero-setup development) and PostgreSQL (production deployment).
Automatic detection via DATABASE_URL or POSTGRES_URL environment variable.
"""

import os
import re
import sys
from pathlib import Path
from contextlib import contextmanager
import sqlite3

# Try loading python-dotenv if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Database target resolution
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("DATABASE_URI")
)

# Standard SQLite fallback path
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "courses.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", DEFAULT_SQLITE_PATH))

# PostgreSQL detection
IS_POSTGRES = bool(
    DATABASE_URL
    and (
        DATABASE_URL.startswith("postgres://")
        or DATABASE_URL.startswith("postgresql://")
    )
)

if IS_POSTGRES:
    # Fix for Heroku / Render legacy postgres:// scheme
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("[WARNING] psycopg2 is required for PostgreSQL connections. Install via pip install psycopg2-binary", file=sys.stderr)
        IS_POSTGRES = False


class PostgresRow(dict):
    """Row wrapper that supports both dict and tuple indexing (row['col'] and row[0])."""
    def __init__(self, cursor_description, values):
        super().__init__()
        self._values = list(values)
        self._keys = [col.name for col in cursor_description]
        for key, val in zip(self._keys, self._values):
            self[key] = val

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return super().__getitem__(item)

    def get(self, key, default=None):
        return super().get(key, default)

    def keys(self):
        return self._keys


class PostgresCursorWrapper:
    """Cursor wrapper that translates SQLite-style queries (?) into Postgres (%s)."""
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self.lastrowid = None

    def _translate_sql(self, sql):
        clean_sql = sql.strip()
        # Ignore SQLite-specific PRAGMA commands
        if clean_sql.upper().startswith("PRAGMA"):
            return None, False

        # Translate BEGIN IMMEDIATE to standard BEGIN
        if clean_sql.upper().startswith("BEGIN IMMEDIATE"):
            clean_sql = "BEGIN"

        # Check if INSERT without RETURNING id
        is_insert = clean_sql.upper().startswith("INSERT INTO") and "RETURNING" not in clean_sql.upper()
        if is_insert:
            clean_sql += " RETURNING id"

        # Convert SQLite parameter marker ? to Postgres %s
        clean_sql = clean_sql.replace("?", "%s")
        return clean_sql, is_insert

    def execute(self, sql, params=None):
        translated_sql, is_insert = self._translate_sql(sql)
        if translated_sql is None:
            return self

        if params is None:
            self._cursor.execute(translated_sql)
        else:
            self._cursor.execute(translated_sql, params)

        if is_insert:
            try:
                row = self._cursor.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                self.lastrowid = None
        return self

    def executemany(self, sql, seq_of_params):
        translated_sql, _ = self._translate_sql(sql)
        if translated_sql is None:
            return self
        self._cursor.executemany(translated_sql, seq_of_params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return PostgresRow(self._cursor.description, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        desc = self._cursor.description
        return [PostgresRow(desc, r) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class PostgresConnectionWrapper:
    """Connection wrapper conforming to Python DB-API for PostgreSQL."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        cur = self.cursor()
        return cur.executemany(sql, seq_of_params)

    def executescript(self, script):
        clean_script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        clean_script = clean_script.replace("PRAGMA foreign_keys = ON;", "")
        clean_script = clean_script.replace("PRAGMA foreign_keys = ON", "")
        with self._conn.cursor() as cur:
            cur.execute(clean_script)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


@contextmanager
def connect():
    """
    Context manager providing a unified database connection.
    Automatically connects to PostgreSQL if DATABASE_URL is configured,
    or SQLite file otherwise.
    """
    if IS_POSTGRES:
        raw_conn = psycopg2.connect(DATABASE_URL)
        wrapper = PostgresConnectionWrapper(raw_conn)
        try:
            yield wrapper
            wrapper.commit()
        except Exception:
            wrapper.rollback()
            raise
        finally:
            wrapper.close()
    else:
        # SQLite connection
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def get_db_info():
    """Returns runtime database configuration metadata."""
    if IS_POSTGRES:
        # Mask credentials in DATABASE_URL
        masked = re.sub(r":([^@]+)@", r":****@", DATABASE_URL)
        return {
            "engine": "PostgreSQL",
            "connection": masked,
            "persistent": True,
            "mode": "production"
        }
    else:
        return {
            "engine": "SQLite",
            "path": str(DB_PATH.resolve()),
            "persistent": True,
            "mode": "development"
        }
