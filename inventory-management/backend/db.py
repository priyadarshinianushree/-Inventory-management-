"""SQLite helpers."""
import sqlite3

from flask import g

import config


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """One connection per request."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()  # uncommitted work is discarded (automatic rollback)


def create_schema(conn):
    with open(config.SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
